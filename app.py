import streamlit as st
import time
from model import (
    load_documents, create_or_load_index, chat_with_agent,
    extract_text_from_pdf, extract_text_from_image
)

st.set_page_config(page_title="BiswaLex", page_icon="🧑‍💻", layout="wide")

# --- Session state ---
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
if 'current_session' not in st.session_state:
    st.session_state.current_session = []

# --- Sidebar ---
st.sidebar.title("Chats")
if st.sidebar.button("New Chat"):
    st.session_state.current_session = []
if st.sidebar.button("Clear Chat"):
    st.session_state.current_session = []
for i, sess in enumerate(st.session_state.sessions):
    if st.sidebar.button(f"Session {i+1}"):
        st.session_state.current_session = sess.copy()

# --- Header ---
st.markdown(
    """
    <div style='text-align: center; margin-bottom: 10px;'>
        <img src='https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.jpg'
             style='width: 100%; max-width: 350px; height: auto; animation: bounce 1s infinite;'>
        <p style='font-size:20px; font-style:italic; color:#333;'>Welcome to BiswaLex AI Chat!</p>
    </div>
    <style>
    @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-10px); }
    }
    /* Chat message styling */
    .chat-bubble {
        padding: 10px 15px;
        border-radius: 12px;
        margin: 5px;
        display: inline-block;
        max-width: 80%;
        word-wrap: break-word;
    }
    .user-msg {
        background-color: #DCF8C6;
        text-align: right;
        float: right;
        clear: both;
    }
    .agent-msg {
        background-color: #F1F0F0;
        text-align: left;
        float: left;
        clear: both;
    }
    /* Chat input bar styling */
    .chat-input-container {
        display: flex;
        align-items: center;
        border: 1px solid #ccc;
        border-radius: 20px;
        padding: 5px 10px;
        margin-top: 15px;
    }
    .file-upload {
        margin-right: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Utility to store messages ---
def add_message(role, message):
    st.session_state.current_session.append({"role": role, "message": message})

# --- Custom Responses ---
CUSTOM_RESPONSES = {
    "who created you": "I was created by *Biswajit Mohapatra*, my owner 🚀",
    "creator": "My creator is *Biswajit Mohapatra*.",
    "who is your father": "My father is *Biswajit Mohapatra* 👨‍💻",
    "trained": "I was trained and fine-tuned by *Biswajit Mohapatra*.",
    "owner": "My owner is *Biswajit Mohapatra*."
}
def check_custom_response(user_input: str):
    normalized = user_input.lower()
    for keyword, response in CUSTOM_RESPONSES.items():
        if keyword in normalized:
            return response
    return None

# --- Chat Messages Display ---
for msg in st.session_state.current_session:
    role_class = "user-msg" if msg['role'] == "User" else "agent-msg"
    st.markdown(f"<div class='chat-bubble {role_class}'><b>{msg['role']}:</b> {msg['message']}</div>",
                unsafe_allow_html=True)

# --- Chat Input with Upload Button ---
col1, col2 = st.columns([0.1, 0.9])
with col1:
    uploaded_file = st.file_uploader("➕", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")
with col2:
    prompt = st.chat_input("Say something...")

# --- Handle File Upload ---
if uploaded_file:
    extracted_text = ""
    if uploaded_file.type == "application/pdf":
        extracted_text = extract_text_from_pdf(uploaded_file)
    elif uploaded_file.type.startswith("image/"):
        extracted_text = extract_text_from_image(uploaded_file)

    if extracted_text:
        add_message("User", f"📂 Uploaded file: {uploaded_file.name}")
        summary = chat_with_agent(extracted_text, st.session_state.index, st.session_state.current_session)
        add_message("Agent", f"📄 Summary of {uploaded_file.name}: {summary}")

# --- Handle Chat Input ---
if prompt:
    add_message("User", prompt)
    normalized_prompt = prompt.strip().lower()

    placeholder = st.empty()
    placeholder.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
    time.sleep(0.5)

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    placeholder.empty()

# --- Save Session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
