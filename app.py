import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time
from supabase import create_client

# --- Streamlit page config ---
st.set_page_config(page_title="BiswaLex", page_icon="⚛️", layout="wide")

# --- Supabase connection ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Initialize index and sessions ---
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'current_session' not in st.session_state:
    st.session_state.current_session = []

# --- Helper functions for Supabase chat storage ---
def save_message(user, message):
    supabase.table("chat_messages").insert({"user": user, "message": message}).execute()

def get_messages():
    response = supabase.table("chat_messages").select("*").order("timestamp", desc=True).execute()
    return response.data

# --- Add message to session ---
def add_message(role, message):
    st.session_state.current_session.append({"role": role, "message": message})
    save_message(role, message)  # persist to Supabase

# --- Custom responses ---
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

# --- Sidebar for chat history ---
st.sidebar.title("Chats")
if st.sidebar.button("New Chat"):
    st.session_state.current_session = []

# Load chat history from Supabase
if "chat_history" not in st.session_state:
    st.session_state.chat_history = get_messages()

# Display Supabase chat history in sidebar
st.sidebar.subheader("Chat History")
for msg in reversed(st.session_state.chat_history):
    st.sidebar.write(f"{msg['user']}: {msg['message']}")

if st.sidebar.button("Refresh History"):
    st.session_state.chat_history = get_messages()

# --- Logo with animation ---
st.markdown(
    """
    <div style='text-align: center; margin-bottom: 10px;'>
        <img src='https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.jpg'
             style='width: 100%; max-width: 350px; height: auto; animation: bounce 1s infinite;'>
        <p style='font-size:20px; font-style:italic; color:#333;'>How can I help you! 😊</p>
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

# --- Chat input ---
prompt = st.chat_input("Say something...")
if prompt:
    add_message("User", prompt)
    normalized_prompt = prompt.strip().lower()

    # Typing indicator
    placeholder = st.empty()
    placeholder.markdown(
        """
        <div style="display:flex; align-items:center; color:gray; font-style:italic;">
            <span style="margin-right:5px;">Agent is typing</span>
            <span class="arrow">&#10148;</span>
        </div>
        <style>
        .arrow { display:inline-block; animation: moveArrow 1s infinite linear; }
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

    placeholder.empty()  # remove typing indicator

# --- Display chat messages ---
for msg in st.session_state.current_session:
    content = msg['message']
    if msg['role'] == "Agent":
        st.markdown(f"<div style='text-align:left; margin:5px 0;'>⚛️ <b>{content}</b></div>",
                    unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align:right; margin:5px 0;'>🧑‍🔬 <b>{content}</b></div>",
                    unsafe_allow_html=True)

# --- Save session to session_state (optional) ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.get("sessions", []):
        if "sessions" not in st.session_state:
            st.session_state.sessions = []
        st.session_state.sessions.append(st.session_state.current_session.copy())
