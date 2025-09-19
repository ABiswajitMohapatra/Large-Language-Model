import os
import pickle
from groq import Groq
from llama_index.core.schema import TextNode
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

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
    return SimpleDirectoryReader('Sanjukta').load_data()

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
    chat_completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return chat_completion.choices[0].message.content

def summarize_messages(messages):
    """Summarize a list of messages into a short summary."""
    text = ""
    for msg in messages:
        text += f"{msg['role']}: {msg['message']}\n"
    prompt = f"Summarize the following conversation concisely:\n{text}\nSummary:"
    return query_groq_api(prompt)

def chat_with_agent(query, index, chat_history, memory_limit=12):
    retriever: BaseRetriever = index.as_retriever()
    nodes = retriever.retrieve(query)
    context = " ".join([node.get_text() for node in nodes if isinstance(node, TextNode)])

    # Split history into old and recent messages
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

    prompt = (
        f"Context from documents: {context}\n"
        f"Conversation so far:\n{conversation_text}\n"
        "Answer the user's last query in context."
    )
    return query_groq_api(prompt)
