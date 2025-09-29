import os
import pickle
import requests
from groq import Groq
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core import VectorStoreIndex
import pdfplumber
from PIL import Image
import pytesseract
import streamlit as st

# Access keys securely via streamlit.secrets if running on Streamlit Cloud
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
NEWSAPI_KEY = st.secrets["newsapi"]["api_key"]
CRICAPI_KEY = st.secrets["cricapi"]["api_key"]  # <-- Add this to your secrets

client = Groq(api_key=GROQ_API_KEY)

class CustomEmbedding(BaseEmbedding):
    def _get_query_embedding(self, query: str) -> list[float]:
        return [0.0] * 512
    async def _aget_query_embedding(self, query: str) -> list[float]:
        return [0.0] * 512
    def _get_text_embedding(self, text: str) -> list[float]:
        return [0.0] * 512

def create_or_load_index():
    index_file = "index.pkl"
    if os.path.exists(index_file):
        with open(index_file, "rb") as f:
            index = pickle.load(f)
    else:
        embedding_model = CustomEmbedding()
        index = VectorStoreIndex([], embed_model=embedding_model)
        with open(index_file, "wb") as f:
            pickle.dump(index, f)
    return index

def query_groq_api(prompt: str):
    try:
        chat_completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        err_msg = str(e)
        if "RateLimit" in err_msg:
            return "⚛ Sorry, the API rate limit has been reached. Please try again in a few moments."
        return f"⚛ An unexpected error occurred: {err_msg}"

def summarize_messages(messages):
    text = ""
    for msg in messages:
        text += f"{msg['role']}: {msg['message']}\n"
    prompt = f"Summarize the following conversation concisely:\n{text}\nSummary:"
    return query_groq_api(prompt)

# -------------------- NEWS API --------------------
def fetch_news(query: str, api_key: str, page_size: int = 5):
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "pageSize": page_size,
        "apiKey": api_key,
        "language": "en",
        "sortBy": "relevancy"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        return data.get("articles", [])
    else:
        return []

# -------------------- CRICKET API --------------------
def fetch_recent_matches():
    url = f"https://cricapi.com/api/matches?apikey={CRICAPI_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("matches", [])
    return []

def fetch_cricket_score(match_id: str):
    url = f"https://cricapi.com/api/cricketScore?apikey={CRICAPI_KEY}&unique_id={match_id}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return {"error": "Unable to fetch score"}

def cricket_retrieve(query: str):
    matches = fetch_recent_matches()
    for match in matches:
        if "India" in query and ("India" in match.get("team-1","") or "India" in match.get("team-2","")):
            match_id = match.get("unique_id")
            score_data = fetch_cricket_score(match_id)
            return f"🏏 {match.get('team-1')} vs {match.get('team-2')} - {score_data.get('score','No score available')}"
        if "England" in query and ("England" in match.get("team-1","") or "England" in match.get("team-2","")):
            match_id = match.get("unique_id")
            score_data = fetch_cricket_score(match_id)
            return f"🏏 {match.get('team-1')} vs {match.get('team-2')} - {score_data.get('score','No score available')}"
        if "Asia Cup" in query and "Asia Cup" in match.get("type",""):
            match_id = match.get("unique_id")
            score_data = fetch_cricket_score(match_id)
            return f"🏏 Asia Cup Match {match.get('team-1')} vs {match.get('team-2')} - {score_data.get('score','No score available')}"
    return None

# -------------------- RAG Retrieve --------------------
def rag_retrieve(query: str, index=None, top_k=3) -> list[str]:
    results = []

    # Cricket queries handled separately
    if any(word in query.lower() for word in ["score", "cricket", "asia cup", "odi", "t20", "ipl"]):
        cricket_result = cricket_retrieve(query)
        if cricket_result:
            results.append(cricket_result)
            return results

    # Otherwise fetch from NewsAPI
    news_articles = fetch_news(query, NEWSAPI_KEY, page_size=top_k)
    for article in news_articles:
        title = article.get("title", "")
        desc = article.get("description", "")
        if title and desc:
            results.append(f"News Title: {title}\nSummary: {desc}")
    return results

# -------------------- Chat Agent --------------------
def chat_with_agent(query, index, chat_history, memory_limit=12, extra_file_content=""):
    rag_results = rag_retrieve(query, index=index, top_k=3)
    rag_context = "\n".join(rag_results)

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
        f"Context from news/cricket and files: {rag_context}\n"
        f"Conversation so far:\n{conversation_text}\n"
        "Answer the user's last query in context."
    )
    return query_groq_api(prompt)

# -------------------- File Helpers --------------------
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.strip()

def extract_text_from_image(file):
    image = Image.open(file)
    return pytesseract.image_to_string(image)
