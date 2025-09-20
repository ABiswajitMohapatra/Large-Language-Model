import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time
from streamlit.components.v1 import html

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

# --- Custom Chat Input with "+" inside ---
user_input_html = """
<style>
.chat-container {
    display: flex;
    width: 100%;
    max-width: 600px;
    margin: 10px auto;
}
.chat-input {
    flex: 1;
    padding: 10px 12px;
    border-radius: 25px;
    border: 2px solid #ccc;
    font-size: 16px;
    outline: none;
}
.upload-btn {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    border: 2px solid #333;
    display: flex;
    justify-content: center;
    align-items: center;
    margin-left: 8px;
    cursor: pointer;
    font-size: 24px;
    background-color: #fff;
}
.upload-btn:hover {
    background-color: #f0f0f0;
}
</style>

<div class="chat-container">
    <input type="text" id="chatInput" class="chat-input" placeholder="Say something...">
    <label class="upload-btn" for="fileUpload">+</label>
    <input type="file" id="fileUpload" style="display:none">
</div>

<script>
const input = document.getElementById('chatInput');
input.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        const value = input.value;
        if (value.trim() !== '') {
            window.parent.postMessage({isStreamlitMessage: true, type: 'USER_INPUT', value: value}, '*');
            input.value = '';
        }
    }
});
</script>
"""

html(user_input_html, height=60)

# --- Handle messages from custom HTML input ---
import streamlit.components.v1 as components

if "user_input" not in st.session_state:
    st.session_state.user_input = ""

message = st.experimental_get_query_params().get("USER_INPUT")
if message:
    st.session_state.user_input = message[0]

if st.session_state.user_input:
    add_message("User", st.session_state.user_input)
    normalized_prompt = st.session_state.user_input.strip().lower()

    placeholder = st.empty()
    placeholder.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
    time.sleep(0.5)

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(st.session_state.user_input, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    placeholder.empty()
    st.session_state.user_input = ""

# --- Display messages with left-right alignment ---
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
