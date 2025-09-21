import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time

# --- Page Configuration ---
st.set_page_config(page_title="BiswaLex", page_icon="🧑‍💻", layout="wide")

# --- Custom CSS ---
st.markdown(
    """
    <style>
    .stTextInput > div > div > input {
        border-radius: 20px;
    }
    .stButton button {
        border-radius: 20px;
        padding: 0.5rem 1rem;
    }
    div[data-testid="stFileUploader"] {
        width: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True
)

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

# --- Custom responses dictionary ---
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

# --- Chat input with upload icon ---
col1, col2 = st.columns([6, 1])

with col1:
    prompt = st.text_input(
        "Say something...",
        key="chat_input",
        placeholder="Type your message here...",
        label_visibility="collapsed",
        icon=":material_send:"  # Corrected icon syntax
    )

with col2:
    uploaded_file = st.file_uploader(
        "Upload file",
        label_visibility="collapsed"
    )

if prompt:
    add_message("User", prompt)
    normalized_prompt = prompt.strip().lower()

    # Typing indicator
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

# --- Display messages with enhanced styling ---
for msg in st.session_state.current_session:
    if msg["role"] == "Agent":
        st.markdown(
            f"""
            <div style='display: flex; align-items: start; margin: 5px 0;'>
                <div style='background-color: #f0f2f6; padding: 10px; border-radius: 10px; max-width: 80%;'>
                    <b>Agent:</b> {msg["message"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:  # User
        st.markdown(
            f"""
            <div style='display: flex; justify-content: flex-end; margin: 5px 0;'>
                <div style='background-color: #e6f3ff; padding: 10px; border-radius: 10px; max-width: 80%;'>
                    <b>You:</b> {msg["message"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

# --- Save session button ---
with st.sidebar:
    if st.button(
        "Save Session",
        type="primary",
        help="Save current chat session"
    ):
        if st.session_state.current_session and st.session_state.current_session not in st.session_state.sessions:
            st.session_state.sessions.append(st.session_state.current_session.copy())
            st.success("Session saved successfully!")

# --- Footer ---
st.markdown(
    """
    <div style='position: fixed; bottom: 0; left: 0; right: 0; background-color: #f0f2f6; padding: 10px; text-align: center;'>
        <p style='margin: 0; font-size: 12px;'>Powered by BiswaLex AI © 2024</p>
    </div>
    """,
    unsafe_allow_html=True
)
