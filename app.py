import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
from io import BytesIO
import tempfile
import os

st.set_page_config(page_title="BiswaLex", page_icon="🧑‍💻", layout="wide")

# --- Initialize index and sessions ---
if "index" not in st.session_state:
    st.session_state.index = create_or_load_index()
if "sessions" not in st.session_state:
    st.session_state.sessions = []
if "current_session" not in st.session_state:
    st.session_state.current_session = []

# --- Sidebar ---
st.sidebar.title("Chats")
if st.sidebar.button("New Chat"):
    st.session_state.current_session = []
if st.sidebar.button("Clear Chat"):
    st.session_state.sessions = []
    st.session_state.current_session = []
if st.sidebar.button("Save Session"):
    st.session_state.sessions.append(st.session_state.current_session)
    st.success("Session saved!")

# --- Title ---
st.title("Welcome to BiswaLex AI Chat!")

# --- Display previous chat history ---
for msg in st.session_state.current_session:
    if msg["role"] == "user":
        st.chat_message("user").markdown(msg["content"])
    else:
        st.chat_message("assistant").markdown(msg["content"])

# --- Custom CSS for Chat Input ---
st.markdown("""
    <style>
    .stFileUploader {
        display: none;
    }
    .chat-bar {
        display: flex;
        align-items: center;
        border: 1px solid #ccc;
        border-radius: 20px;
        padding: 5px 10px;
        background-color: #fff;
    }
    .chat-input {
        flex: 1;
        border: none;
        outline: none;
        font-size: 16px;
        padding: 8px;
    }
    .plus-btn {
        font-size: 24px;
        font-weight: bold;
        margin-right: 10px;
        cursor: pointer;
    }
    </style>
""", unsafe_allow_html=True)

# --- Custom Chat Input with + Upload ---
col1, col2 = st.columns([0.1, 0.9])

with col1:
    upload = st.file_uploader("", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")

with col2:
    user_input = st.chat_input("Say something...")

# --- Handle Upload ---
if upload is not None:
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(upload.read())
        temp_path = tmp_file.name

    # Load file and update index
    docs = load_documents(temp_path)
    st.session_state.index = create_or_load_index(docs)
    os.remove(temp_path)

    response = "✅ File uploaded and processed! You can now ask questions about it."
    st.chat_message("assistant").markdown(response)
    st.session_state.current_session.append({"role": "assistant", "content": response})

# --- Handle User Input ---
if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.current_session.append({"role": "user", "content": user_input})

    response = chat_with_agent(st.session_state.index, user_input)
    st.chat_message("assistant").markdown(response)
    st.session_state.current_session.append({"role": "assistant", "content": response})
