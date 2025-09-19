import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent

st.set_page_config(
    page_title="MohapAI",
    page_icon="🧑‍💻",
    layout="wide"
)

# Initialize index and sessions
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()

if 'sessions' not in st.session_state:
    st.session_state.sessions = []

if 'current_session' not in st.session_state:
    st.session_state.current_session = []

# --- Sidebar: Chat History ---
st.sidebar.title("Chats")
if st.sidebar.button("New Chat"):
    st.session_state.current_session = []

for i, sess in enumerate(st.session_state.sessions):
    if st.sidebar.button(f"Session {i+1}"):
        st.session_state.current_session = sess.copy()

# --- Main Chat Area ---
st.markdown(
    """
    <div style='text-align: center; margin-bottom: 20px;'>
        <img src='https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.png.png' width='180'>
    </div>
    """,
    unsafe_allow_html=True
)


def add_message(role, message, color):
    st.session_state.current_session.append({
        "role": role,
        "message": message,
        "color": color
    })

# --- Custom responses dictionary ---
CUSTOM_RESPONSES = {
    "who created you": "I was created by **Biswajit Mohapatra**, my owner 🚀",
    "creator": "My creator is **Biswajit Mohapatra**.",
    "who is your father": "My father is **Biswajit Mohapatra** 👨‍💻",
    "father": "My father is **Biswajit Mohapatra**.",
    "who trained you": "I was trained by **Biswajit Mohapatra**.",
    "trained": "I was trained and fine-tuned by **Biswajit Mohapatra**.",
    "who built you": "I was built by **Biswajit Mohapatra**.",
    "built": "I was built by **Biswajit Mohapatra**.",
    "who developed you": "I was developed by **Biswajit Mohapatra**.",
    "developed": "I was developed by **Biswajit Mohapatra**.",
    "who established you": "I was established by **Biswajit Mohapatra**.",
    "established": "I was established by **Biswajit Mohapatra**.",
    "made you": "I was made by **Biswajit Mohapatra**.",
    "owner": "My owner is **Biswajit Mohapatra**.",
    "contribution": "The contribution of **Biswajit Mohapatra** is creating, developing, training, and establishing me 🚀"
}

def check_custom_response(user_input: str):
    normalized = user_input.lower()
    for keyword, response in CUSTOM_RESPONSES.items():
        if keyword in normalized:
            return response
    return None

# --- Input handling ---
prompt = st.chat_input("Say something to Agent...")
if prompt:
    add_message("User", prompt, "#118ab2")
    normalized_prompt = prompt.strip().lower()

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer, "#ef476f")
    elif normalized_prompt in ["exit", "quit"]:
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
        f"<b>{msg['role']}:</b> {msg['message']}</div>",
        unsafe_allow_html=True
    )

# Save current session
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())

