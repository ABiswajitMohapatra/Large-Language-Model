import os
import json
import io
from typing import List
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import engine

app = FastAPI(title="BiswaLex API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store uploaded documents in memory: {filename: extracted_text}
uploaded_documents = {}
last_uploaded_filename = None
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
    history: List[Message] = []
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


class AnalyzeRequest(BaseModel):
    history: List[Message] = []
    model: str = None


class TitleRequest(BaseModel):
    history: List[Message] = []
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
    history: List[Message] = []
    model: str = None


class VerifyRequest(BaseModel):
    query: str
    answer: str
    model: str = None


class BackgroundTaskRequest(BaseModel):
    query: str
    model: str = None
    persona_prompt: str = None


@app.get("/")
def health():
    return {
        "status": "ok",
        "model": engine.CHAT_MODEL
    }


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
def chat(req: ChatRequest):
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
    generator, doc_sources, web_used = engine.chat_with_agent_stream(
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
def quick_task(req: QuickTaskRequest):
    result = engine.quick_task(
        req.text,
        req.task,
        target_language=req.target_language,
        model=req.model,
    )
    return {"result": result, "task": req.task}


@app.post("/analyze-conversation")
def analyze_conversation(req: AnalyzeRequest):
    history = [{"role": m.role, "message": m.message} for m in req.history]
    sections = engine.analyze_conversation(history, model=req.model)
    return {"sections": sections}


@app.post("/generate-title")
def generate_title(req: TitleRequest):
    history = [{"role": m.role, "message": m.message} for m in req.history]
    result = engine.generate_chat_title(history, model=req.model)
    return result


@app.post("/generate-ppt")
def generate_ppt(req: SlideRequest):
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
def web_search_quick(req: WebSearchQuickRequest):
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
def suggest_followups(req: FollowupsRequest):
    suggestions = engine.generate_followups(req.query, req.answer, model=req.model)
    return {"suggestions": suggestions}


@app.get("/discover-topics")
def discover_topics():
    """Discover feed: returns curated trending topics/questions daily."""
    topics = engine.discover_topics()
    return {"topics": topics, "refreshed": True}


@app.post("/execute-plugin")
def execute_plugin(req: PluginExecuteRequest):
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
def extract_memory(req: MemoryExtractRequest):
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
def verify_response(req: VerifyRequest):
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
def background_task(req: BackgroundTaskRequest):
    """
    Background agent mode: starts a query running server-side without
    needing the chat stream/tab to stay open, returns a job_id immediately.
    Fully isolated from /chat's session state (uploaded_documents, etc).
    """
    job_id = engine.start_background_task(req.query, model=req.model, persona_prompt=req.persona_prompt)
    return {"job_id": job_id}


@app.get("/background-task/{job_id}")
def background_task_status(job_id: str):
    job = engine.get_background_task(job_id)
    if job is None:
        return {"status": "not_found"}
    return job


@app.post("/upload")
async def upload(file: UploadFile = File(...), batch_id: str = Form(None)):
    global last_uploaded_filename, last_uploaded_batch, _current_batch_id
    contents = await file.read()
    text = engine.load_file(
        io.BytesIO(contents),
        file.filename
    )
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
    return {
        "success": True,
        "filename": file.filename,
        "characters": len(text),
        "documents_loaded": len(uploaded_documents),
        "message": "Document indexed successfully."
    }


@app.delete("/documents/{filename}")
def delete_document(filename: str):
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
def clear_documents():
    global last_uploaded_filename
    uploaded_documents.clear()
    last_uploaded_filename = None
    return {
        "success": True,
        "message": "All uploaded documents removed."
    }


@app.get("/documents")
def documents():
    return {
        "count": len(uploaded_documents),
        "documents": list(uploaded_documents.keys()),
        "last_uploaded": last_uploaded_filename,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port
    )