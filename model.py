# model.py

import os
import pickle
from groq import Groq
from llama_index.core.schema import TextNode
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.settings import Settings
import pdfplumber
from PIL import Image
import pytesseract
from tavily import TavilyClient

# =========================
# GROQ API
# =========================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

def query_groq_api(prompt: str):
    try:
        chat_completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        err_msg = str(e)
        if "RateLimit" in err_msg:
            return "⚛ Sorry, the API rate limit has been reached. Please try again in a few moments."
        return f"⚛ An unexpected error occurred: {err_msg}"

# =========================
# Document Embeddings (REAL)
# =========================
embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
Settings.embed_model = embed_model
Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=80)

# =========================
# Live search / current data
# =========================
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

def needs_live_data(query: str) -> bool:
    keywords = [
        "today", "latest", "current", "news", "recent",
        "stock", "price now", "weather"
    ]
    q = query.lower()
    return any(k in q for k in keywords)

def live_search(query: str) -> str:
    try:
        if not TAVILY_API_KEY:
            return ""
        response = tavily_client.search(query=query, search_depth="advanced", max_results=3)
        results = [f"{r['title']}: {r['content']}" for r in response.get("results", [])]
        return "\n\n".join(results)
    except Exception as e:
        print("Live search error:", e)
        return ""

# =========================
# Load documents safely
# =========================
def load_documents():
    folder = "Sanjukta"
    if os.path.exists(folder):
        return SimpleDirectoryReader(folder).load_data()
    else:
        print(f"⚠ Folder '{folder}' not found. Continuing with empty documents.")
        return []

# =========================
# Create or load index
# =========================
def create_or_load_index():
    index_file = "index.pkl"
    if os.path.exists(index_file):
        with open(index_file, "rb") as f:
            index = pickle.load(f)
    else:
        docs = load_documents()
        index = VectorStoreIndex.from_documents(docs)
        with open(index_file, "wb") as f:
            pickle.dump(index, f)
    return index

# =========================
# Summarize messages for memory
# =========================
def summarize_messages(messages):
    text = ""
    for msg in messages:
        text += f"{msg['role']}: {msg['message']}\n"
    prompt = f"Summarize the following conversation concisely:\n{text}\nSummary:"
    return query_groq_api(prompt)

# =========================
# RAG + live data + fallback
# =========================
def chat_with_agent(query, index, chat_history, memory_limit=12, extra_file_content=""):
    retriever: BaseRetriever = index.as_retriever()
    nodes = retriever.retrieve(query)
    context = " ".join([node.get_text() for node in nodes if isinstance(node, TextNode)])

    if extra_file_content:
        context += f"\nAdditional context from uploaded file:\n{extra_file_content}"

    rag_context = context
    live_context = live_search(query) if needs_live_data(query) else ""

    # Combine contexts
    full_context = ""
    if rag_context:
        full_context += f"DOCUMENT CONTEXT:\n{rag_context}\n"
    if live_context:
        full_context += f"LIVE DATA:\n{live_context}\n"

    # Chat memory
    if len(chat_history) > memory_limit:
        old_messages = chat_history[:-memory_limit]
        recent_messages = chat_history[-memory_limit:]
        summary = summarize_messages(old_messages)
        conversation_text = f"Summary of previous conversation: {summary}\n"
    else:
        recent_messages = chat_history
        conversation_text = ""
    for msg in recent_messages:
        conversation_text += f"{msg['role']}: {msg['message']}\n"
    conversation_text += f"User: {query}\n"

    # Final prompt
    if not full_context.strip():
        # Fallback to general knowledge if no document/live data
        prompt = f"Answer the following question as best as you can:\n{query}\nAnswer:"
    else:
        prompt = (
            f"STRICTLY USE THE FOLLOWING CONTEXT TO ANSWER:\n{full_context}\n"
            f"Conversation so far:\n{conversation_text}\n"
            "Answer the user's last query based on the above context. "
            "If answer is not in context, answer based on general knowledge."
        )

    return query_groq_api(prompt)

# =========================
# PDF & Image Extraction
# =========================
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.strip()

def extract_text_from_image(file):
    image = Image.open(file)
    return pytesseract.image_to_string(image)
