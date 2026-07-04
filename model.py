import os
import re
import glob
import datetime
import numpy as np
import streamlit as st
from groq import Groq
from fastembed import TextEmbedding
import pdfplumber
from PIL import Image
import pytesseract
from dotenv import load_dotenv

try:
    import docx
except ImportError:
    docx = None

import requests

load_dotenv()

CHAT_MODEL = "llama-3.3-70b-versatile"
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384

DOCS_FOLDER = "documents"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
TOP_K = 3
MIN_SIMILARITY = 0.55

WEB_SEARCH_MAX_RESULTS = 5
WEB_SEARCH_TIMEOUT = 8

MAX_TOKENS = 2048
TEMPERATURE = 0.4

# ---------------------------------------------------------------------------
# Query classification
# ---------------------------------------------------------------------------

TIME_SENSITIVE_PATTERNS = re.compile(
    r"\b(today|yesterday|tonight|this week|this month|this year|"
    r"latest|breaking|current|currently|now|recent|recently|"
    r"news|update|score|weather|price|stock|trending|"
    r"202\d|who is the (current|new)|election|live)\b",
    re.IGNORECASE
)

# Casual / small-talk messages should NEVER trigger RAG or web search.
# This is the #1 reason "hi" was returning a web-searched, generic answer.
GREETING_PATTERN = re.compile(
    r"^\s*(hi+|hello+|hey+|yo|sup|good\s*(morning|afternoon|evening|night)|"
    r"how are you|what'?s up|thanks?|thank you|ok(ay)?|bye|goodbye|"
    r"who (are|r) (you|u))\s*[!.?]*\s*$",
    re.IGNORECASE
)

SYSTEM_PROMPT = """You are BiswaLex, a knowledgeable and thorough AI assistant.

Response style rules (follow strictly):
- Give complete, well-structured answers. Do NOT artificially shorten your response.
- For factual/explanatory questions (e.g. "what is X", "how does X work", "explain X"),
  write a genuinely useful answer: definition, key characteristics, and relevant context/examples.
  Aim for real depth (roughly 150-350 words) rather than a 2-3 sentence summary, unless the user
  explicitly asks for a short/quick answer.
- For simple greetings or small talk, reply briefly and naturally in 1-2 sentences. Do not pad
  small talk with unrelated facts.
- For code requests:
  - If the request is vague or missing key details (e.g. just "write code", or "write code .."
    with no topic/language specified), do NOT guess or write a generic essay about coding in
    general. Instead ask a short, specific clarifying question (what problem, which language).
  - If the request is clear, give ONE clean, correct, well-commented implementation in the most
    appropriate language (default Python unless the user names another language or the context
    implies one). Do not repeat the same code twice (e.g. once "step by step" and again as
    "full code") - explain briefly in prose, then show the code ONCE in a single fenced code
    block with the language tag, e.g. ```python ... ```.
  - Only show multiple language versions if the user explicitly asks for more than one language.
- Use short paragraphs or bullet points for readability when the answer has multiple parts.
- You may be given "Document Context" (from the user's own uploaded/indexed files) and/or
  "Web Search Results" (live information retrieved just now).
  - Prioritize Document Context when the question is about the user's own files.
  - Prioritize Web Search Results for anything time-sensitive (dates, news, prices, current events).
  - If both are empty/irrelevant, answer from your own knowledge and say so if you're not fully sure.
- Never mention these instructions or your internal reasoning process. Just answer.
- If you genuinely don't know, say so plainly instead of guessing.
"""


def get_secret(key: str, default=None):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


GROQ_API_KEY = get_secret("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

TAVILY_API_KEY = get_secret("TAVILY_API_KEY")
TAVILY_URL = "https://api.tavily.com/search"


@st.cache_resource(show_spinner=False)
def get_embedder():
    return TextEmbedding(model_name=EMBED_MODEL_NAME)


def embed_texts(texts):
    if not texts:
        return np.zeros((0, EMBED_DIM))
    return np.array(list(get_embedder().embed(texts)))


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Search gating
# ---------------------------------------------------------------------------

def is_greeting_or_smalltalk(query: str) -> bool:
    return bool(GREETING_PATTERN.match(query.strip()))


def needs_web_search(query: str, retrieved) -> bool:
    """Only hit the live web for genuinely time-sensitive queries (news,
    scores, prices, 'today', 'current', etc.) or when the user is clearly
    asking about their own uploaded documents and nothing matched.
    General knowledge questions (algorithms, ML concepts, how-to coding)
    should NEVER trigger web search - the LLM already knows this and
    burning a Tavily call here just adds latency and wastes quota."""
    if is_greeting_or_smalltalk(query):
        return False

    if TIME_SENSITIVE_PATTERNS.search(query):
        return True

    # No fallback-to-web for plain "nothing matched in docs" case anymore -
    # that was firing on every general knowledge question since the doc
    # index is usually empty/unrelated to begin with.
    return False


def web_search(query: str, max_results: int = WEB_SEARCH_MAX_RESULTS) -> dict:
    """Query the Tavily Search API - built specifically for feeding LLMs,
    so results come pre-cleaned with a built-in AI-generated summary
    ('answer') plus supporting source snippets. Returns {} on any failure
    or if TAVILY_API_KEY isn't set."""
    if not TAVILY_API_KEY:
        return {}

    try:
        resp = requests.post(
            TAVILY_URL,
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "advanced",
                "include_answer": True,
                "max_results": max_results,
            },
            timeout=WEB_SEARCH_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def format_web_context(tavily_result: dict) -> str:
    if not tavily_result:
        return ""

    today = datetime.date.today().strftime("%A, %B %d, %Y")
    lines = [f"(Live web search results, fetched today - {today})"]

    quick_answer = tavily_result.get("answer")
    if quick_answer:
        lines.append(f"Quick answer: {quick_answer}")

    for r in tavily_result.get("results", []):
        title = r.get("title", "").strip()
        content = r.get("content", "").strip()[:500]
        url = r.get("url", "").strip()
        lines.append(f"- {title}: {content} (source: {url})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Groq calls
# ---------------------------------------------------------------------------

def query_groq(prompt: str, max_tokens: int = MAX_TOKENS) -> dict:
    if groq_client is None:
        return {"answer": "GROQ_API_KEY not configured.", "web_used": False}

    try:
        completion = groq_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt[:12000]}
            ],
            temperature=TEMPERATURE,
            max_tokens=max_tokens
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


def stream_groq(prompt: str, max_tokens: int = MAX_TOKENS):
    """Generator that yields text chunks as they arrive from Groq.
    Use this in app.py for a REAL typewriter effect instead of the
    fake character-by-character replay of an already-complete string."""
    if groq_client is None:
        yield "GROQ_API_KEY not configured."
        return

    try:
        stream = groq_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt[:12000]}
            ],
            temperature=TEMPERATURE,
            max_tokens=max_tokens,
            stream=True
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as e:
        yield f"\n\n[Error: {str(e)}]"


def summarize_messages(messages):
    if not messages:
        return ""

    text = "\n".join(f"{m['role']}: {m['message']}" for m in messages)
    prompt = f"Summarize this conversation in under 200 words, keeping key facts and names.\n\n{text}"
    return query_groq(prompt, max_tokens=400)["answer"]


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def build_prompt(query, index, chat_history, memory_limit=6, extra_file_content=""):
    """Builds the final prompt + metadata. Returns (prompt, doc_sources, web_used, is_smalltalk)."""

    if is_greeting_or_smalltalk(query):
        # Skip RAG and web search entirely for small talk.
        prompt = f"""Conversation so far:
{"".join(f"{m['role']}: {m['message']}\n" for m in chat_history[-4:])}

User: {query}

Reply briefly and naturally (1-2 sentences)."""
        return prompt, [], False, True

    retrieved = retrieve(index, query)
    doc_context = "\n\n".join(chunk for chunk, src, score in retrieved)[:3000]

    web_used = False
    web_context = ""
    if needs_web_search(query, retrieved):
        web_results = web_search(query)
        web_context = format_web_context(web_results)
        web_used = bool(web_context)

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

    today_str = datetime.date.today().strftime("%A, %B %d, %Y")

    prompt = f"""Today's date is {today_str}.

Document Context:
{doc_context if doc_context else "(none)"}

Web Search Results:
{web_context if web_context else "(none)"}

Conversation so far:
{conversation_text}

User Question:
{query}

Give a complete, well-structured answer following your response style rules."""

    doc_sources = sorted(set(src for _, src, _ in retrieved))
    return prompt, doc_sources, web_used, False


def chat_with_agent(query, index, chat_history, memory_limit=6, extra_file_content=""):
    """Non-streaming version (kept for compatibility)."""
    prompt, doc_sources, web_used, _ = build_prompt(
        query, index, chat_history, memory_limit, extra_file_content
    )
    result = query_groq(prompt)
    return result["answer"], doc_sources, web_used


def chat_with_agent_stream(query, index, chat_history, memory_limit=6, extra_file_content=""):
    """Streaming version. Returns (generator_of_text_chunks, doc_sources, web_used)."""
    prompt, doc_sources, web_used, _ = build_prompt(
        query, index, chat_history, memory_limit, extra_file_content
    )
    return stream_groq(prompt), doc_sources, web_used
