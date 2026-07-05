import os
import json
import io
from typing import List
from fastapi import FastAPI, UploadFile, File
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
# Tracks the most recently uploaded filename, so generic references like
# "this pdf" / "the attached document" resolve to it (same behavior as
# ChatGPT/Claude/Gemini) instead of guessing across everything ever uploaded.
last_uploaded_filename = None


class Message(BaseModel):
    role: str
    message: str


class ChatRequest(BaseModel):
    query: str
    history: List[Message] = []
    model: str = None


@app.get("/")
def health():
    return {
        "status": "ok",
        "model": engine.CHAT_MODEL
    }


@app.get("/rag-status")
def rag_status():
    """
    Debug endpoint: shows exactly what the folder-based RAG index sees right
    now, so you can confirm whether it's picking up your `documents` folder
    at all without needing to dig through container logs.
    """
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
        model=req.model,
    )

    def event_stream():
        meta = {
            "type": "meta",
            "doc_sources": doc_sources,
            "web_used": web_used,
            "uploaded_docs": list(uploaded_documents.keys())
        }
        yield f"data: {json.dumps(meta)}\n\n"
        for chunk in generator:
            payload = {
                "type": "chunk",
                "text": chunk
            }
            yield f"data: {json.dumps(payload)}\n\n"
        yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    global last_uploaded_filename
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
    # Documents accumulate (multi-document support) rather than replacing
    # each other. Ambiguous references like "this pdf" are resolved to
    # last_uploaded_filename in engine.py, while questions naming an older
    # file by name (e.g. "in my resume") still work correctly.
    uploaded_documents[file.filename] = text
    last_uploaded_filename = file.filename
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
        # fall back to whatever's left, most-recently-added last in dict order
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
