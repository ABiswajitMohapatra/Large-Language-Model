import os
import pickle
from groq import Groq
from llama_index.core.schema import TextNode
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
import pdfplumber
from PIL import Image
import pytesseract
import requests

# --- Groq client setup ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# --- Custom Embedding ---
class CustomEmbedding(BaseEmbedding):
    def _get_query_embedding(self, query: str) -> list[float]:
        return [0.0] * 512
    async def _aget_query_embedding(self, query: str) -> list[float]:
        return [0.0] * 512
    def _get_text_embedding(self, text: str) -> list[float]:
        return [0.0] * 512

# --- Load documents ---
def load_documents():
    folder = "Sanjukta"
    if os.path.exists(folder):
        return SimpleDirectoryReader(folder).load_data()
    else:
        print(f"⚠ Folder '{folder}' not found. Continuing with empty documents.")
        return []

# --- Index creation/loading ---
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

# --- Summarize messages ---
def summarize_messages(messages):
    text = ""
    for msg in messages:
        text += f"{msg['role']}: {msg['message']}\n"
    prompt = f"Summarize the following conversation concisely:\n{text}\nSummary:"
    return query_groq_api(prompt)

# --- RAG: Fetch latest info (World News + Wikipedia) ---
WORLD_NEWS_API_KEY = "3e44dc7d70e54273a555227f01790315"

def fetch_latest_info(query: str) -> list[str]:
    snippets = []

    # --- World News API ---
    try:
        url = "https://worldnewsapi.com/api/v1/search-news"
        params = {
            "q": query,
            "language": "en",
            "apiKey": WORLD_NEWS_API_KEY
        }
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            for article in data.get("articles", []):
                title = article.get("title", "")
                content = article.get("content", "")
                if title or content:
                    snippets.append(f"{title}: {content}")
        else:
            snippets.append(f"⚠ Could not fetch latest news, status code: {response.status_code}")
    except Exception as e:
        snippets.append(f"⚠ Could not fetch latest news: {str(e)}")

    # --- Wikipedia snippet fallback ---
    try:
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
        r = requests.get(wiki_url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            extract = data.get("extract", "")
            if extract:
                snippets.append(extract)
    except Exception as e:
        snippets.append(f"⚠ Wikipedia fetch failed: {str(e)}")

    return snippets

def rag_retrieve(query: str) -> list[str]:
    return fetch_latest_info(query)

# --- Chat with agent incorporating RAG ---
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
        f"You are an expert assistant. Use the context provided from documents, uploaded files, and latest retrieved information to answer the user's query.\n\n"
        f"Context: {full_context}\n\n"
        f"Conversation so far:\n{conversation_text}\n"
        "Answer the user's last query using the most recent and up-to-date information."
    )
    return query_groq_api(prompt)

# --- PDF / image text extraction ---
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.strip()

def extract_text_from_image(file):
    image = Image.open(file)
    return pytesseract.image_to_string(image)
