# model.py

import os
import pickle
from groq import Groq
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.settings import Settings

# =========================
# GROQ CLIENT
# =========================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# =========================
# EMBEDDING MODEL (REAL — not fake)
# Works on Streamlit Cloud
# =========================
embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-en-v1.5"
)

# Apply globally
Settings.embed_model = embed_model
Settings.node_parser = SentenceSplitter(
    chunk_size=512,
    chunk_overlap=80,
)

# =========================
# LOAD DOCUMENTS SAFELY
# =========================
def load_documents():
    folder = "Sanjukta"
    if os.path.exists(folder):
        return SimpleDirectoryReader(folder).load_data()
    else:
        print(f"⚠ Folder '{folder}' not found.")
        return []

# =========================
# CREATE OR LOAD INDEX
# (Streamlit-friendly)
# =========================
def create_or_load_index():
    index_file = "index.pkl"

    try:
        if os.path.exists(index_file):
            with open(index_file, "rb") as f:
                index = pickle.load(f)
        else:
            docs = load_documents()
            index = VectorStoreIndex.from_documents(docs)
            with open(index_file, "wb") as f:
                pickle.dump(index, f)
    except Exception as e:
        print("⚠ Rebuilding index due to error:", e)
        docs = load_documents()
        index = VectorStoreIndex.from_documents(docs)

    return index

# =========================
# GROQ CALL
# =========================
def query_groq_api(prompt: str):
    try:
        chat_completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"⚛ Error: {str(e)}"

# =========================
# OPTIONAL LIVE SEARCH
# (currently safe fallback)
# =========================
def live_search(query: str) -> str:
    """
    Later you can connect Tavily or Serper here.
    For now returns empty so app never crashes.
    """
    return ""

# =========================
# MAIN RAG PIPELINE
# =========================
def chat_with_agent(query, index, chat_history, memory_limit=12):

    # ---- RETRIEVE ----
    retriever = index.as_retriever(similarity_top_k=4)
    nodes = retriever.retrieve(query)

    # Debug log (visible in Streamlit logs)
    print("\n🔍 Retrieved chunks:")
    for i, n in enumerate(nodes):
        print(f"\n--- Chunk {i+1} ---\n{n.get_text()[:300]}")

    context = "\n\n".join([n.get_text() for n in nodes])

    # ---- LIVE DATA ----
    live_context = live_search(query)

    # ---- MEMORY ----
    if len(chat_history) > memory_limit:
        recent_messages = chat_history[-memory_limit:]
    else:
        recent_messages = chat_history

    conversation_text = ""
    for msg in recent_messages:
        conversation_text += f"{msg['role']}: {msg['message']}\n"

    # ---- STRONG GROUNDED PROMPT ----
    prompt = f"""
You are a grounded AI assistant.

STRICT RULES:
- Answer ONLY from the provided context.
- If answer is not in context, say: "I don't have enough information."
- Do NOT use prior knowledge.
- Be concise and factual.

DOCUMENT CONTEXT:
{context}

LIVE DATA:
{live_context}

CONVERSATION:
{conversation_text}

USER QUESTION:
{query}

ANSWER:
"""

    return query_groq_api(prompt)
