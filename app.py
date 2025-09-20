import streamlit as st
import time
from model import (
    load_documents, create_or_load_index, chat_with_agent,
    extract_text_from_pdf, extract_text_from_image
)

st.set_page_config(page_title="BiswaLex", page_icon="🧑‍💻", layout="wide")

if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
if 'current_session' not in st.session_state:
    st.session_state.current_session = []
if 'uploaded_content' not in st.session_state:
    st.session_state.uploaded_content = ""

st.sidebar.title("Chats")
if st.sidebar.button("New Chat"):
    st.session_state.current_session = []
if st.sidebar.button("Clear Chat"):
    st.session_state.current_session = []

for i, sess in enumerate(st.session_state.sessions):
    if st.sidebar.button(f"Session {i+1}"):
        st.session_state.current_session = sess.copy()

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

    /* --- Style the chat input bar with + icon --- */
    .stChatInputContainer {
        position: relative;
    }
    .upload-btn-wrapper {
        position: absolute;
        left: 10px;
        top: 50%;
        transform: translateY(-50%);
    }
    .upload-btn-wrapper input[type=file] {
        font-size: 100px;
        position: absolute;
        left: 0;
        top: 0;
        opacity: 0;
        cursor: pointer;
    }
    .upload-btn {
        background: none;
        border: none;
        font-size: 22px;
        cursor: pointer;
        color: gray;
    }
    </style>
    """, unsafe_allow_html=True
)

def add_message(role, message):
    st.session_state.current_session.append({"role": role, "message": message})

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

# --- Custom Input Bar with "+" inside ---
st.markdown(
    """
    <div class="stChatInputContainer">
        <div class="upload-btn-wrapper">
            <button class="upload-btn">+</button>
            <input type="file" id="fileUpload" accept=".pdf,.png,.jpg,.jpeg">
        </div>
    </div>
    """, unsafe_allow_html=True
)

# normal chat input (aligned with our + button)
prompt = st.chat_input("Say something...")

# Handle upload via st.file_uploader (hidden, controlled by CSS)
uploaded_file = st.file_uploader("hidden uploader", type=["pdf","png","jpg","jpeg"], label_visibility="collapsed")
if uploaded_file:
    if uploaded_file.type == "application/pdf":
        st.session_state.uploaded_content = extract_text_from_pdf(uploaded_file)
    elif uploaded_file.type.startswith("image/"):
        st.session_state.uploaded_content = extract_text_from_image(uploaded_file)

# --- Chat Section ---
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
        context = prompt
        if st.session_state.uploaded_content:
            context += "\n\n" + st.session_state.uploaded_content
        answer = chat_with_agent(context, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    placeholder.empty()

for msg in st.session_state.current_session:
    align = "left" if msg['role'] == "Agent" else "right"
    st.markdown(
        f"<div style='color:black; text-align:{align}; margin:5px 0;'><b>{msg['role']}:</b> {msg['message']}</div>",
        unsafe_allow_html=True
    )

if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
