import asyncio
import io
import json
import os
import secrets
from concurrent.futures import ThreadPoolExecutor

import jwt as _pyjwt
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import auth
import chat_routes
import db
import engine
import rag_store

app = FastAPI(title="Mastishk API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_routes.chat_router)

# Bounded pool dedicated to the (blocking, CPU-bound) text-extraction step
# of /upload - kept separate from Starlette's default threadpool (which
# handles all the sync `def` routes like /chat, /auth/*) so a burst of
# uploads can't starve request-handling capacity for everyone else.
_extraction_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="upload-extract")


@app.on_event("startup")
def _preload_models():
    """
    Load the embedding model (and warm the base folder index) once at
    boot instead of on whatever request happens to hit them first. Before
    this, the FIRST /chat or /upload after a cold start paid the full
    model-download/load cost inline, which looked exactly like the same
    "everything is slow" symptom this whole pass is meant to fix, just
    from a different cause. rag_store's own module-level FAISS/BM25 load
    already runs at import time (see rag_store.py's `_load()`/
    `_rebuild_bm25()` calls), so it needs no extra wiring here.
    """
    engine.get_embedder()
    engine.get_base_index()
    print("[STARTUP] Embedding model and base index preloaded.")


# ============================================================================
# AUTH DEPENDENCY - validates the "Authorization: Bearer <access_token>"
# header on protected routes. auto_error=False so we can return our own
# consistent {"detail": "..."} 401 JSON shape instead of FastAPI's default.
# ============================================================================
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer_scheme)):
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Not authenticated. Please log in.")
    try:
        payload = auth.decode_access_token(creds.credentials)
    except _pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Session expired. Please log in again.")
    except _pyjwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Invalid authentication token.")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Invalid token type.")
    return {"id": int(payload["sub"]), "email": payload.get("email"), "name": payload.get("name")}

# Store uploaded documents in memory: {filename: extracted_text}
uploaded_documents = {}
last_uploaded_filename = None
# Shared-chat links: backed by db.py's SharedChat table (Postgres), same
# durable storage as chat sessions/messages - see db.create_shared_chat()/
# db.get_shared_chat(). Was an in-memory dict before, which meant every
# link died silently on the next restart/redeploy.
# Tracks files uploaded together in one multi-select action, so the chat
# endpoint can default to using ALL of them (not just the single most
# recent file) when the user attaches several files at once. Purely
# additive: a normal single-file upload (no batch_id) behaves exactly as
# before, only setting last_uploaded_filename.
last_uploaded_batch = []
_current_batch_id = None


class Message(BaseModel):
    role: str
    message: str


class ChatRequest(BaseModel):
    query: str
    history: list[Message] = []
    model: str = None
    research_mode: bool = False
    persona_prompt: str = None
    # Optional cross-chat memory facts (short bullet list as one string),
    # supplied by the frontend from its local memory store. Additive/opt-in:
    # omitting it (as all existing clients do) leaves behavior unchanged.
    memory_context: str = None


class WebSearchQuickRequest(BaseModel):
    query: str


class FollowupsRequest(BaseModel):
    query: str
    answer: str
    model: str = None


class QuickTaskRequest(BaseModel):
    text: str
    task: str
    target_language: str = None
    model: str = None


class CanvasEditRequest(BaseModel):
    text: str
    instruction: str
    model: str = None


class AnalyzeRequest(BaseModel):
    history: list[Message] = []
    model: str = None


class TitleRequest(BaseModel):
    history: list[Message] = []
    model: str = None


class SlideRequest(BaseModel):
    topic: str
    slides: int = 8
    template: str = "business"
    model: str = None


class PluginExecuteRequest(BaseModel):
    plugin_name: str
    query: str
    url: str = None
    method: str = "GET"
    headers_json: str = None


class MemoryExtractRequest(BaseModel):
    history: list[Message] = []
    model: str = None


class VerifyRequest(BaseModel):
    query: str
    answer: str
    model: str = None


class BackgroundTaskRequest(BaseModel):
    query: str
    model: str = None
    persona_prompt: str = None


class ShareCreateRequest(BaseModel):
    title: str = "Shared chat"
    messages: list[Message] = []


# ---------------------------------------------------------------------------
# Auth request models
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str


class ResetPasswordRequest(BaseModel):
    email: str
    reset_token: str
    new_password: str
    confirm_password: str


class FeedbackRequest(BaseModel):
    message: str
    user_name: str = ""
    user_email: str = ""
    admin_email: str = ""


@app.get("/")
def health():
    return {
        "status": "ok",
        "model": engine.CHAT_MODEL
    }


# ============================================================================
# AUTH ROUTES - all public (no login required to reach them, obviously).
# Each catches auth.AuthError and returns it as a 400 with a clean message
# so the frontend can show it directly without extra mapping.
# ============================================================================

@app.post("/auth/signup")
def auth_signup(req: SignupRequest):
    try:
        user = auth.signup(req.name, req.email, req.password, req.confirm_password)
    except auth.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    tokens = auth.issue_token_pair(user)
    return tokens


@app.post("/auth/login")
def auth_login(req: LoginRequest):
    try:
        user = auth.login(req.email, req.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    tokens = auth.issue_token_pair(user)
    return tokens


@app.post("/auth/refresh")
def auth_refresh(req: RefreshRequest):
    try:
        result = auth.refresh_access_token(req.refresh_token)
    except auth.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return result


@app.post("/auth/logout")
def auth_logout(req: LogoutRequest):
    auth.revoke_refresh_token(req.refresh_token)
    return {"message": "Logged out."}


@app.get("/auth/me")
def auth_me(user=Depends(get_current_user)):
    return {"user": user}


@app.post("/auth/forgot-password")
def auth_forgot_password(req: ForgotPasswordRequest):
    try:
        result = auth.request_password_reset(req.email)
    except auth.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.post("/auth/verify-otp")
def auth_verify_otp(req: VerifyOtpRequest):
    try:
        reset_token = auth.verify_otp(req.email, req.otp)
    except auth.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"reset_token": reset_token}


@app.post("/auth/reset-password")
def auth_reset_password(req: ResetPasswordRequest):
    try:
        result = auth.reset_password(req.email, req.reset_token, req.new_password, req.confirm_password)
    except auth.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Feedback message is required.")
    to_email = req.admin_email or auth.ADMIN_NOTIFY_EMAIL
    if not to_email:
        raise HTTPException(status_code=500, detail="Admin notification email is not configured.")
    body = (
        f"From: {req.user_name or 'Unknown'} ({req.user_email or 'no email'})\n\n"
        f"{req.message}"
    )
    sent = auth._send_email(to_email, "New User Feedback - Mastishk", body)
    return {"message": "Feedback submitted.", "email_sent": sent}


@app.get("/rag-status")
def rag_status():
    index = engine.get_base_index()
    return {
        "documents_folder_path": engine.DOCS_FOLDER,
        "folder_exists": os.path.isdir(engine.DOCS_FOLDER),
        "files_in_folder": os.listdir(engine.DOCS_FOLDER) if os.path.isdir(engine.DOCS_FOLDER) else [],
        "chunks_indexed": len(index["chunks"]),
        "sources_indexed": sorted(set(index["sources"])),
        "uploaded_documents": list(uploaded_documents.keys()),
        "last_uploaded": last_uploaded_filename,
    }


@app.get("/models")
def list_models():
    return {
        "default": engine.CHAT_MODEL,
        "models": [
            {"id": model_id, "label": label}
            for model_id, label in engine.AVAILABLE_MODELS.items()
        ]
    }


@app.post("/chat")
def chat(req: ChatRequest, user=Depends(get_current_user)):
    if req.research_mode:
        generator, sources = engine.research_report_stream(req.query, model=req.model)

        def research_stream():
            meta = {
                "type": "meta",
                "doc_sources": [],
                "web_used": True,
                "uploaded_docs": list(uploaded_documents.keys()),
                "research_sources": sources,
            }
            yield f"data: {json.dumps(meta)}\n\n"
            for chunk in generator:
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
            yield 'data: {"type":"done"}\n\n'

        return StreamingResponse(research_stream(), media_type="text/event-stream")

    index = engine.get_base_index()
    history = [
        {
            "role": m.role,
            "message": m.message
        }
        for m in req.history
    ]
    generator, doc_sources, web_used, _citations = engine.chat_with_agent_stream(
        req.query,
        index,
        history,
        uploaded_docs=uploaded_documents,
        last_uploaded=last_uploaded_filename,
        last_uploaded_batch=last_uploaded_batch,
        model=req.model,
        persona_prompt=req.persona_prompt,
        memory_context=req.memory_context,
    )

    def event_stream():
        meta = {
            "type": "meta",
            "doc_sources": doc_sources,
            "web_used": web_used,
            "uploaded_docs": list(uploaded_documents.keys())
        }
        yield f"data: {json.dumps(meta)}\n\n"
        full_text_parts = []
        for chunk in generator:
            full_text_parts.append(chunk)
            payload = {
                "type": "chunk",
                "text": chunk
            }
            yield f"data: {json.dumps(payload)}\n\n"
        # Token/cost transparency (additive, estimate-based - see
        # engine.estimate_tokens): frontend can ignore this event type and
        # nothing else about the stream changes.
        history_text = " ".join(m.message for m in req.history)
        prompt_tokens_est = engine.estimate_tokens(req.query + " " + history_text)
        completion_tokens_est = engine.estimate_tokens("".join(full_text_parts))
        usage_payload = {
            "type": "usage",
            "prompt_tokens_est": prompt_tokens_est,
            "completion_tokens_est": completion_tokens_est,
            "total_tokens_est": prompt_tokens_est + completion_tokens_est,
        }
        yield f"data: {json.dumps(usage_payload)}\n\n"
        yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )


@app.post("/quick-task")
def quick_task(req: QuickTaskRequest, user=Depends(get_current_user)):
    result = engine.quick_task(
        req.text,
        req.task,
        target_language=req.target_language,
        model=req.model,
    )
    return {"result": result, "task": req.task}


@app.post("/canvas-edit")
def canvas_edit(req: CanvasEditRequest, user=Depends(get_current_user)):
    prompt = (
        "Apply this instruction to the text and return ONLY the edited "
        "text, no preamble, no explanation, no markdown fences:\n"
        f"Instruction: {req.instruction}\n\nText:\n{req.text}"
    )
    result = engine.quick_task(prompt, "improve", model=req.model)
    return {"result": result}


@app.post("/analyze-conversation")
def analyze_conversation(req: AnalyzeRequest, user=Depends(get_current_user)):
    history = [{"role": m.role, "message": m.message} for m in req.history]
    sections = engine.analyze_conversation(history, model=req.model)
    return {"sections": sections}


@app.post("/generate-title")
def generate_title(req: TitleRequest, user=Depends(get_current_user)):
    history = [{"role": m.role, "message": m.message} for m in req.history]
    result = engine.generate_chat_title(history, model=req.model)
    return result


@app.post("/generate-ppt")
def generate_ppt(req: SlideRequest, user=Depends(get_current_user)):
    n_slides = max(3, min(req.slides, 20))
    pptx_bytes = engine.generate_presentation(
        req.topic,
        n_slides=n_slides,
        template=req.template,
        model=req.model,
    )
    safe_name = "".join(c for c in req.topic[:40] if c.isalnum() or c in " -_").strip() or "presentation"
    return StreamingResponse(
        io.BytesIO(pptx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.pptx"'}
    )


@app.post("/web-search-quick")
def web_search_quick(req: WebSearchQuickRequest, user=Depends(get_current_user)):
    raw = engine.web_search(req.query, max_results=5)
    if raw.get("_error"):
        return {"success": False, "message": raw["_error"], "results": []}
    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": (r.get("content", "") or "")[:220],
        }
        for r in raw.get("results", [])
    ]
    return {"success": True, "answer": raw.get("answer", ""), "results": results}


@app.post("/suggest-followups")
def suggest_followups(req: FollowupsRequest, user=Depends(get_current_user)):
    suggestions = engine.generate_followups(req.query, req.answer, model=req.model)
    return {"suggestions": suggestions}


@app.get("/discover-topics")
def discover_topics(user=Depends(get_current_user)):
    """Discover feed: returns curated trending topics/questions daily."""
    topics = engine.discover_topics()
    return {"topics": topics, "refreshed": True}


@app.post("/execute-plugin")
def execute_plugin(req: PluginExecuteRequest, user=Depends(get_current_user)):
    """Plugin execution: user-defined API endpoint callable mid-chat."""
    result = engine.execute_plugin(
        req.plugin_name,
        req.query,
        url=req.url,
        method=req.method,
        headers_json=req.headers_json,
    )
    return {"success": result.get("success", False), "result": result.get("result", ""), "error": result.get("error")}


@app.post("/extract-memory")
def extract_memory(req: MemoryExtractRequest, user=Depends(get_current_user)):
    """
    Persistent cross-chat memory: pulls a few durable facts about the user
    out of a conversation. Read-only, stateless on the backend - the
    frontend owns storing/merging/injecting these facts, so this endpoint
    can't affect any existing chat/RAG behavior by itself.
    """
    history = [{"role": m.role, "message": m.message} for m in req.history]
    facts = engine.extract_memory_facts(history, model=req.model)
    return {"facts": facts}


@app.post("/verify-response")
def verify_response(req: VerifyRequest, user=Depends(get_current_user)):
    """
    Fact-check / self-correction pass: user-triggered re-review of an
    already-given answer, returning a confidence score, flagged claims
    (each with a best-effort source link), and an optional corrected
    answer. Never called automatically - only when the user clicks the
    fact-check action - so it cannot slow down or alter normal replies.
    """
    result = engine.verify_response(req.query, req.answer, model=req.model)
    return result


@app.post("/background-task")
def background_task(req: BackgroundTaskRequest, user=Depends(get_current_user)):
    """
    Background agent mode: starts a query running server-side without
    needing the chat stream/tab to stay open, returns a job_id immediately.
    Fully isolated from /chat's session state (uploaded_documents, etc).
    """
    job_id = engine.start_background_task(req.query, model=req.model, persona_prompt=req.persona_prompt)
    return {"job_id": job_id}


@app.get("/background-task/{job_id}")
def background_task_status(job_id: str, user=Depends(get_current_user)):
    job = engine.get_background_task(job_id)
    if job is None:
        return {"status": "not_found"}
    return job


@app.post("/upload")
async def upload(file: UploadFile = File(...), batch_id: str = Form(None), user=Depends(get_current_user)):
    global last_uploaded_filename, last_uploaded_batch, _current_batch_id
    contents = await file.read()
    try:
        # engine.load_file() does synchronous, CPU-bound work (pdfplumber
        # parsing, and OCR for scanned PDFs) - running it directly inside
        # this `async def` would block the entire event loop for the
        # whole extraction, freezing every other concurrent request
        # (chat, auth, everything) until it finished. Offloading to the
        # dedicated extraction pool (not Starlette's shared default
        # threadpool, which also runs every sync `def` route like /chat
        # and /auth/*) is the fix; nothing about the return value or
        # error handling below changes.
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(_extraction_executor, engine.load_file, io.BytesIO(contents), file.filename)
    except engine.UnsupportedFileError as e:
        return {
            "success": False,
            "filename": file.filename,
            "message": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "filename": file.filename,
            "message": f"Failed to process file: {e}"
        }
    if not text.strip():
        return {
            "success": False,
            "filename": file.filename,
            "message": "No text could be extracted."
        }
    uploaded_documents[file.filename] = text
    last_uploaded_filename = file.filename
    if batch_id:
        if batch_id != _current_batch_id:
            _current_batch_id = batch_id
            last_uploaded_batch = []
        last_uploaded_batch.append(file.filename)
    else:
        _current_batch_id = None
        last_uploaded_batch = [file.filename]

    # Kick off page-aware chunking + embedding + FAISS/BM25 indexing in
    # the background so this response isn't held up by it (this is the
    # FAISS/BM25/citations pipeline build_prompt() already expects to be
    # able to query via rag_store.list_indexed()/hybrid_search()/
    # get_chunks_by_page() - it was previously never triggered anywhere,
    # so uploaded files never actually made it into the vector store).
    # Runs on rag_store's own bounded worker pool, not a per-upload thread,
    # so many simultaneous uploads queue safely. Status is pollable via
    # GET /upload-status/{filename}; the response shape below is unchanged.
    rag_store.index_document_background(file.filename, contents)

    return {
        "success": True,
        "filename": file.filename,
        "characters": len(text),
        "documents_loaded": len(uploaded_documents),
        "message": "Document indexed successfully."
    }


@app.get("/upload-status/{filename}")
def upload_status(filename: str, user=Depends(get_current_user)):
    """
    Polling endpoint for background indexing progress (queued/indexing/
    done/error + percent), keyed by filename. Purely additive - doesn't
    change /upload's response shape or timing, so existing frontend flows
    that ignore this endpoint keep working exactly as before.
    """
    return rag_store.get_progress(filename)


@app.delete("/documents/{filename}")
def delete_document(filename: str, user=Depends(get_current_user)):
    global last_uploaded_filename
    if filename not in uploaded_documents:
        return {"success": False, "message": f"'{filename}' not found."}
    del uploaded_documents[filename]
    if last_uploaded_filename == filename:
        last_uploaded_filename = list(uploaded_documents.keys())[-1] if uploaded_documents else None
    return {
        "success": True,
        "message": f"'{filename}' removed.",
        "remaining_documents": list(uploaded_documents.keys())
    }


@app.post("/clear")
def clear_documents(user=Depends(get_current_user)):
    global last_uploaded_filename
    uploaded_documents.clear()
    last_uploaded_filename = None
    return {
        "success": True,
        "message": "All uploaded documents removed."
    }


@app.get("/documents")
def documents(user=Depends(get_current_user)):
    return {
        "count": len(uploaded_documents),
        "documents": list(uploaded_documents.keys()),
        "last_uploaded": last_uploaded_filename,
    }


@app.post("/share")
def create_share(req: ShareCreateRequest, user=Depends(get_current_user)):
    """Creates a short, shareable link for a conversation. Login required
    to create one (same as every other write in this API); the resulting
    id is public/unauthenticated to view (GET below), same as before when
    the payload was embedded directly in the URL."""
    share_id = secrets.token_urlsafe(6)
    db.create_shared_chat(
        share_id,
        req.title,
        [{"role": m.role, "message": m.message} for m in req.messages],
    )
    return {"id": share_id}


@app.get("/share/{share_id}")
def get_share(share_id: str):
    data = db.get_shared_chat(share_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Shared chat not found or expired.")
    return data


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port
    )