"""
Chat-session/message persistence endpoints.

This is the missing wiring: db.py already defines create_chat_session,
list_chat_sessions, get_messages, add_message, etc. (all correctly scoped
by user_id), but nothing exposed them over HTTP, so the frontend had no way
to read/write conversations from Postgres and fell back to browser-only
localStorage - which is why conversations "disappeared" across logins/
devices. This router is the fix; every route requires a valid access token
and every db.py call is scoped to that token's user_id, so one user can
never read/write another user's conversations.

Wire into your existing FastAPI app with:

    from chat_routes import chat_router
    app.include_router(chat_router)
"""

import jwt
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List

import auth
import db

chat_router = APIRouter(prefix="/chat-sessions", tags=["chat-sessions"])


# ----------------------------------------------------------------------
# Auth dependency - identical semantics to whatever main.py's /chat route
# already uses (Bearer access token -> decoded -> current user), pulled out
# here so this router doesn't depend on main.py's internals.
# ----------------------------------------------------------------------

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = auth.decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid access token.")

    user = auth.get_user_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists.")
    return user


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------

class CreateSessionBody(BaseModel):
    title: Optional[str] = "New chat"
    parent_id: Optional[int] = None


class UpdateSessionBody(BaseModel):
    title: Optional[str] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None
    deleted: Optional[bool] = None
    folder_id: Optional[str] = None
    tags: Optional[List[str]] = None


class AddMessageBody(BaseModel):
    role: str
    content: str
    model: Optional[str] = None


class BulkMessage(BaseModel):
    role: str
    content: str
    model: Optional[str] = None


class BulkMessagesBody(BaseModel):
    messages: List[BulkMessage]


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------

@chat_router.get("")
def list_sessions(user: dict = Depends(get_current_user)):
    """All conversations for the authenticated user - this is what the
    frontend calls right after login/signup/session-restore to populate
    the sidebar, and it is the only source of truth for that list."""
    return db.list_chat_sessions(user["id"])


@chat_router.post("")
def create_session(body: CreateSessionBody, user: dict = Depends(get_current_user)):
    return db.create_chat_session(user["id"], title=body.title, parent_id=body.parent_id)


@chat_router.get("/{session_id}")
def get_session(session_id: int, user: dict = Depends(get_current_user)):
    cs = db.get_chat_session(session_id, user["id"])
    if not cs:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return cs


@chat_router.patch("/{session_id}")
def update_session(session_id: int, body: UpdateSessionBody, user: dict = Depends(get_current_user)):
    fields = body.dict(exclude_unset=True)
    updated = db.update_chat_session_meta(session_id, user["id"], **fields)
    if not updated:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return updated


@chat_router.delete("/{session_id}")
def delete_session(session_id: int, user: dict = Depends(get_current_user)):
    """Hard delete (used for 'permanently delete' / empty trash). Soft
    delete (move to trash) should use PATCH with {"deleted": true} instead."""
    ok = db.delete_chat_session(session_id, user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"ok": True}


@chat_router.get("/{session_id}/messages")
def list_messages(session_id: int, user: dict = Depends(get_current_user)):
    msgs = db.get_messages(session_id, user["id"])
    if msgs is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return msgs


@chat_router.post("/{session_id}/messages")
def post_message(session_id: int, body: AddMessageBody, user: dict = Depends(get_current_user)):
    msg = db.add_message(session_id, user["id"], body.role, body.content, model=body.model)
    if msg is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return msg


@chat_router.post("/{session_id}/messages/bulk")
def post_messages_bulk(session_id: int, body: BulkMessagesBody, user: dict = Depends(get_current_user)):
    """Used for branch/fork: writes several messages to a session in one
    call (e.g. copying a branched history into its new session)."""
    saved = []
    for m in body.messages:
        msg = db.add_message(session_id, user["id"], m.role, m.content, model=m.model)
        if msg is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        saved.append(msg)
    return saved
