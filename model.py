import os
import pickle
import datetime
import requests
import pandas as pd
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

# --- Embedding ---
class CustomEmbedding(BaseEmbedding):
    def _get_query_embedding(self, query: str) -> list[float]:
        return [0.0] * 512
    async def _aget_query_embedding(self, query: str) -> list[float]:
        return [0.0] * 512
    def _get_text_embedding(self, text: str) -> list[float]:
        return [0.0] * 512

# --- Load local documents ---
def load_documents():
    folder = "Sanjukta"
    if os.path.exists(folder):
        return SimpleDirectoryReader(folder).load_data()
    else:
        print(f"⚠️ Folder '{folder}' not found. Continuing with empty documents.")
        return []

# --- Create or load index ---
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

# --- Groq API query ---
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
                import time; time.sleep(delay)
                continue
            else:
                return f"⚛ Sorry, Groq API failed: {str(e)}"

# --- Summarize old messages ---
def summarize_messages(messages):
    text = ""
    for msg in messages:
        text += f"{msg['role']}: {msg['message']}\n"
    prompt = f"Summarize the following conversation concisely:\n{text}\nSummary:"
    return query_groq_api(prompt)

# --- Fetch yesterday's news ---
def fetch_yesterdays_news():
    api_key = "YOUR_NEWSAPI_KEY"  # Replace with your NewsAPI key
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    url = f"https://newsapi.org/v2/everything?q=latest&from={yesterday}&to={yesterday}&sortBy=publishedAt&apiKey={api_key}&language=en&pageSize=5"
    try:
        response = requests.get(url)
        data = response.json()
        if data['status'] == 'ok' and data['totalResults'] > 0:
            news_text = "**Yesterday's Top News:**\n\n"
            for article in data['articles']:
                news_text += f"- **{article['title']}**\n  {article['description']}\n  Source: {article['source']['name']}\n\n"
            return news_text
        else:
            return "⚛ Sorry, no news was found for yesterday."
    except Exception as e:
        return f"⚛ Could not fetch live news: {str(e)}"

# --- Fetch live cricket scores (example placeholder) ---
def fetch_cricket_scores():
    # Replace with actual Cricket API integration
    return "**Yesterday's Cricket Scores:**\n- Team A vs Team B: 250/5 vs 200/10\n- Winner: Team A\n"

# --- Fetch finance data placeholder ---
def fetch_stock_prices(query):
    # Replace with actual Finance API like yfinance
    return "**Finance Update:**\n- Stock XYZ: $123.45\n- Stock ABC: $67.89\n"

# --- Fetch weather data placeholder ---
def fetch_weather(query):
    # Replace with actual Weather API
    return "**Weather Update:**\n- Yesterday in New York: 22°C, Sunny\n"

# --- Fetch live data based on query ---
def fetch_live_data(query):
    texts = []
    q = query.lower()
    if "news" in q or "yesterday" in q:
        texts.append(fetch_yesterdays_news())
    if "cricket" in q or "match" in q:
        texts.append(fetch_cricket_scores())
    if "stock" in q or "price" in q:
        texts.append(fetch_stock_prices(query))
    if "weather" in q:
        texts.append(fetch_weather(query))
    return texts

# --- RAG retrieve ---
def rag_retrieve(query: str, top_k: int = 3) -> list[str]:
    texts = []

    # --- Local PDFs / Index ---
    if 'index' in st.session_state:
        retriever: BaseRetriever = st.session_state.index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query)
        texts.extend([node.get_text() for node in nodes if isinstance(node, TextNode)])

    # --- Uploaded PDFs ---
    if "uploaded_pdf_text" in st.session_state:
        pdf_chunks = [st.session_state.uploaded_pdf_text[i:i+1000] 
                      for i in range(0, len(st.session_state.uploaded_pdf_text), 1000)]
        texts.extend(pdf_chunks[:top_k])

    # --- Live APIs ---
    live_texts = fetch_live_data(query)
    texts.extend(live_texts)

    return texts

# --- Chat with agent ---
def chat_with_agent(query, index, chat_history, memory_limit=12, extra_file_content=""):
    retriever: BaseRetriever = index.as_retriever()
    nodes = retriever.retrieve(query)
    context = " ".join([node.get_text() for node in nodes if isinstance(node, TextNode)])

    if extra_file_content:
        context += f"\nAdditional context from uploaded file:\n{extra_file_content}"

    rag_results = rag_retrieve(query)
    rag_context = "\n".join(rag_results)

    full_context = context + "\n" + rag_context if rag_context else context

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

    prompt = (
        f"Context from documents, uploaded files, and live data: {full_context}\n"
        f"Conversation so far:\n{conversation_text}\n"
        "Answer the user's last query in context.\n"
        "Format the answer professionally and clearly using:\n"
        "- Bullet points for key points\n"
        "- Tables for comparisons or numeric data (Markdown table)\n"
        "- Highlight keywords using **bold** or *italic*\n"
        "- Provide clear reasoning, analysis, or examples\n"
        "- Keep language concise and well-structured"
    )
    return query_groq_api(prompt)

# --- PDF / Image helpers ---
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.strip()

def extract_text_from_image(file):
    image = Image.open(file)
    return pytesseract.image_to_string(image)
