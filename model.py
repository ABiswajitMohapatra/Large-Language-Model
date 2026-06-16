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

load_dotenv()

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

CHAT_MODEL = "llama-3.3-70b-versatile"
SUMMARY_MODEL = "llama-3.1-8b-instant"
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384

DOCS_FOLDER = "documents"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
TOP_K = 3
MIN_SIMILARITY = 0.55


def get_secret(key: str, default=None):
    """Read from Streamlit secrets first, then environment variables."""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


GROQ_API_KEY = get_secret("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

SYSTEM_PROMPT = """
You are a helpful AI assistant.

Answer naturally and directly.

Never mention:
- document retrieval
- document context
- web search
- internal reasoning

If information is unavailable, simply say you do not know.
"""


# ----------------------------------------------------------------------------
# Embeddings
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
# Chunking + vector index
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
    return {
        "chunks": [],
        "sources": [],
        "embeddings": np.zeros((0, EMBED_DIM))
    }


def build_index(documents):
    chunks, sources = [], []

    for source, text in documents:
        for chunk in chunk_text(text):
            chunks.append(chunk)
            sources.append(source)

    if not chunks:
        return empty_index()

    return {
        "chunks": chunks,
        "sources": sources,
        "embeddings": embed_texts(chunks)
    }


def add_to_index(index, source_name: str, text: str):
    new_chunks = chunk_text(text)
    if not new_chunks:
        return index

    new_vectors = embed_texts(new_chunks)

    merged_embeddings = (
        new_vectors
        if index["embeddings"].shape[0] == 0
        else np.vstack([index["embeddings"], new_vectors])
    )

    return {
        "chunks": index["chunks"] + new_chunks,
        "sources": index["sources"] + [source_name] * len(new_chunks),
        "embeddings": merged_embeddings,
    }


def merge_indexes(*indexes):
    chunks, sources, emb_parts = [], [], []

    for idx in indexes:
        chunks.extend(idx["chunks"])
        sources.extend(idx["sources"])
        if idx["embeddings"].shape[0] > 0:
            emb_parts.append(idx["embeddings"])

    embeddings = np.vstack(emb_parts) if emb_parts else np.zeros((0, EMBED_DIM))

    return {
        "chunks": chunks,
        "sources": sources,
        "embeddings": embeddings
    }


@st.cache_resource(show_spinner="Indexing your documents...")
def get_base_index():
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
        for i in top_idx
        if sims[i] >= MIN_SIMILARITY
    ]


# ----------------------------------------------------------------------------
# Groq chat
# ----------------------------------------------------------------------------

def query_groq(prompt: str) -> dict:
    if groq_client is None:
        return {
            "answer": "GROQ_API_KEY not configured.",
            "web_used": False
        }

    try:
        if len(prompt) > 12000:
            prompt = prompt[:12000]

        completion = groq_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )

        return {
            "answer": completion.choices[0].message.content,
            "web_used": False
        }

    except Exception as e:
        return {
            "answer": f"Error: {str(e)}",
            "web_used": False
        }


def summarize_messages(messages):
    if not messages:
        return ""

    text = "\n".join(
        f"{m['role']}: {m['message']}"
        for m in messages
    )

    prompt = f"""
Summarize this conversation in under 200 words.

{text}
"""

    return query_groq(prompt)["answer"]


def chat_with_agent(
    query,
    index,
    chat_history,
    memory_limit=6,
    extra_file_content=""
):
    retrieved = retrieve(index, query)

    doc_context = "\n\n".join(
        chunk for chunk, src, score in retrieved
    )
    doc_context = doc_context[:3000]

    if len(chat_history) > memory_limit:
        summary = summarize_messages(chat_history[:-memory_limit])
        recent_messages = chat_history[-memory_limit:]
        conversation_text = summary + "\n"
    else:
        recent_messages = chat_history
        conversation_text = ""

    for msg in recent_messages:
        conversation_text += f"{msg['role']}: {msg['message']}\n"

    conversation_text = conversation_text[-3000:]

    if extra_file_content:
        doc_context = (doc_context + "\n\n" + extra_file_content[:2000]).strip()

    prompt = f"""
Document Information:

{doc_context}

Conversation:

{conversation_text}

User Question:

{query}

Answer the question clearly.
"""

    result = query_groq(prompt)

    doc_sources = sorted(set(src for _, src, _ in retrieved))

    return result["answer"], doc_sources, result["web_used"]
