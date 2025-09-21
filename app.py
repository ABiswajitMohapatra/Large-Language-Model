import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time

st.set_page_config(page_title="BiswaLex", page_icon="⚛️", layout="wide")

# --- Initialize index, sessions, and theme ---
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
if 'current_session' not in st.session_state:
    st.session_state.current_session = []
if 'theme' not in st.session_state:
    st.session_state.theme = 'light'  # default theme is light

# --- Sidebar ---
st.sidebar.title("Settings")
if st.sidebar.button("New Chat"):
    st.session_state.current_session = []
if st.sidebar.button("Clear Chat"):
    st.session_state.current_session = []

# Theme toggle
theme_choice = st.sidebar.radio("Select Theme", ["Light 🌞", "Dark 🌙"])
st.session_state.theme = 'dark' if theme_choice == "Dark 🌙" else 'light'

for i, sess in enumerate(st.session_state.sessions):
    if st.sidebar.button(f"Session {i+1}"):
        st.session_state.current_session = sess.copy()

# --- Theme CSS ---
if st.session_state.theme == 'dark':
    bg_color = "#1E1E1E"
    text_color = "#F5F5F5"
    user_bg = "#3A3A3A"
    agent_bg = "#2E2E2E"
else:
    bg_color = "#FFFFFF"
    text_color = "#000000"
    user_bg = "#a0e7e5"
    agent_bg = "#f0f0f0"

st.markdown(f"""
    <style>
        body {{background-color:{bg_color}; color:{text_color};}}
        .stApp {{background-color:{bg_color}; color:{text_color};}}
        div[role="list"] {{background-color:{bg_color};}}
    </style>
""", unsafe_allow_html=True)

# --- Logo with animation and welcome text ---
st.markdown(f"""
    <div style='text-align: center; margin-bottom: 10px;'>
        <img src='https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.jpg'
             style='width: 100%; max-width: 350px; height: auto; animation: bounce 1s infinite;'>
        <p style='font-size:20px; font-style:italic; color:{text_color};'>Welcome to BiswaLex AI Chat!</p>
    </div>
    <style>
    @keyframes bounce {{
        0%, 100% {{ transform: translateY(0); }}
        50% {{ transform: translateY(-10px); }}
    }}
    </style>
""", unsafe_allow_html=True)

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

    # --- Typing indicator ---
    placeholder = st.empty()
    placeholder.markdown(f"""
        <div style="display:flex; align-items:center; color:gray; font-style:italic;">
            <span style="margin-right:5px;">Agent is typing</span>
            <span class="arrow">&#10148;</span>
        </div>
        <style>
        .arrow {{
            display:inline-block;
            animation: moveArrow 1s infinite linear;
        }}
        @keyframes moveArrow {{
            0% {{ transform: translateX(0) rotate(180deg); }}
            50% {{ transform: translateX(-10px) rotate(180deg); }}
            100% {{ transform: translateX(0) rotate(180deg); }}
        }}
        </style>
    """, unsafe_allow_html=True)
    time.sleep(1)

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    placeholder.empty()

# --- Display messages with scientific emojis and theme-aware colors ---
for msg in st.session_state.current_session:
    if msg['role'] == "Agent":
        st.markdown(
            f"<div style='background-color:{agent_bg}; color:{text_color}; text-align:left; padding:10px; border-radius:10px; margin:5px 0;'>⚛️ {msg['message']}</div>",
            unsafe_allow_html=True
        )
    else:  # User
        st.markdown(
            f"<div style='background-color:{user_bg}; color:{text_color}; text-align:right; padding:10px; border-radius:10px; margin:5px 0;'>🧑‍🔬 {msg['message']}</div>",
            unsafe_allow_html=True
        )

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
