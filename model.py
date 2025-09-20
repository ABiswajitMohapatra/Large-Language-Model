import os
import pickle
from groq import Groq
from llama_index.core.schema import TextNode
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
# Load Groq API key
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# --- Load documents from "Sanjukta" folder ---
def load_documents():
    return SimpleDirectoryReader('Sanjukta').load_data()

# --- Create or load index (with embeddings) ---
def create_or_load_index():
    index_file = "index.pkl"
    if os.path.exists(index_file):
        with open(index_file, "rb") as f:
            index = pickle.load(f)
    else:
        docs = load_documents()
        embedding_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        index = VectorStoreIndex(docs, embed_model=embedding_model)
        with open(index_file, "wb") as f:
            pickle.dump(index, f)
    return index

# --- Query Groq API (LLM) ---
def query_groq_api(prompt: str):
    chat_completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",   # Groq model
        messages=[{"role": "user", "content": prompt}]
    )
    return chat_completion.choices[0].message.content

# --- Summarize messages (for memory) ---
def summarize_messages(messages):
    text = ""
    for msg in messages:
        text += f"{msg['role']}: {msg['message']}\n"
    prompt = f"Summarize the following conversation concisely:\n{text}\nSummary:"
    return query_groq_api(prompt)

# --- Chat agent with RAG + memory ---
def chat_with_agent(query, index, chat_history, memory_limit=12):
    # Retrieve context from vector index
    retriever: BaseRetriever = index.as_retriever(similarity_top_k=3)
    nodes = retriever.retrieve(query)
    context = " ".join([node.get_text() for node in nodes if isinstance(node, TextNode)])

    # Manage memory
    if len(chat_history) > memory_limit:
        old_messages = chat_history[:-memory_limit]
        recent_messages = chat_history[-memory_limit:]
        summary = summarize_messages(old_messages)
        conversation_text = f"Summary of previous conversation: {summary}\n"
    else:
        recent_messages = chat_history
        conversation_text = ""

    # Append recent messages
    for msg in recent_messages:
        conversation_text += f"{msg['role']}: {msg['message']}\n"
    conversation_text += f"User: {query}\n"

    # Final prompt
    prompt = (
        f"Context from documents:\n{context}\n\n"
        f"Conversation so far:\n{conversation_text}\n"
        "Answer the user's last query in context."
    )
    return query_groq_api(prompt)


