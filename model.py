import os
import pickle
import time
from groq import Groq
from llama_index.core.schema import TextNode
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
import pdfplumber
from PIL import Image
import pytesseract

# --- Groq API Setup ---
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


# --- Load Documents ---
def load_documents():
    folder = "Sanjukta"
    if os.path.exists(folder):
        return SimpleDirectoryReader(folder).load_data()
    else:
        print(f"⚠ Folder '{folder}' not found. Continuing with empty documents.")
        return []


# --- Create or Load Index ---
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


# --- Query Groq API ---
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


# --- Summarize Messages ---
def summarize_messages(messages):
    text = ""
    for msg in messages:
        text += f"{msg['role']}: {msg['message']}\n"

    prompt = f"Summarize the following conversation concisely:\n{text}\nSummary:"
    return query_groq_api(prompt)


# --- (Optional) RAG Retrieve ---
def rag_retrieve(query: str) -> list[str]:
    return []


# --- Chat with Agent ---
def chat_with_agent(query, index, chat_history, memory_limit=12, extra_file_content=""):
    retriever: BaseRetriever = index.as_retriever()
    nodes = retriever.retrieve(query)
    context = " ".join([node.get_text() for node in nodes if isinstance(node, TextNode)])

    if extra_file_content:
        context += f"\nAdditional context from uploaded file:\n{extra_file_content}"

    rag_results = rag_retrieve(query)
    rag_context = "\n".join(rag_results)
    full_context = context + "\n" + rag_context if rag_context else context

    # Conversation memory handling
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

    # --- Natural greetings ---
    if query.strip().lower() in ["hi", "hello", "hey", "good morning", "good evening"]:
        prompt = (
            f"Conversation so far:\n{conversation_text}\n"
            "Reply naturally to the user's greeting without extra formatting."
        )
    else:
        # --- Formatted answers with proper headings ---
          prompt = (
            f"Context from documents and files: {full_context}\n"
            f"Conversation so far:\n{conversation_text}\n"
            "Answer the user's last query in context.\n\n"
            "⚠ Formatting rules:\n"
            "- Start with a main heading using Markdown (## Heading).\n"
            "- Use **bold sub-headings** for sections, each on a new line.\n"
            "- Use • bullet points, each on a new line.\n"
          )


    return query_groq_api(prompt)


# --- Extract Text from PDF ---
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.strip()


# --- Extract Text from Image ---
def extract_text_from_image(file):
    image = Image.open(file)
    return pytesseract.image_to_string(image)

