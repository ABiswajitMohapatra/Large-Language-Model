import os
import pickle
import requests
from groq import Groq
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core import VectorStoreIndex
from PIL import Image
import pytesseract
import pdfplumber
import streamlit as st

# --- API Keys ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
NEWSAPI_KEY = st.secrets["newsapi"]["api_key"]
CRICAPI_KEY = st.secrets["cricapi"]["api_key"]

client = Groq(api_key=GROQ_API_KEY)

# --- Custom Embedding ---
class CustomEmbedding(BaseEmbedding):
    def _get_query_embedding(self, query: str) -> list[float]:
        return [0.0] * 512
    async def _aget_query_embedding(self, query: str) -> list[float]:
        return [0.0] * 512
    def _get_text_embedding(self, text: str) -> list[float]:
        return [0.0] * 512

# --- Vector Index ---
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

# --- Groq Query ---
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
            return "⚛ Sorry, the API rate limit has been reached. Try again later."
        return f"⚛ An unexpected error occurred: {err_msg}"

def summarize_messages(messages):
    text = "".join([f"{m['role']}: {m['message']}\n" for m in messages])
    prompt = f"Summarize the following conversation concisely:\n{text}\nSummary:"
    return query_groq_api(prompt)

# --- News API ---
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
    return []

# --- Cricket API ---
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
        data = response.json()
        score = data.get('score') or data.get('stat') or data.get('score_string') or "No score available"
        team1 = data.get('team-1', '')
        team2 = data.get('team-2', '')
        return {"score": score, "team-1": team1, "team-2": team2}
    return {"score": "Unable to fetch score"}

def cricket_retrieve(query: str):
    matches = fetch_recent_matches()
    query_lower = query.lower()
    for match in matches:
        teams = [match.get("team-1", ""), match.get("team-2", "")]
        if ("asia cup" in query_lower) or any(t.lower() in query_lower for t in teams):
            match_id = match.get("unique_id")
            score_data = fetch_cricket_score(match_id)
            return f"🏏 {score_data['team-1']} vs {score_data['team-2']} - {score_data['score']}"
    return None

# --- RAG Retrieve (Universal) ---
def rag_retrieve(query: str, index=None, top_k=3) -> list[str]:
    results = []

    # --- Cricket ---
    if any(word in query.lower() for word in ["score", "cricket", "asia cup", "odi", "t20", "ipl"]):
        cricket_result = cricket_retrieve(query)
        if cricket_result:
            results.append(cricket_result)

    # --- News ---
    news_keywords = ["news", "update", "breaking", "latest", "report", "headline"]
    if any(word in query.lower() for word in news_keywords) or len(results) == 0:
        news_articles = fetch_news(query, NEWSAPI_KEY, page_size=top_k)
        for article in news_articles:
            title = article.get("title", "")
            desc = article.get("description", "")
            if title and desc:
                results.append(f"📰 News Title: {title}\nSummary: {desc}")

    # --- Local index (PDF/Image docs if any) ---
    if index is not None:
        retriever = index.as_retriever()
        nodes = retriever.retrieve(query)
        for node in nodes[:top_k]:
            if hasattr(node, "get_text"):
                text = node.get_text()
                if text:
                    results.append(f"📄 File Content: {text[:500]}...")  # preview first 500 chars

    return results

# --- Chat Agent ---
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
        f"Context from news/cricket/files: {rag_context}\n"
        f"Conversation so far:\n{conversation_text}\n"
        "Answer the user's last query in context."
    )
    return query_groq_api(prompt)

# --- File Helpers ---
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.strip()

def extract_text_from_image(file):
    image = Image.open(file)
    return pytesseract.image_to_string(image)
