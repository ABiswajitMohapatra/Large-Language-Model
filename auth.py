"""
JWT authentication module for BiswaLex/Mastishk.

Self-contained: owns its own SQLite database (auth.db, created next to this
file) for users, refresh tokens, and password-reset OTPs. Does not touch
engine.py's RAG state or any existing chat behavior.

Env vars (all optional, sensible defaults for local/dev use):
  JWT_SECRET            - signing secret for access/refresh tokens.
                          IMPORTANT: set a real random value in production;
                          falls back to a dev-only default otherwise.
  JWT_ACCESS_MINUTES    - access token lifetime in minutes (default 30)
  JWT_REFRESH_DAYS      - refresh token lifetime in days (default 7)
  OTP_TTL_MINUTES       - password-reset OTP lifetime in minutes (default 10)
  SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / SMTP_FROM
                        - if all of these are set, OTP emails are sent for
                          real via SMTP. If not configured, the OTP is
                          printed to the server console instead (dev
                          fallback) so the forgot-password flow is still
                          testable without an email provider.
"""

import os
import re
import sqlite3
import hashlib
import hmac
import secrets
import smtplib
import datetime
from email.mime.text import MIMEText
from contextlib import contextmanager

import jwt  # PyJWT

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth.db")

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-insecure-secret-change-me")
JWT_ALGO = "HS256"
JWT_ACCESS_MINUTES = int(os.environ.get("JWT_ACCESS_MINUTES", "30"))
JWT_REFRESH_DAYS = int(os.environ.get("JWT_REFRESH_DAYS", "7"))
OTP_TTL_MINUTES = int(os.environ.get("OTP_TTL_MINUTES", "10"))

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ============================================================================
# DB SETUP
# ============================================================================

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS password_resets (
                email TEXT PRIMARY KEY,
                otp_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                verified INTEGER NOT NULL DEFAULT 0,
                reset_token TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)


init_db()


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
# USER CRUD
# ============================================================================

def _now():
    return datetime.datetime.utcnow()


def _iso(dt):
    return dt.isoformat()


def get_user_by_email(email: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def signup(name: str, email: str, password: str, confirm_password: str):
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
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, password_hash, salt, _iso(_now())),
        )
        user_id = cur.lastrowid

    return get_user_by_id(user_id)


def login(email: str, password: str):
    email = (email or "").strip().lower()
    user = get_user_by_email(email)
    # Constant-shape error regardless of which part was wrong, so we don't
    # leak whether an email is registered.
    if not user or not _verify_password(password or "", user["password_hash"], user["salt"]):
        raise AuthError("Invalid email or password.")
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
    with get_db() as conn:
        conn.execute(
            "INSERT INTO refresh_tokens (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token, user["id"], _iso(expires_at), _iso(_now())),
        )
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
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM refresh_tokens WHERE token = ?", (refresh_token,)
        ).fetchone()
    if not row:
        raise AuthError("Invalid refresh token.")
    if row["revoked"]:
        raise AuthError("This session has been logged out. Please log in again.")
    if datetime.datetime.fromisoformat(row["expires_at"]) < _now():
        raise AuthError("Session expired. Please log in again.")

    user = get_user_by_id(row["user_id"])
    if not user:
        raise AuthError("Account no longer exists.")

    new_access = create_access_token(user)
    return {
        "access_token": new_access,
        "token_type": "bearer",
        "expires_in": JWT_ACCESS_MINUTES * 60,
    }


def revoke_refresh_token(refresh_token: str):
    with get_db() as conn:
        conn.execute("UPDATE refresh_tokens SET revoked = 1 WHERE token = ?", (refresh_token,))


def revoke_all_refresh_tokens_for_user(user_id: int):
    with get_db() as conn:
        conn.execute("UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?", (user_id,))


# ============================================================================
# FORGOT PASSWORD (email + OTP -> verify -> reset)
# ============================================================================

def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def _send_otp_email(email: str, otp: str):
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    if smtp_host and smtp_port and smtp_user and smtp_pass:
        msg = MIMEText(
            f"Your Mastishk password reset code is: {otp}\n\n"
            f"This code expires in {OTP_TTL_MINUTES} minutes. "
            f"If you didn't request this, you can safely ignore this email."
        )
        msg["Subject"] = "Your Mastishk password reset code"
        msg["From"] = smtp_from
        msg["To"] = email
        try:
            with smtplib.SMTP(smtp_host, int(smtp_port), timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [email], msg.as_string())
            return True
        except Exception as e:
            print(f"[auth] SMTP send failed, falling back to console log: {e}")

    # Dev fallback: no SMTP configured (or it failed) - log so the flow is
    # still testable locally without an email provider set up.
    print(f"[auth] (DEV) Password reset OTP for {email}: {otp}")
    return False


def request_password_reset(email: str):
    email = (email or "").strip().lower()
    if not email or not EMAIL_PATTERN.match(email):
        raise AuthError("A valid email is required.")

    user = get_user_by_email(email)
    otp = _generate_otp()
    expires_at = _now() + datetime.timedelta(minutes=OTP_TTL_MINUTES)

    # Always write/overwrite a reset row and "send" an OTP even if the user
    # doesn't exist, so this endpoint doesn't leak which emails are
    # registered. (verify/reset below still correctly no-ops for unknown
    # accounts.)
    with get_db() as conn:
        conn.execute(
            """INSERT INTO password_resets (email, otp_hash, expires_at, verified, reset_token, attempts, created_at)
               VALUES (?, ?, ?, 0, NULL, 0, ?)
               ON CONFLICT(email) DO UPDATE SET
                 otp_hash=excluded.otp_hash, expires_at=excluded.expires_at,
                 verified=0, reset_token=NULL, attempts=0, created_at=excluded.created_at""",
            (email, _hash_otp(otp), _iso(expires_at), _iso(_now())),
        )

    if user:
        email_sent = _send_otp_email(email, otp)
    else:
        email_sent = False

    return {"message": "If an account exists for this email, a reset code has been sent.",
            "email_sent": email_sent}


MAX_OTP_ATTEMPTS = 5


def verify_otp(email: str, otp: str) -> str:
    """Returns a short-lived reset_token to be used with reset_password."""
    email = (email or "").strip().lower()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM password_resets WHERE email = ?", (email,)).fetchone()

    if not row:
        raise AuthError("No password reset was requested for this email.")
    if row["attempts"] >= MAX_OTP_ATTEMPTS:
        raise AuthError("Too many incorrect attempts. Please request a new code.")
    if datetime.datetime.fromisoformat(row["expires_at"]) < _now():
        raise AuthError("This code has expired. Please request a new one.")

    if not hmac.compare_digest(_hash_otp((otp or "").strip()), row["otp_hash"]):
        with get_db() as conn:
            conn.execute("UPDATE password_resets SET attempts = attempts + 1 WHERE email = ?", (email,))
        raise AuthError("Incorrect code.")

    reset_token = secrets.token_urlsafe(32)
    with get_db() as conn:
        conn.execute(
            "UPDATE password_resets SET verified = 1, reset_token = ? WHERE email = ?",
            (reset_token, email),
        )
    return reset_token


def reset_password(email: str, reset_token: str, new_password: str, confirm_password: str):
    email = (email or "").strip().lower()
    if new_password != confirm_password:
        raise AuthError("Passwords do not match.")
    validate_password_strength(new_password)

    with get_db() as conn:
        row = conn.execute("SELECT * FROM password_resets WHERE email = ?", (email,)).fetchone()

    if not row or not row["verified"] or not row["reset_token"]:
        raise AuthError("Please verify your reset code first.")
    if datetime.datetime.fromisoformat(row["expires_at"]) < _now():
        raise AuthError("This reset session has expired. Please start over.")
    if not hmac.compare_digest(reset_token or "", row["reset_token"]):
        raise AuthError("Invalid or expired reset session.")

    user = get_user_by_email(email)
    if not user:
        raise AuthError("Account not found.")

    password_hash, salt = _hash_password(new_password)
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
            (password_hash, salt, user["id"]),
        )
        # One-time use: clear the reset row so the same OTP/token can't be
        # replayed, and log out any existing sessions for safety.
        conn.execute("DELETE FROM password_resets WHERE email = ?", (email,))

    revoke_all_refresh_tokens_for_user(user["id"])
    return {"message": "Password reset successfully. Please log in with your new password."}
