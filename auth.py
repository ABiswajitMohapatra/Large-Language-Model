"""
JWT authentication module for BiswaLex/Mastishk.

IMPORTANT FIX: this module previously owned its own SQLite database
(auth.db) for users/refresh tokens/password-reset OTPs, completely
separate from db.py's Postgres tables. db.py's chat_sessions/messages
tables have a foreign key to a `users` table - but that Postgres `users`
table was never actually written to, because signup/login here wrote to
the SQLite auth.db instead. Two disjoint user stores with two disjoint
id spaces is why cloud chat history could never really work: the user id
embedded in the JWT (from SQLite) didn't correspond to any row a
Postgres-backed chat_sessions.user_id could reliably join against, and on
most hosting platforms (e.g. ephemeral containers) auth.db doesn't even
persist across restarts.

This version uses db.py's SessionLocal/User/RefreshToken/PasswordReset
models exclusively, so there is exactly one users table (Postgres) and
exactly one id space, matching what chat_sessions.user_id expects.

All function names/signatures are unchanged from before, so main.py does
not need to change.

Env vars (all optional, sensible defaults for local/dev use):
  JWT_SECRET            - signing secret for access/refresh tokens.
                          IMPORTANT: set a real random value in production;
                          falls back to a dev-only default otherwise.
  JWT_ACCESS_MINUTES    - access token lifetime in minutes (default 30)
  JWT_REFRESH_DAYS      - refresh token lifetime in days (default 7)
  OTP_TTL_MINUTES       - password-reset OTP lifetime in minutes (default 10)
  SMTP_HOST / SMTP_PORT
  SMTP_USER or SMTP_USERNAME
  SMTP_PASS or SMTP_PASSWORD
  SMTP_FROM or FROM_EMAIL
                        - if host/port/user/pass are all set, OTP/welcome/
                          login-notification emails are sent for real via
                          SMTP. If not configured (or the send fails), the
                          email body is logged instead (dev fallback) so
                          every flow is still testable/observable without
                          an email provider.
"""

import os
import re
import hashlib
import hmac
import secrets
import json
import urllib.request
import urllib.error
import logging
import datetime

import jwt  # PyJWT

import db  # Postgres (Supabase) persistence layer - single source of truth

logger = logging.getLogger("auth.email")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-insecure-secret-change-me")
JWT_ALGO = "HS256"
JWT_ACCESS_MINUTES = int(os.environ.get("JWT_ACCESS_MINUTES", "30"))
JWT_REFRESH_DAYS = int(os.environ.get("JWT_REFRESH_DAYS", "7"))
OTP_TTL_MINUTES = int(os.environ.get("OTP_TTL_MINUTES", "10"))

# Resend (https://resend.com) - HTTP API, not SMTP. Read once at import
# time is deliberately avoided for the API key itself (read fresh inside
# _send_email each call) so a key set/rotated after process start (e.g. via
# a secrets manager that updates os.environ at runtime) is still picked up
# without a restart.
RESEND_API_URL = "https://api.resend.com/emails"
RESEND_FROM = os.environ.get("FROM_EMAIL") or os.environ.get("RESEND_FROM") or "Mastishk <onboarding@resend.dev>"
ADMIN_NOTIFY_EMAIL = os.environ.get("ADMIN_NOTIFY_EMAIL")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Make sure tables exist (no-op if main.py already calls db.init_db() at
# startup - create_all is idempotent).
db.init_db()


# ============================================================================
# PASSWORD HASHING (PBKDF2-HMAC-SHA256, stdlib only - no extra dependency)
# ============================================================================

def _hash_password(password: str, salt: str = None) -> tuple:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return digest.hex(), salt


def _verify_password(password: str, password_hash: str, salt: str) -> bool:
    digest, _ = _hash_password(password, salt)
    return hmac.compare_digest(digest, password_hash)


PASSWORD_MIN_LEN = 8


def validate_password_strength(password: str):
    if not password or len(password) < PASSWORD_MIN_LEN:
        raise AuthError(f"Password must be at least {PASSWORD_MIN_LEN} characters long.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        raise AuthError("Password must contain both letters and numbers.")


class AuthError(Exception):
    """User-facing auth error (bad credentials, validation failure, etc)."""
    pass


# ============================================================================
# USER CRUD (Postgres via db.py)
# ============================================================================

def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _user_to_dict(u) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "password_hash": u.password_hash,
        "salt": u.salt,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def get_user_by_email(email: str):
    email = (email or "").lower().strip()
    with db.get_db() as session:
        u = session.query(db.User).filter(db.User.email == email).first()
        return _user_to_dict(u) if u else None


def get_user_by_id(user_id: int):
    with db.get_db() as session:
        u = session.query(db.User).filter(db.User.id == user_id).first()
        return _user_to_dict(u) if u else None


def signup(name: str, email: str, password: str, confirm_password: str,
           ip_address: str = None, user_agent: str = None):
    name = (name or "").strip()
    email = (email or "").strip().lower()

    if not name:
        raise AuthError("Name is required.")
    if not email or not EMAIL_PATTERN.match(email):
        raise AuthError("A valid email is required.")
    if password != confirm_password:
        raise AuthError("Passwords do not match.")
    validate_password_strength(password)

    if get_user_by_email(email):
        raise AuthError("An account with this email already exists.")

    password_hash, salt = _hash_password(password)
    with db.get_db() as session:
        u = db.User(name=name, email=email, password_hash=password_hash, salt=salt)
        session.add(u)
        session.flush()
        user_id = u.id

    new_user = get_user_by_id(user_id)

    # Welcome email is best-effort: signup must succeed even if SMTP is
    # down/misconfigured, so any failure here is only logged, never raised.
    try:
        _send_welcome_email(new_user)
    except Exception as e:
        logger.error("Unexpected error sending welcome email to %s: %s", email, e, exc_info=True)

    # Admin signup notification: best-effort, only after the user row is
    # already committed above - signup must succeed even if this fails.
    try:
        _send_admin_signup_notification(new_user, ip_address, user_agent)
    except Exception as e:
        logger.error("[auth] Admin signup notification FAILED: %s", e, exc_info=True)

    return new_user


def login(email: str, password: str):
    email = (email or "").strip().lower()
    user = get_user_by_email(email)
    # Constant-shape error regardless of which part was wrong, so we don't
    # leak whether an email is registered.
    if not user or not _verify_password(password or "", user["password_hash"], user["salt"]):
        raise AuthError("Invalid email or password.")

    # Login notification is best-effort: login must succeed even if SMTP is
    # down/misconfigured, so any failure here is only logged, never raised.
    try:
        _send_login_notification_email(user)
    except Exception as e:
        logger.error("Unexpected error sending login notification to %s: %s", email, e, exc_info=True)

    return user


# ============================================================================
# JWT ACCESS + REFRESH TOKENS
# ============================================================================

def create_access_token(user: dict) -> str:
    now = _now()
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "name": user["name"],
        "type": "access",
        "iat": now,
        "exp": now + datetime.timedelta(minutes=JWT_ACCESS_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def create_refresh_token(user: dict) -> str:
    token = secrets.token_urlsafe(48)
    expires_at = _now() + datetime.timedelta(days=JWT_REFRESH_DAYS)
    with db.get_db() as session:
        session.add(db.RefreshToken(token=token, user_id=user["id"], expires_at=expires_at))
    return token


def issue_token_pair(user: dict) -> dict:
    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "bearer",
        "expires_in": JWT_ACCESS_MINUTES * 60,
        "user": {"id": user["id"], "name": user["name"], "email": user["email"]},
    }


def decode_access_token(token: str) -> dict:
    """Raises jwt exceptions on invalid/expired tokens - caller decides how
    to surface those (main.py maps them to 401s)."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])


def refresh_access_token(refresh_token: str) -> dict:
    with db.get_db() as session:
        row = session.query(db.RefreshToken).filter(db.RefreshToken.token == refresh_token).first()
        if not row:
            raise AuthError("Invalid refresh token.")
        if row.revoked:
            raise AuthError("This session has been logged out. Please log in again.")
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
        if expires_at < _now():
            raise AuthError("Session expired. Please log in again.")
        user_id = row.user_id

    user = get_user_by_id(user_id)
    if not user:
        raise AuthError("Account no longer exists.")

    new_access = create_access_token(user)
    return {
        "access_token": new_access,
        "token_type": "bearer",
        "expires_in": JWT_ACCESS_MINUTES * 60,
    }


def revoke_refresh_token(refresh_token: str):
    with db.get_db() as session:
        row = session.query(db.RefreshToken).filter(db.RefreshToken.token == refresh_token).first()
        if row:
            row.revoked = True


def revoke_all_refresh_tokens_for_user(user_id: int):
    with db.get_db() as session:
        session.query(db.RefreshToken).filter(db.RefreshToken.user_id == user_id).update({"revoked": True})


# ============================================================================
# FORGOT PASSWORD (email + OTP -> verify -> reset)
# ============================================================================

def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def _smtp_config():
    """Reads SMTP config from env vars. Accepts both naming conventions
    (SMTP_USER/SMTP_PASS/SMTP_FROM, the ones this module originally used,
    AND SMTP_USERNAME/SMTP_PASSWORD/FROM_EMAIL, the ones actually set in
    the deployment env) - THIS mismatch was the root cause of every email
    silently going to the dev console instead of real SMTP: os.environ.get
    on a name that was never set just returns None, which fails the
    `if smtp_host and smtp_port and smtp_user and smtp_pass` check below
    with no error raised anywhere, so it looked like emails were "broken"
    with nothing in the logs to explain why."""
    host = os.environ.get("SMTP_HOST")
    port = os.environ.get("SMTP_PORT")
    user = os.environ.get("SMTP_USER") or os.environ.get("SMTP_USERNAME")
    pw = os.environ.get("SMTP_PASS") or os.environ.get("SMTP_PASSWORD")
    from_addr = os.environ.get("SMTP_FROM") or os.environ.get("FROM_EMAIL") or user
    return host, port, user, pw, from_addr


def _send_email(to_email: str, subject: str, body: str) -> bool:
    """Shared sender used by OTP/welcome/login-notification emails, now via
    the Resend HTTP API (RESEND_API_KEY). Never raises - callers treat
    email as best-effort and must not fail the surrounding auth flow
    because of it. Logs from/to/status/full JSON response every time."""
    api_key = os.environ.get("RESEND_API_KEY")

    if not api_key:
        logger.warning(
            "RESEND_API_KEY not configured - email NOT sent: from=%s to=%s subject=%r",
            RESEND_FROM, to_email, subject,
        )
        logger.info("(DEV fallback) email body for %s: %s", to_email, body)
        return False

    payload = json.dumps({
        "from": RESEND_FROM,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }).encode("utf-8")

    req = urllib.request.Request(
        RESEND_API_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mastishk-Backend/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            resp_body = resp.read().decode("utf-8", errors="replace")
        logger.info(
            "Resend response: from=%s to=%s status=%s body=%s",
            RESEND_FROM, to_email, status, resp_body,
        )
        if 200 <= status < 300:
            logger.info("Email sent: to=%s subject=%r", to_email, subject)
            return True
        logger.error("Resend send FAILED: from=%s to=%s status=%s body=%s",
                      RESEND_FROM, to_email, status, resp_body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        logger.error(
            "Resend send FAILED: from=%s to=%s status=%s body=%s",
            RESEND_FROM, to_email, e.code, err_body,
        )
        if e.code == 403 and "onboarding@resend.dev" in RESEND_FROM:
            logger.error(
                "[auth] Resend 403: onboarding@resend.dev can only send to "
                "the account owner's verified email. Verify a custom domain "
                "in Resend and set FROM_EMAIL/RESEND_FROM to an address on "
                "that domain to send to arbitrary recipients."
            )
    except Exception as e:
        logger.error("Unexpected error calling Resend: from=%s to=%s error=%s",
                      RESEND_FROM, to_email, e, exc_info=True)

    logger.info("(DEV fallback) email body for %s: %s", to_email, body)
    return False


def _send_otp_email(email: str, otp: str) -> bool:
    return _send_email(
        email,
        "Your Mastishk password reset code",
        f"Your Mastishk password reset code is: {otp}\n\n"
        f"This code expires in {OTP_TTL_MINUTES} minutes. "
        f"If you didn't request this, you can safely ignore this email.",
    )


def _send_welcome_email(user: dict) -> bool:
    return _send_email(
        user["email"],
        "Welcome to Mastishk",
        f"Hi {user.get('name') or ''},\n\n"
        f"Your Mastishk account ({user['email']}) has been created successfully. "
        f"You can now sign in and start chatting.\n\n"
        f"If you didn't create this account, please ignore this email.",
    )


def _send_login_notification_email(user: dict) -> bool:
    if not ADMIN_NOTIFY_EMAIL:
        logger.warning("[auth] ADMIN_NOTIFY_EMAIL not configured - admin login notification NOT sent")
        return False
    login_time = _now().strftime("%Y-%m-%d %H:%M:%S UTC")
    sent = _send_email(
        ADMIN_NOTIFY_EMAIL,
        "New login to Mastishk account",
        f"User: {user.get('name') or ''}\n"
        f"Email: {user['email']}\n"
        f"Time: {login_time}\n",
    )
    if sent:
        logger.info("[auth] Admin login notification sent to %s", ADMIN_NOTIFY_EMAIL)
    else:
        logger.error("[auth] Admin login notification FAILED: send returned False")
    return sent


def _send_admin_signup_notification(user: dict, ip_address: str = None, user_agent: str = None) -> bool:
    if not ADMIN_NOTIFY_EMAIL:
        logger.warning("[auth] ADMIN_NOTIFY_EMAIL not configured - admin signup notification NOT sent")
        return False

    now = _now()
    utc_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        local_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S (local)")
    except Exception:
        local_str = "N/A"

    try:
        with db.get_db() as session:
            total_users = session.query(db.User).count()
    except Exception:
        total_users = "N/A"

    body = (
        f"Full Name: {user.get('name') or ''}\n"
        f"Email: {user['email']}\n"
        f"Registration Time (UTC): {utc_str}\n"
        f"Registration Time (Local): {local_str}\n"
        f"IP Address: {ip_address or 'N/A'}\n"
        f"User Agent / Device: {user_agent or 'N/A'}\n"
        f"Total Registered Users: {total_users}\n"
    )

    sent = _send_email(ADMIN_NOTIFY_EMAIL, "\U0001F195 New User Registered - Mastishk", body)
    if sent:
        logger.info("[auth] Admin signup notification sent to %s", ADMIN_NOTIFY_EMAIL)
    else:
        logger.error("[auth] Admin signup notification FAILED: send returned False")
    return sent


def request_password_reset(email: str):
    email = (email or "").strip().lower()
    if not email or not EMAIL_PATTERN.match(email):
        raise AuthError("A valid email is required.")

    user = get_user_by_email(email)
    otp = _generate_otp()
    expires_at = _now() + datetime.timedelta(minutes=OTP_TTL_MINUTES)
    otp_hash = _hash_otp(otp)

    # Always write/overwrite a reset row and "send" an OTP even if the user
    # doesn't exist, so this endpoint doesn't leak which emails are
    # registered. (verify/reset below still correctly no-ops for unknown
    # accounts.)
    with db.get_db() as session:
        row = session.query(db.PasswordReset).filter(db.PasswordReset.email == email).first()
        if row:
            row.otp_hash = otp_hash
            row.expires_at = expires_at
            row.verified = False
            row.reset_token = None
            row.attempts = 0
        else:
            session.add(db.PasswordReset(email=email, otp_hash=otp_hash, expires_at=expires_at))

    if user:
        try:
            email_sent = _send_otp_email(email, otp)
        except Exception as e:
            logger.error("Unexpected error sending OTP email to %s: %s", email, e, exc_info=True)
            email_sent = False
    else:
        email_sent = False

    return {"message": "If an account exists for this email, a reset code has been sent.",
            "email_sent": email_sent}


MAX_OTP_ATTEMPTS = 5


def verify_otp(email: str, otp: str) -> str:
    """Returns a short-lived reset_token to be used with reset_password."""
    email = (email or "").strip().lower()
    with db.get_db() as session:
        row = session.query(db.PasswordReset).filter(db.PasswordReset.email == email).first()

        if not row:
            raise AuthError("No password reset was requested for this email.")
        if row.attempts >= MAX_OTP_ATTEMPTS:
            raise AuthError("Too many incorrect attempts. Please request a new code.")
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
        if expires_at < _now():
            raise AuthError("This code has expired. Please request a new one.")

        if not hmac.compare_digest(_hash_otp((otp or "").strip()), row.otp_hash):
            row.attempts = row.attempts + 1
            raise AuthError("Incorrect code.")

        reset_token = secrets.token_urlsafe(32)
        row.verified = True
        row.reset_token = reset_token

    return reset_token


def reset_password(email: str, reset_token: str, new_password: str, confirm_password: str):
    email = (email or "").strip().lower()
    if new_password != confirm_password:
        raise AuthError("Passwords do not match.")
    validate_password_strength(new_password)

    with db.get_db() as session:
        row = session.query(db.PasswordReset).filter(db.PasswordReset.email == email).first()

        if not row or not row.verified or not row.reset_token:
            raise AuthError("Please verify your reset code first.")
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
        if expires_at < _now():
            raise AuthError("This reset session has expired. Please start over.")
        if not hmac.compare_digest(reset_token or "", row.reset_token):
            raise AuthError("Invalid or expired reset session.")

    user = get_user_by_email(email)
    if not user:
        raise AuthError("Account not found.")

    password_hash, salt = _hash_password(new_password)
    with db.get_db() as session:
        u = session.query(db.User).filter(db.User.id == user["id"]).first()
        u.password_hash = password_hash
        u.salt = salt
        # One-time use: clear the reset row so the same OTP/token can't be
        # replayed, and log out any existing sessions for safety.
        session.query(db.PasswordReset).filter(db.PasswordReset.email == email).delete()

    revoke_all_refresh_tokens_for_user(user["id"])
    return {"message": "Password reset successfully. Please log in with your new password."}