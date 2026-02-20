# =========================
# model.py additions for RAG + current data
# =========================

from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.settings import Settings
from tavily import TavilyClient
import os

# -------------------------
# Strong embeddings for RAG
# -------------------------
# This replaces your zero embeddings internally, no other code change
embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
Settings.embed_model = embed_model
Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=80)

# -------------------------
# Live search for current data
# -------------------------
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

def needs_live_data(query: str) -> bool:
    """Return True if query likely needs current/live data"""
    keywords = [
        "today", "latest", "current", "news", "recent", 
        "stock", "price now", "weather"
    ]
    q = query.lower()
    return any(k in q for k in keywords)

def live_search(query: str) -> str:
    """Fetch live data using Tavily API"""
    try:
        if not TAVILY_API_KEY:
            return ""
        response = tavily_client.search(query=query, search_depth="advanced", max_results=3)
        results = [f"{r['title']}: {r['content']}" for r in response.get("results", [])]
        return "\n\n".join(results)
    except Exception as e:
        print("Live search error:", e)
        return ""

# -------------------------
# Updated chat_with_agent
# -------------------------
# Only modify this function, keeping all previous logic intact
old_chat_with_agent = chat_with_agent  # keep backup

def chat_with_agent(query, index, chat_history, memory_limit=12, extra_file_content=""):
    # --- original retrieval ---
    retriever = index.as_retriever()
    nodes = retriever.retrieve(query)
    context = " ".join([node.get_text() for node in nodes if isinstance(node, TextNode)])

    if extra_file_content:
        context += f"\nAdditional context from uploaded file:\n{extra_file_content}"

    # --- RAG results from nodes ---
    rag_context = context

    # --- live data if needed ---
    live_context = live_search(query) if needs_live_data(query) else ""

    # --- combine contexts ---
    full_context = ""
    if rag_context:
        full_context += f"DOCUMENT CONTEXT:\n{rag_context}\n"
    if live_context:
        full_context += f"LIVE DATA:\n{live_context}\n"

    # --- conversation memory ---
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

    # --- final prompt ---
    prompt = (
        f"STRICTLY USE THE FOLLOWING CONTEXT TO ANSWER:\n{full_context}\n"
        f"Conversation so far:\n{conversation_text}\n"
        "Answer the user's last query based on the above context. "
        "If answer is not in context, answer based on general knowledge."
    )

    # --- call Groq API as before ---
    return query_groq_api(prompt)
