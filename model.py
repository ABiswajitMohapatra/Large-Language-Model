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

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
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

def summarize_messages(messages):
    text = ""
    for msg in messages:
        text += f"{msg['role']}: {msg['message']}\n"
    prompt = f"Summarize the following conversation concisely:\n{text}\nSummary:"
    return query_groq_api(prompt)

def rag_retrieve(query: str) -> list[str]:
    return []

def is_simple_query(query: str):
    SIMPLE_QUERIES = [
        "full form", "meaning of", "define", "abbreviation of", "what is",
        "who is", "when was", "where is", "how many"
    ]
    normalized = query.lower()
    return any(keyword in normalized for keyword in SIMPLE_QUERIES)

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

    if is_simple_query(query):
        prompt_text = f"{full_context}\nConversation:\n{conversation_text}\nAnswer concisely:"
    else:
        prompt_text = (
            f"{full_context}\nConversation:\n{conversation_text}\n"
            "Answer the user's last query in context.\n"
            "Format the answer professionally and clearly using:\n"
            "- Bullet points for each key point\n"
            "- Tables for comparisons or numeric data (use Markdown table syntax)\n"
            "- Highlight keywords using **bold** or *italic* text\n"
            "- Provide clear reasoning, analysis, or examples when applicable\n"
            "- Keep language concise and well-structured for readability\n"
        )

    return query_groq_api(prompt_text)

def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.strip()

def extract_text_from_image(file):
    image = Image.open(file)
    return pytesseract.image_to_string(image)
