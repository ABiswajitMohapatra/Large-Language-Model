import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time

st.set_page_config(page_title="BiswaLex", page_icon="⚛", layout="wide")

# Add custom CSS for scroll functionality at the top
st.markdown("""
    <style>
    .scroll-indicator {
        position: fixed;
        right: 20px;
        top: 50%;
        background: rgba(255, 255, 255, 0.9);
        padding: 10px;
        border-radius: 50%;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        cursor: pointer;
        display: none;
        z-index: 1000;
    }
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
        scroll-behavior: smooth;
    }
    .chat-container::-webkit-scrollbar {
        width: 6px;
    }
    .chat-container::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 3px;
    }
    </style>

    <script>
    document.addEventListener('DOMContentLoaded', function() {
        const container = document.querySelector('.chat-container');
        const indicator = document.querySelector('.scroll-indicator');

        if (container) {
            container.addEventListener('scroll', function() {
                if (container.scrollHeight > container.clientHeight) {
                    indicator.style.display = 'block';
                } else {
                    indicator.style.display = 'none';
                }
            });
        }
    });
    </script>
""", unsafe_allow_html=True)

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
    <div style="text-align: center; margin-bottom: 10px;">
        <img src="https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.jpg"
             style="width: 100%; max-width: 350px; height: auto; animation: bounce 1s infinite;">
        <p style="font-size:20px; font-style:italic; color:#333;">How can i help with!😊</p>
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

# Create chat container with scroll functionality
chat_container = st.container()

with chat_container:
    # Start chat container div
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)

    # Add scroll indicator
    st.markdown("""
        <div class="scroll-indicator">
            <span style="font-size: 24px;">⬇️</span>
        </div>
    """, unsafe_allow_html=True)

    # Display messages
    for msg in st.session_state.current_session:
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

    # Close chat container div
    st.markdown('</div>', unsafe_allow_html=True)

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
    time.sleep(1)  # simulate typing

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    placeholder.empty()  # Remove typing indicator

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
