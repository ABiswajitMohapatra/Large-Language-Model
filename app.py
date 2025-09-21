import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time
import base64

st.set_page_config(page_title="BiswaLex", page_icon="🧑‍💻", layout="wide")

# --- Initialize index and sessions ---
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
if 'current_session' not in st.session_state:
    st.session_state.current_session = []
if 'user_input' not in st.session_state:
    st.session_state.user_input = ""
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None

# --- Sidebar ---
st.sidebar.title("Chats")
if st.sidebar.button("New Chat"):
    st.session_state.current_session = []
if st.sidebar.button("Clear Chat"):
    st.session_state.current_session = []

for i, sess in enumerate(st.session_state.sessions):
    if st.sidebar.button(f"Session {i+1}"):
        st.session_state.current_session = sess.copy()

# --- Logo with animation and welcome text ---
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
    </style>
    """,
    unsafe_allow_html=True
)

# --- Message handler ---
def add_message(role, message):
    st.session_state.current_session.append({"role": role, "message": message})

# --- Custom responses ---
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

# --- Custom CSS + HTML for GPT-style input ---
st.markdown("""
<style>
.chat-box {
    display: flex;
    align-items: center;
    border: 1px solid #ccc;
    border-radius: 20px;
    padding: 8px 12px;
    background-color: #f9f9f9;
    margin-top: 10px;
}
.chat-box textarea {
    flex-grow: 1;
    border: none;
    outline: none;
    font-size: 16px !important;
    background: transparent;
    resize: none;
    height: 30px;
}
.upload-btn-wrapper {
    position: relative;
    overflow: hidden;
    display: inline-block;
    cursor: pointer;
}
.upload-btn {
    font-size: 22px;
    padding: 0 8px;
    color: #333;
}
.upload-btn-wrapper input[type=file] {
    font-size: 100px;
    position: absolute;
    left: 0;
    top: 0;
    opacity: 0;
    cursor: pointer;
}
</style>
""", unsafe_allow_html=True)

# --- Input form ---
with st.form("chat_form", clear_on_submit=True):
    st.markdown("""
    <div class="chat-box">
      <textarea name="user_input" placeholder="Say something..." rows="1"></textarea>
      <div class="upload-btn-wrapper">
        <span class="upload-btn">➕</span>
        <input type="file" name="file_uploader" accept=".pdf,.png,.jpg,.jpeg"/>
      </div>
    </div>
    """, unsafe_allow_html=True)
    submitted = st.form_submit_button("Send")

# --- Handle chat submission ---
if submitted:
    user_input = st.session_state.get("user_input", "")
    if user_input.strip():
        add_message("User", user_input)
        normalized_prompt = user_input.strip().lower()

        # Typing indicator
        placeholder = st.empty()
        placeholder.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
        time.sleep(0.5)

        custom_answer = check_custom_response(normalized_prompt)
        if custom_answer:
            add_message("Agent", custom_answer)
        else:
            answer = chat_with_agent(user_input, st.session_state.index, st.session_state.current_session)
            add_message("Agent", answer)

        placeholder.empty()

# --- Display messages ---
for msg in st.session_state.current_session:
    if msg['role'] == "Agent":
        st.markdown(
            f"<div style='color:black; text-align:left; margin:5px 0;'>"
            f"<b>Agent:</b> {msg['message']}</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div style='color:black; text-align:right; margin:5px 0;'>"
            f"<b>User:</b> {msg['message']}</div>",
            unsafe_allow_html=True
        )

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
