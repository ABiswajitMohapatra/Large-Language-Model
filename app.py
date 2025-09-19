import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent

st.set_page_config(page_title="Agentic AI Chat", page_icon="🧑‍💻", layout="wide")

if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []  # list of sessions
if 'current_session' not in st.session_state:
    st.session_state.current_session = []

# --- Sidebar: Chat History ---
st.sidebar.title("Chats")
if st.sidebar.button("New Chat"):
    st.session_state.current_session = []

# List previous sessions
for i, sess in enumerate(st.session_state.sessions):
    if st.sidebar.button(f"Session {i+1}"):
        st.session_state.current_session = sess.copy()

# --- Main Chat Area ---
st.markdown("<h1 style='text-align: center; color: #4F8BF9;'>Agentic AI Chat</h1>", unsafe_allow_html=True)

def add_message(role, message, color):
    st.session_state.current_session.append({"role": role, "message": message, "color": color})

prompt = st.chat_input("Say something to Agent...")

if prompt:
    add_message("User", prompt, "#118ab2")
    normalized_prompt = prompt.strip().lower()

    if normalized_prompt in ["exit", "quit"]:
        add_message("Agent", "Goodbye!", "#FFD166")
    elif normalized_prompt in ["hi", "hello", "hey", "greetings"]:
        add_message("Agent", "Hello! How can I assist you today?", "#06d6a0")
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer, "#06d6a0")

# Display current chat
for msg in st.session_state.current_session:
    st.markdown(
        f"<div style='background-color: {msg['color']}; padding:10px; border-radius:10px; margin-bottom:5px;'>"
        f"<b>{msg['role']}:</b> {msg['message']}</div>", unsafe_allow_html=True
    )

# Save current session when user closes or switches chat
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
