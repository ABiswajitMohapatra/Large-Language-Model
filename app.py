import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time

st.set_page_config(page_title="BiswaLex", page_icon="🧑‍💻", layout="wide")

# --- Initialize index and sessions ---
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

# --- Logo ---
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
    .chat-container {
        display: flex;
        align-items: center;
        max-width: 800px;
        margin: 10px auto;
        border: 1px solid #ccc;
        border-radius: 25px;
        padding: 5px 10px;
        background-color: #f9f9f9;
    }
    .chat-input {
        flex: 1;
        border: none;
        outline: none;
        padding: 10px;
        font-size: 16px;
        border-radius: 25px;
        background-color: #f9f9f9;
    }
    .upload-btn {
        background-color: transparent;
        border: none;
        font-size: 20px;
        cursor: pointer;
        margin-left: 5px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Message handler ---
def add_message(role, message):
    st.session_state.current_session.append({"role": role, "message": message})

CUSTOM_RESPONSES = {
    "who created you": "I was created by Biswajit Mohapatra, my owner 🚀",
    "creator": "My creator is Biswajit Mohapatra.",
    "who is your father": "My father is Biswajit Mohapatra 👨‍💻",
    "father": "My father is Biswajit Mohapatra.",
    "who trained you": "I was trained by Biswajit Mohapatra.",
    "trained": "I was trained and fine-tuned by Biswajit Mohapatra.",
    "who built you": "I was built by Biswajit Mohapatra.",
    "built": "I was built by Biswajit Mohapatra.",
    "who developed you": "I was developed by Biswajit Mohapatra.",
    "developed": "I was developed by Biswajit Mohapatra.",
    "who established you": "I was established by Biswajit Mohapatra.",
    "established": "I was established by Biswajit Mohapatra.",
    "made you": "I was made by Biswajit Mohapatra.",
    "owner": "My owner is Biswajit Mohapatra.",
    "contribution": "The contribution of Biswajit Mohapatra is creating, developing, training, and establishing me 🚀"
}

def check_custom_response(user_input: str):
    normalized = user_input.lower()
    for keyword, response in CUSTOM_RESPONSES.items():
        if keyword in normalized:
            return response
    return None

# --- Custom GPT-style input bar with + upload ---
col1, col2 = st.columns([8,1])
with col1:
    prompt = st.text_input("Ask anything...", key="chat_input")
with col2:
    uploaded_file = st.file_uploader("", label="+", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")

# --- Handle chat input ---
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
    st.experimental_rerun()

# --- Handle uploaded file ---
if uploaded_file:
    add_message("User", f"Uploaded file: {uploaded_file.name}")
    st.experimental_rerun()

# --- Display messages ---
for msg in st.session_state.current_session:
    if msg['role'] == "Agent":
        st.markdown(f"<div style='text-align:left; color:black; margin:5px 0;'><b>Agent:</b> {msg['message']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align:right; color:black; margin:5px 0;'><b>User:</b> {msg['message']}</div>", unsafe_allow_html=True)

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
