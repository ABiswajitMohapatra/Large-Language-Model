import os
import pickle
import time
import datetime  # <-- added for live data handling
import pandas as pd  # <-- added for live data handling
from groq import Groq
from llama_index.core.schema import TextNode
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
import pdfplumber
from PIL import Image
import pytesseract
import streamlit as st

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# ---------------- Custom Embedding ----------------
class CustomEmbedding(BaseEmbedding):
    def _get_query_embedding(self, query: str) -> list[float]:
        return [0.0] * 512
    async def _aget_query_embedding(self, query: str) -> list[float]:
        return [0.0] * 512
    def _get_text_embedding(self, text: str) -> list[float]:
        return [0.0] * 512

# ---------------- Document Loading ----------------
def load_documents():
    folder = "Sanjukta"
    if os.path.exists(folder):
        return SimpleDirectoryReader(folder).load_data()
    else:
        print(f"⚠️ Folder '{folder}' not found. Continuing with empty documents.")
        return []

# ---------------- Index Creation / Loading ----------------
def create_or_load_index():
    index_file = "index.pkl"
    if os.path.exists(index_file):
        with open(index_file, "rb") as f:
            index = pickle.load(f)
    else:
        docs = load_documents()
        embedding_model = CustomEmbedding()
        index = VectorStoreIndex(docs, embed_model=embedding_model)
        with open(index_file, "wb") as f:
            pickle.dump(index, f)
    return index

# ---------------- Groq API Query ----------------
def query_groq_api(prompt: str, retries=3, delay=2):
    for attempt in range(retries):
        try:
            chat_completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
                continue
            else:
                return f"⚛ Sorry, Groq API failed: {str(e)}"

# ---------------- Summarize Old Messages ----------------
def summarize_messages(messages):
    text = ""
    for msg in messages:
        text += f"{msg['role']}: {msg['message']}\n"
    prompt = f"Summarize the following conversation concisely:\n{text}\nSummary:"
    return query_groq_api(prompt)

# ---------------- RAG Retrieval (NEW) ----------------
def rag_retrieve(query: str, top_k: int = 3) -> list[str]:
    """
    Retrieves relevant text snippets from:
    1. Pre-indexed documents
    2. Uploaded PDF (dynamic)
    3. Live/current data (e.g., yesterday's sales)
    """
    texts = []

    # --- 1. Pre-indexed documents (existing functionality) ---
    if 'index' in st.session_state:
        retriever: BaseRetriever = st.session_state.index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query)
        texts.extend([node.get_text() for node in nodes if isinstance(node, TextNode)])

    # --- 2. Uploaded PDF (existing functionality, integrated dynamically) ---
    if "uploaded_pdf_text" in st.session_state and st.session_state.uploaded_pdf_text:
        pdf_chunks = [st.session_state.uploaded_pdf_text[i:i+1000] 
                      for i in range(0, len(st.session_state.uploaded_pdf_text), 1000)]
        texts.extend(pdf_chunks[:top_k])

    # --- 3. Live/current data (NEW) ---
    try:
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        # Replace with your actual live data CSV or data source
        if os.path.exists("sales_data.csv"):
            df = pd.read_csv("sales_data.csv")
            yesterday_data = df[df['date'] == yesterday]
            if not yesterday_data.empty:
                live_text = yesterday_data.to_string(index=False)
                texts.append(live_text)
    except Exception as e:
        texts.append(f"⚛ Could not load live data: {str(e)}")

    return texts

# ---------------- Chat With Agent ----------------
def chat_with_agent(query, index, chat_history, memory_limit=12, extra_file_content=""):
    retriever: BaseRetriever = index.as_retriever()
    nodes = retriever.retrieve(query)
    context = " ".join([node.get_text() for node in nodes if isinstance(node, TextNode)])

    if extra_file_content:
        context += f"\nAdditional context from uploaded file:\n{extra_file_content}"

    # --- RAG integration (NEW) ---
    rag_results = rag_retrieve(query)
    rag_context = "\n".join(rag_results)
    full_context = context + "\n" + rag_context if rag_context else context

    # --- Conversation memory ---
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

    # --- Structured-answer prompt (existing functionality) ---
    prompt = (
        f"Context from documents and files: {full_context}\n"
        f"Conversation so far:\n{conversation_text}\n"
        "Answer the user's last query in context.\n"
        "Format the answer professionally and clearly using:\n"
        "- Bullet points for each key point\n"
        "- Tables for comparisons or numeric data (use Markdown table syntax)\n"
        "- Highlight keywords using **bold** or *italic* text\n"
        "- Provide clear reasoning, analysis, or examples when applicable\n"
        "- Keep language concise and well-structured for readability\n"
    )
    return query_groq_api(prompt)

# ---------------- PDF / Image Extraction (existing) ----------------
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.strip()

def extract_text_from_image(file):
    image = Image.open(file)
    return pytesseract.image_to_string(image)
