import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time

st.set_page_config(
    page_title="BiswaLex",
    page_icon="🧑‍💻",
    layout="wide"
)

# --- Initialize index and sessions ---
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()

if 'sessions' not in st.session_state:
    st.session_state.sessions = []

if 'current_session' not in st.session_state:
    st.session_state.current_session = []

if 'typing' not in st.session_state:
    st.session_state.typing = False

# --- Sidebar: Chat History ---
st.sidebar.title("Chats")
if st.sidebar.button("New Chat"):
    st.session_state.current_session = []

if st.sidebar.button("Clear Chat"):
    st.session_state.current_session = []

for i, sess in enumerate(st.session_state.sessions):
    if st.sidebar.button(f"Session {i+1}"):
        st.session_state.current_session = sess.copy()

# --- Main Chat Area: Logo ---
st.markdown(
    """
    <div style='text-align: center; margin-bottom: 20px;'>
        <img src='https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.jpg'
             style='width: 100%; max-width: 350px; height: auto;'>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Message handler ---
def add_message(role, message):
    st.session_state.current_session.append({
        "role": role,
        "message": message
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

# --- Input handling with Enter key and auto-focus ---
st.markdown("""
<script>
const inputBox = window.parent.document.querySelector('input[type=text]');
if (inputBox) {
    inputBox.focus();
    inputBox.addEventListener("keypress", function(event) {
        if (event.key === "Enter") {
            event.preventDefault();
            const sendButton = window.parent.document.querySelector('button[kind=primary]');
            if (sendButton) sendButton.click();
        }
    });
}
</script>
""", unsafe_allow_html=True)

prompt = st.chat_input("Say something...")
if prompt:
    add_message("User", prompt)
    normalized_prompt = prompt.strip().lower()

    # Typing indicator
    st.session_state.typing = True
    st.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
    st.experimental_rerun()  # Force UI update to show typing

    time.sleep(0.5)  # simulate typing delay

    # Check for custom responses first
    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    st.session_state.typing = False

# --- Display messages with black text and auto-scroll ---
for msg in st.session_state.current_session:
    st.markdown(
        f"<p style='color:black; font-size:16px; margin:5px 0;'><b>{msg['role']}:</b> {msg['message']}</p>",
        unsafe_allow_html=True
    )

# Auto-scroll to bottom
st.markdown("""
<script>
var chatContainer = window.parent.document.querySelector('main');
chatContainer.scrollTo(0, chatContainer.scrollHeight);
</script>
""", unsafe_allow_html=True)

# --- Save current session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
