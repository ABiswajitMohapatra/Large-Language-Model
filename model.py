import os
import pickle
import requests
from groq import Groq
from llama_index.core.schema import TextNode
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
import pdfplumber
from PIL import Image
import pytesseract
import streamlit as st

# Access keys securely via streamlit.secrets if running on Streamlit Cloud
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
NEWSAPI_KEY = st.secrets["newsapi"]["api_key"]

client = Groq(api_key=GROQ_API_KEY)

class CustomEmbedding(BaseEmbedding):
    def _get_query_embedding(self, query: str) -> list[float]:
        return [0.0] * 512
    async def _aget_query_embedding(self, query: str) -> list[float]:
        return [0.0] * 512
    def _get_text_embedding(self, text: str) -> list[float]:
        return [0.0] * 512

def load_documents():
    folder = "Sanjukta"
    if os.path.exists(folder):
        return SimpleDirectoryReader(folder).load_data()
    else:
        print(f"⚠️ Folder '{folder}' not found. Continuing with empty documents.")
        return []

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

def rag_retrieve(query: str, index=None, top_k=3) -> list[str]:
    results = []
    # Retrieve from local index if available
    if index is not None:
        retriever: BaseRetriever = index.as_retriever()
        nodes = retriever.retrieve(query)
        for node in nodes[:top_k]:
            if isinstance(node, TextNode):
                text = node.get_text()
                if text:
                    results.append(text)
    # Retrieve live news articles from NewsAPI
    news_articles = fetch_news(query, NEWSAPI_KEY, page_size=top_k)
    for article in news_articles:
        title = article.get("title", "")
        desc = article.get("description", "")
        if title and desc:
            results.append(f"News Title: {title}\nSummary: {desc}")
    return results

def chat_with_agent(query, index, chat_history, memory_limit=12, extra_file_content=""):
    # Get local documents context via retriever
    retriever: BaseRetriever = index.as_retriever()
    nodes = retriever.retrieve(query)
    context = " ".join([node.get_text() for node in nodes if isinstance(node, TextNode)])

    # Additional context from uploaded files
    if extra_file_content:
        context += f"\nAdditional context from uploaded file:\n{extra_file_content}"

    # Use RAG retrieve to get both local docs and live news context
    rag_results = rag_retrieve(query, index=index, top_k=3)
    rag_context = "\n".join(rag_results)

    full_context = context + "\n" + rag_context if rag_context else context

    # Manage chat history and summarize if exceeding memory_limit
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
        f"Context from documents and files: {full_context}\n"
        f"Conversation so far:\n{conversation_text}\n"
        "Answer the user's last query in context."
    )
    return query_groq_api(prompt)

def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.strip()

def extract_text_from_image(file):
    image = Image.open(file)
    return pytesseract.image_to_string(image)
