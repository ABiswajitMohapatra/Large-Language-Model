"""
SQLAlchemy persistence layer for BiswaLex/Mastishk.

Replaces the old per-module SQLite files (auth.db) with a single Postgres
(Supabase) database, connected via the DATABASE_URL environment variable.

Tables (all created automatically on startup via init_db(), no manual SQL
or migration tool needed):
  users            - one row per account (email unique, password hash)
  refresh_tokens   - JWT refresh tokens, FK -> users, cascade delete
  password_resets  - forgot-password OTP state, keyed by email
  chat_sessions    - one row per chat/conversation, FK -> users, cascade
  messages         - one row per chat message, FK -> chat_sessions, cascade

All timestamps are stored in UTC (timezone-aware DateTime columns).

If DATABASE_URL is missing, import of this module raises a RuntimeError
with a clear message instead of silently falling back to local storage -
by design, per deployment requirements.
"""

import os
import sys
import json
import datetime
import contextlib

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, Boolean,
    ForeignKey, UniqueConstraint, Index, func, select,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, scoped_session

# ----------------------------------------------------------------------
# Connection setup
# ----------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print(
        "[db] FATAL: DATABASE_URL environment variable is not set. "
        "This application requires a Postgres (Supabase) connection string "
        "and will NOT silently fall back to local/SQLite storage. "
        "Set DATABASE_URL (e.g. from your Supabase project's connection "
        "string) in your environment / Space secrets and restart.",
        file=sys.stderr,
        flush=True,
    )
    raise RuntimeError(
        "DATABASE_URL is not set. Refusing to start without a configured "
        "Postgres database. See stderr log above for details."
    )

# Supabase/Heroku-style URLs sometimes use the legacy "postgres://" scheme,
# which SQLAlchemy's psycopg2 dialect no longer accepts directly.
_normalized_url = DATABASE_URL
if _normalized_url.startswith("postgres://"):
    _normalized_url = _normalized_url.replace("postgres://", "postgresql://", 1)
if _normalized_url.startswith("postgresql://") and "+psycopg2" not in _normalized_url:
    _normalized_url = _normalized_url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(
    _normalized_url,
    pool_pre_ping=True,   # avoids stale-connection errors after idle periods
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
    future=True,
)

if engine.dialect.name == "sqlite":
    # SQLite doesn't enforce FK constraints (and thus ON DELETE CASCADE)
    # unless explicitly turned on per-connection. Postgres/Supabase always
    # enforces FKs, so this only matters for local/dev testing against
    # sqlite - harmless no-op in production.
    from sqlalchemy import event as _sa_event

    @_sa_event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

# scoped_session -> thread-safe: each thread gets its own Session bound to
# the same engine/connection pool, which is what we want for FastAPI's
# threadpool-executed sync endpoints plus our background-thread email jobs.
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))

Base = declarative_base()


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(320), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    salt = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    chat_sessions = relationship(
        "ChatSession", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    token = Column(String(255), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    user = relationship("User", back_populates="refresh_tokens")


class PasswordReset(Base):
    __tablename__ = "password_resets"

    email = Column(String(320), primary_key=True)
    otp_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified = Column(Boolean, nullable=False, default=False)
    reset_token = Column(String(255), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False, default="New chat")
    pinned = Column(Boolean, nullable=False, default=False)
    archived = Column(Boolean, nullable=False, default=False)
    deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    folder_id = Column(String(64), nullable=True)
    parent_id = Column(Integer, nullable=True)
    tags = Column(Text, nullable=False, default="[]")  # JSON-encoded list of strings
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan", passive_deletes=True,
        order_by="Message.id",
    )

    __table_args__ = (
        Index("ix_chat_sessions_user_updated", "user_id", "updated_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False)          # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    model = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_session_created", "session_id", "created_at"),
    )


# ----------------------------------------------------------------------
# Setup / session helpers
# ----------------------------------------------------------------------

def init_db():
    """Creates all tables if they don't already exist. No manual SQL /
    migration tool required - safe to call on every startup."""
    Base.metadata.create_all(bind=engine)
    _migrate_missing_columns()


def _migrate_missing_columns():
    """create_all() only creates tables that don't exist yet - it never
    ALTERs an existing table to add a newly-defined column. Since
    chat_sessions already existed in production before pinned/archived/
    deleted/folder_id/parent_id/tags were added to the model, this adds
    any columns that are missing so old deployments don't crash with
    'column ... does not exist'. Safe/idempotent to run on every startup."""
    from sqlalchemy import inspect as _sa_inspect, text as _sa_text

    inspector = _sa_inspect(engine)
    if "chat_sessions" not in inspector.get_table_names():
        return
    existing_cols = {c["name"] for c in inspector.get_columns("chat_sessions")}

    is_sqlite = engine.dialect.name == "sqlite"
    bool_type = "BOOLEAN" if not is_sqlite else "INTEGER"
    statements = {
        "pinned": f"ALTER TABLE chat_sessions ADD COLUMN pinned {bool_type} NOT NULL DEFAULT 0" if is_sqlite
                  else "ALTER TABLE chat_sessions ADD COLUMN pinned BOOLEAN NOT NULL DEFAULT false",
        "archived": f"ALTER TABLE chat_sessions ADD COLUMN archived {bool_type} NOT NULL DEFAULT 0" if is_sqlite
                    else "ALTER TABLE chat_sessions ADD COLUMN archived BOOLEAN NOT NULL DEFAULT false",
        "deleted": f"ALTER TABLE chat_sessions ADD COLUMN deleted {bool_type} NOT NULL DEFAULT 0" if is_sqlite
                   else "ALTER TABLE chat_sessions ADD COLUMN deleted BOOLEAN NOT NULL DEFAULT false",
        "deleted_at": "ALTER TABLE chat_sessions ADD COLUMN deleted_at TIMESTAMP" if is_sqlite
                      else "ALTER TABLE chat_sessions ADD COLUMN deleted_at TIMESTAMPTZ",
        "folder_id": "ALTER TABLE chat_sessions ADD COLUMN folder_id VARCHAR(64)",
        "parent_id": "ALTER TABLE chat_sessions ADD COLUMN parent_id INTEGER",
        "tags": "ALTER TABLE chat_sessions ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'",
    }
    missing = [col for col in statements if col not in existing_cols]
    if not missing:
        return
    with engine.begin() as conn:
        for col in missing:
            try:
                conn.execute(_sa_text(statements[col]))
            except Exception as e:
                print(f"[db] migration warning: could not add column '{col}': {e}")


@contextlib.contextmanager
def get_db():
    """Context-manager session, mirroring the old sqlite3 get_db() shape
    used throughout auth.py: commits on success, rolls back on error,
    always removes the scoped session afterwards."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        SessionLocal.remove()


def _test_connection():
    """Runs a trivial query to confirm the DB is actually reachable, used
    once at startup for a clear pass/fail log line."""
    with engine.connect() as conn:
        conn.execute(select(func.now()))


# ----------------------------------------------------------------------
# Chat session / message helpers - all scoped by user_id so one user can
# never see or touch another user's chats. Used by the new, additive
# /chat-sessions endpoints in main.py.
# ----------------------------------------------------------------------

def _session_to_dict(s) -> dict:
    try:
        tags = json.loads(s.tags) if s.tags else []
    except (TypeError, ValueError):
        tags = []
    return {
        "id": s.id,
        "user_id": s.user_id,
        "title": s.title,
        "pinned": bool(s.pinned),
        "archived": bool(s.archived),
        "deleted": bool(s.deleted),
        "deleted_at": s.deleted_at.isoformat() if s.deleted_at else None,
        "folder_id": s.folder_id,
        "parent_id": s.parent_id,
        "tags": tags,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _message_to_dict(m) -> dict:
    return {
        "id": m.id,
        "session_id": m.session_id,
        "role": m.role,
        "content": m.content,
        "model": m.model,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def create_chat_session(user_id: int, title: str = "New chat", parent_id: int = None) -> dict:
    with get_db() as session:
        cs = ChatSession(user_id=user_id, title=(title or "New chat")[:500], parent_id=parent_id)
        session.add(cs)
        session.flush()
        result = _session_to_dict(cs)
    return result


_ALLOWED_META_FIELDS = {"title", "pinned", "archived", "deleted", "folder_id", "tags"}


def update_chat_session_meta(session_id: int, user_id: int, **fields) -> dict:
    """Partial update of a session's metadata (title/pinned/archived/deleted/
    folder_id/tags), scoped to the owning user. Returns the updated dict, or
    None if the session doesn't exist / isn't owned by user_id."""
    with get_db() as session:
        cs = (
            session.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )
        if not cs:
            return None
        for key, value in fields.items():
            if key not in _ALLOWED_META_FIELDS or value is None:
                continue
            if key == "title":
                cs.title = (value or "New chat")[:500]
            elif key == "tags":
                cs.tags = json.dumps(value if isinstance(value, list) else [])
            elif key == "deleted":
                cs.deleted = bool(value)
                cs.deleted_at = _utcnow() if value else None
            else:
                setattr(cs, key, value)
        cs.updated_at = _utcnow()
        session.flush()
        result = _session_to_dict(cs)
    return result


def list_chat_sessions(user_id: int) -> list:
    with get_db() as session:
        rows = (
            session.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )
        return [_session_to_dict(r) for r in rows]


def get_chat_session(session_id: int, user_id: int):
    with get_db() as session:
        cs = (
            session.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )
        return _session_to_dict(cs) if cs else None


def rename_chat_session(session_id: int, user_id: int, title: str) -> bool:
    with get_db() as session:
        cs = (
            session.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )
        if not cs:
            return False
        cs.title = (title or "New chat")[:500]
        cs.updated_at = _utcnow()
        return True


def delete_chat_session(session_id: int, user_id: int) -> bool:
    with get_db() as session:
        cs = (
            session.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )
        if not cs:
            return False
        session.delete(cs)  # cascades to messages
        return True


def add_message(session_id: int, user_id: int, role: str, content: str, model: str = None):
    """Adds a message to a session, but only if that session belongs to
    user_id - enforces per-user isolation at the write path too."""
    with get_db() as session:
        cs = (
            session.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )
        if not cs:
            return None
        msg = Message(session_id=session_id, role=role, content=content, model=model)
        session.add(msg)
        cs.updated_at = _utcnow()
        session.flush()
        result = _message_to_dict(msg)
    return result


def get_messages(session_id: int, user_id: int):
    """Returns None if the session doesn't belong to user_id (so callers
    can 404/403 instead of leaking other users' messages)."""
    with get_db() as session:
        cs = (
            session.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )
        if not cs:
            return None
        rows = (
            session.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .all()
        )
        return [_message_to_dict(m) for m in rows]