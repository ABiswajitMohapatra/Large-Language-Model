import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time

st.set_page_config(page_title="BiswaLex", page_icon="⚛️", layout="wide")

if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
if 'current_session' not in st.session_state:
    st.session_state.current_session = []

# --- Sidebar ---
st.sidebar.title("Chats⚛️")
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
        <p style='font-size:20px; font-style:italic; color:#333;'>How can i help with!😊</p>
    </div>
    <style>
    @keyframes bounce {0%, 100% { transform: translateY(0); }50% { transform: translateY(-10px);}}
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

# --- Display old messages with copy button ---
for msg in st.session_state.current_session:
    content = msg['message']
    if msg['role'] == "Agent":
        col1, col2 = st.columns([0.95, 0.05])
        with col1:
            st.markdown(f"⚛️ **{content}**", unsafe_allow_html=True)
        with col2:
            if st.button("📋", key=f"copy_{content}"):
                st.clipboard_set(content)
    else:
        st.markdown(f"🧑‍🔬 **{content}**", unsafe_allow_html=True)

# --- Chat input ---
prompt = st.chat_input("Say something...")
if prompt:
    add_message("User", prompt)
    st.markdown(f"🧑‍🔬 **{prompt}**", unsafe_allow_html=True)

    placeholder = st.empty()
    typed_text = ""
    final_answer = check_custom_response(prompt.lower()) or chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)

    # Typing animation
    for char in final_answer:
        typed_text += char
        placeholder.markdown(f"⚛️ **{typed_text}**", unsafe_allow_html=True)
        time.sleep(0.002)

    add_message("Agent", final_answer)

    # Show copy button for the final message
    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        st.markdown(f"⚛️ **{final_answer}**", unsafe_allow_html=True)
    with col2:
        if st.button("📋", key=f"copy_final_{prompt}"):
            st.clipboard_set(final_answer)

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())

# --- Sidebar helper ---
st.sidebar.markdown(
    "<p style='font-size:14px; color:gray;'>Right-click on the chat input to access emojis and additional features.</p>",
    unsafe_allow_html=True
)
