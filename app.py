import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time

st.set_page_config(page_title="BiswaLex", page_icon="⚛", layout="wide")

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
        <p style='font-size:20px; font-style:italic; color:#333;'>How can i help with!😊</p>
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
    "trained": "I was trained and fine-tuned by Biswajit Mohapatra."
}

def check_custom_response(user_input: str):
    normalized = user_input.lower()
    for keyword, response in CUSTOM_RESPONSES.items():
        if keyword in normalized:
            return response
    return None

# --- Chat input ---
prompt = st.chat_input("Say something...")
if prompt:
    add_message("User", prompt)
    normalized_prompt = prompt.strip().lower()

    # --- Typing indicator with backward arrow animation ---
    placeholder = st.empty()
    placeholder.markdown(
        """
        <div style="display:flex; align-items:center; color:gray; font-style:italic;">
            <span style="margin-right:5px;">Agent is typing</span>
            <span class="arrow">&#10148;</span>
        </div>
        <style>
        .arrow {
            display:inline-block;
            animation: moveArrow 1s infinite linear;
        }
        @keyframes moveArrow {
            0% { transform: translateX(0) rotate(180deg); }
            50% { transform: translateX(-10px) rotate(180deg); }
            100% { transform: translateX(0) rotate(180deg); }
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    time.sleep(1)

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        answer = custom_answer
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)

    placeholder.empty()

    # --- Live typing for Agent ---
    typed_text = ""
    agent_placeholder = st.empty()
    for char in answer:
        typed_text += char
        agent_placeholder.markdown(
            f"<div style='text-align:left; margin:5px 0;'>⚛ <b>{typed_text}</b></div>",
            unsafe_allow_html=True
        )
        time.sleep(0.02)

    add_message("Agent", answer)

# --- Display old messages (skip last Agent, already live-typed) ---
for msg in st.session_state.current_session[:-1]:
    content = msg['message']
    if msg['role'] == "Agent":
        st.markdown(
            f"<div style='text-align:left; margin:5px 0;'>⚛ <b>{content}</b></div>",
            unsafe_allow_html=True
        )
    else:  # User
        st.markdown(
            f"<div style='text-align:right; margin:5px 0;'>🧑‍🔬 <b>{content}</b></div>",
            unsafe_allow_html=True
        )

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
