import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time
import uuid
import urllib.parse

st.set_page_config(page_title="BiswaLex", page_icon="⚛️", layout="wide")

# --- Initialize index and sessions ---
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
if 'all_sessions' not in st.session_state:
    st.session_state.all_sessions = {}

# --- Get session ID from URL query parameters ---
query_params = st.experimental_get_query_params()
if "session" in query_params:
    session_id = query_params["session"][0]
    st.session_state.session_id = session_id
    if session_id in st.session_state.all_sessions:
        st.session_state.current_session = st.session_state.all_sessions[session_id].copy()
    else:
        st.session_state.current_session = []
else:
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
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

# --- Logo and welcome ---
st.markdown(
    """
    <div style='text-align: center; margin-bottom: 10px;'>
        <img src='https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.jpg'
             style='width: 100%; max-width: 350px; height: auto; animation: bounce 1s infinite;'>
        <p style='font-size:20px; font-style:italic; color:#333;'>How can I help with!😊</p>
    </div>
    <style>
    @keyframes bounce {0%,100%{transform:translateY(0);}50%{transform:translateY(-10px);}}
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

    placeholder = st.empty()
    placeholder.markdown(
        """
        <div style="display:flex; align-items:center; color:gray; font-style:italic;">
            <span style="margin-right:5px;">Agent is typing</span>
            <span class="arrow">&#10148;</span>
        </div>
        <style>
        .arrow { display:inline-block; animation: moveArrow 1s infinite linear; }
        @keyframes moveArrow {0% {transform:translateX(0) rotate(180deg);}50% {transform:translateX(-10px) rotate(180deg);}100% {transform:translateX(0) rotate(180deg);}}
        </style>
        """,
        unsafe_allow_html=True
    )
    time.sleep(1)

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    placeholder.empty()

# --- Display chat messages ---
for msg in st.session_state.current_session:
    content = msg['message']
    if msg['role'] == "Agent":
        st.markdown(f"<div style='text-align:left; margin:5px 0;'>⚛️ <b>{content}</b></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align:right; margin:5px 0;'>🧑‍🔬 <b>{content}</b></div>", unsafe_allow_html=True)

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
    st.session_state.all_sessions[st.session_state.session_id] = st.session_state.current_session.copy()

# --- Shareable link with buttons ---
shareable_link = f"{st.get_url()}?session={st.session_state.session_id}"
encoded_link = urllib.parse.quote(shareable_link, safe=':/?=&')

st.sidebar.markdown(f"**Share this chat:** [Click Here]({shareable_link})")
st.sidebar.markdown(f"[Share on WhatsApp](https://wa.me/?text={encoded_link})")
st.sidebar.markdown(f"[Share on Telegram](https://t.me/share/url?url={encoded_link}&text=Check%20out%20this%20chat!)")
st.sidebar.markdown(f"[Share via Email](mailto:?subject=Check%20this%20chat&body={encoded_link})")
