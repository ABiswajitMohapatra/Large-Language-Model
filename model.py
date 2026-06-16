"""
Core logic for the chatbot:
- Loads documents (PDF / DOCX / TXT / images) and turns them into a searchable index
  using FREE local embeddings (fastembed) - no embedding API key needed.
- Talks to Groq for the actual chat completion. Uses Groq's built-in `groq/compound`
  model, which automatically performs live web search server-side whenever a question
  needs current/up-to-date information - no separate search API key required.
"""

import os
import re
import glob
import numpy as np
import streamlit as st
from groq import Groq
from fastembed import TextEmbedding
import pdfplumber
from PIL import Image
import pytesseract
from dotenv import load_dotenv

try:
    import docx  # python-docx, optional
except ImportError:
    docx = None

load_dotenv()  # allows a local .env file to work when running on your own machine

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

CHAT_MODEL = "groq/compound"          # built-in, automatic web search when needed
SUMMARY_MODEL = "llama-3.3-70b-versatile"  # cheaper/faster, used only for summarizing history
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384

DOCS_FOLDER = "documents"  # put PDFs / DOCX / TXT / MD files here for the bot to learn from
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K = 4
MIN_SIMILARITY = 0.2


def get_secret(key: str, default=None):
    """Read a secret from Streamlit's secrets manager first (for Streamlit Cloud),
    falling back to environment variables / .env (for local development)."""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


GROQ_API_KEY = get_secret("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


# ----------------------------------------------------------------------------
# Embeddings (loaded once, cached)
# ----------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_embedder():
    return TextEmbedding(model_name=EMBED_MODEL_NAME)


def embed_texts(texts):
    if not texts:
        return np.zeros((0, EMBED_DIM))
    return np.array(list(get_embedder().embed(texts)))


# ----------------------------------------------------------------------------
# Text extraction
# ----------------------------------------------------------------------------

def extract_text_from_pdf(file) -> str:
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    return text.strip()


def extract_text_from_docx(file) -> str:
    if docx is None:
        return ""
    document = docx.Document(file)
    return "\n".join(p.text for p in document.paragraphs)


def extract_text_from_image(file) -> str:
    try:
        image = Image.open(file)
        return pytesseract.image_to_string(image)
    except Exception:
        # tesseract not installed / unreadable image - fail soft, don't crash the app
        return ""


def extract_text_from_txt(file) -> str:
    if hasattr(file, "read"):
        raw = file.read()
        return raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else raw
    with open(file, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def load_file(path_or_buffer, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        return extract_text_from_pdf(path_or_buffer)
    if ext == "docx":
        return extract_text_from_docx(path_or_buffer)
    if ext in ("txt", "md"):
        return extract_text_from_txt(path_or_buffer)
    if ext in ("png", "jpg", "jpeg"):
        return extract_text_from_image(path_or_buffer)
    return ""


def load_folder_documents(folder: str = DOCS_FOLDER):
    """Read every supported file under `folder` -> list of (filename, text)."""
    docs = []
    if not os.path.isdir(folder):
        return docs
    for path in glob.glob(os.path.join(folder, "**", "*"), recursive=True):
        if os.path.isfile(path):
            filename = os.path.basename(path)
            try:
                with open(path, "rb") as f:
                    text = load_file(f, filename)
            except Exception:
                text = ""
            if text.strip():
                docs.append((filename, text))
    return docs


# ----------------------------------------------------------------------------
# Chunking + simple in-memory vector index
# ----------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c for c in chunks if c.strip()]


def empty_index():
    return {"chunks": [], "sources": [], "embeddings": np.zeros((0, EMBED_DIM))}


def build_index(documents):
    """documents: list of (source_name, text) -> index dict."""
    chunks, sources = [], []
    for source, text in documents:
        for chunk in chunk_text(text):
            chunks.append(chunk)
            sources.append(source)
    if not chunks:
        return empty_index()
    return {"chunks": chunks, "sources": sources, "embeddings": embed_texts(chunks)}


def add_to_index(index, source_name: str, text: str):
    """Return a NEW index dict with `text` added (does not mutate the original)."""
    new_chunks = chunk_text(text)
    if not new_chunks:
        return index
    new_vectors = embed_texts(new_chunks)
    merged_embeddings = (
        new_vectors if index["embeddings"].shape[0] == 0
        else np.vstack([index["embeddings"], new_vectors])
    )
    return {
        "chunks": index["chunks"] + new_chunks,
        "sources": index["sources"] + [source_name] * len(new_chunks),
        "embeddings": merged_embeddings,
    }


def merge_indexes(*indexes):
    """Combine several index dicts WITHOUT mutating any of them - used to combine
    the shared base knowledge base with a user's session-only uploaded files."""
    chunks, sources, emb_parts = [], [], []
    for idx in indexes:
        chunks.extend(idx["chunks"])
        sources.extend(idx["sources"])
        if idx["embeddings"].shape[0] > 0:
            emb_parts.append(idx["embeddings"])
    embeddings = np.vstack(emb_parts) if emb_parts else np.zeros((0, EMBED_DIM))
    return {"chunks": chunks, "sources": sources, "embeddings": embeddings}


@st.cache_resource(show_spinner="Indexing your documents...")
def get_base_index():
    """The shared knowledge base built from the DOCS_FOLDER. Cached once per app
    instance - never mutated afterwards, so it's safe to share across users."""
    documents = load_folder_documents()
    return build_index(documents)


def retrieve(index, query: str, top_k: int = TOP_K):
    if index["embeddings"].shape[0] == 0 or not query.strip():
        return []
    q_vec = embed_texts([query])[0]
    emb = index["embeddings"]
    denom = np.linalg.norm(emb, axis=1) * np.linalg.norm(q_vec)
    denom[denom == 0] = 1e-8
    sims = (emb @ q_vec) / denom
    top_idx = np.argsort(sims)[::-1][:top_k]
    return [
        (index["chunks"][i], index["sources"][i], float(sims[i]))
        for i in top_idx if sims[i] >= MIN_SIMILARITY
    ]


# ----------------------------------------------------------------------------
# Groq chat
# ----------------------------------------------------------------------------

def query_groq(prompt: str, use_web_search: bool = True) -> dict:
    """Returns {"answer": str, "web_used": bool}."""
    if groq_client is None:
        return {"answer": "⚛ GROQ_API_KEY is not set. Add it to .env (local) or "
                           "Settings -> Secrets (Streamlit Cloud).", "web_used": False}
    try:
        kwargs = {}
        model = CHAT_MODEL if use_web_search else SUMMARY_MODEL
        if use_web_search:
            kwargs["compound_custom"] = {"tools": {"enabled_tools": ["web_search"]}}

        completion = groq_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        message = completion.choices[0].message
        executed_tools = getattr(message, "executed_tools", None)
        return {"answer": message.content, "web_used": bool(executed_tools)}

    except Exception as e:
        err_msg = str(e)
        if "rate" in err_msg.lower() or "429" in err_msg:
            return {"answer": "⚛ Sorry, the Groq API rate limit has been reached. "
                               "Please try again in a few moments.", "web_used": False}
        return {"answer": f"⚛ An unexpected error occurred: {err_msg}", "web_used": False}


def summarize_messages(messages):
    text = "\n".join(f"{m['role']}: {m['message']}" for m in messages)
    prompt = f"Summarize the following conversation concisely:\n{text}\nSummary:"
    return query_groq(prompt, use_web_search=False)["answer"]


def chat_with_agent(query, index, chat_history, memory_limit=12, extra_file_content=""):
    """Returns (answer: str, doc_sources: list[str], web_used: bool)."""
    retrieved = retrieve(index, query)
    doc_context = "\n\n".join(f"[From {src}]: {chunk}" for chunk, src, _ in retrieved)

    if extra_file_content:
        doc_context += f"\n\nAdditional context from an uploaded file:\n{extra_file_content}"

    if len(chat_history) > memory_limit:
        old_messages = chat_history[:-memory_limit]
        recent_messages = chat_history[-memory_limit:]
        summary = summarize_messages(old_messages)
        conversation_text = f"Summary of earlier conversation: {summary}\n"
    else:
        recent_messages = chat_history
        conversation_text = ""

    for msg in recent_messages:
        conversation_text += f"{msg['role']}: {msg['message']}\n"
    conversation_text += f"User: {query}\n"

    prompt = (
        "You are a helpful assistant with two sources of extra context: (1) content "
        "retrieved from the user's own documents below, and (2) live web search, which "
        "you should use automatically whenever the question needs current, recent, or "
        "up-to-date information that you might not already know.\n\n"
        f"Context from the user's documents:\n"
        f"{doc_context if doc_context else '(no relevant document context found)'}\n\n"
        f"Conversation so far:\n{conversation_text}\n"
        "Answer the user's last message. Prefer the document context when it's relevant; "
        "use web search for anything time-sensitive or current."
    )

    result = query_groq(prompt, use_web_search=True)
    doc_sources = sorted(set(src for _, src, _ in retrieved))
    return result["answer"], doc_sources, result["web_used"]
