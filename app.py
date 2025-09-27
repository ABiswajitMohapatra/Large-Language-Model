import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import pdfplumber
import time
import re

st.set_page_config(page_title="BiswaLex", page_icon="⚛", layout="wide")

# --- Initialize index and sessions ---
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
if 'current_session' not in st.session_state:
    st.session_state.current_session = []

# --- Mobile-friendly CSS ---
st.markdown("""
<style>
div.message {
    margin: 6px 0;
    font-size: 17px;
    line-height: 1.6;
}
h1 {
    text-align: center;
    color: #FF5722;
    font-size: 28px;
}
span.keyword {
    color: #e91e63;
    font-weight: bold;
}
table {
    border-collapse: collapse;
    margin: 10px 0;
    width: 100%;
}
th, td {
    border: 1px solid #ddd;
    padding: 8px;
    text-align: center;
}
th {
    background-color: #f2f2f2;
}
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.title("B͎i͎s͎w͎a͎L͎e͎x͎⚛")
if st.sidebar.button("New Chat"):
    st.session_state.current_session = []
if st.sidebar.button("Clear Chat"):
    st.session_state.current_session = []

for i, sess in enumerate(st.session_state.sessions):
    if st.sidebar.button(f"Session {i+1}"):
        st.session_state.current_session = sess.copy()

uploaded_file = st.sidebar.file_uploader("", label_visibility="collapsed", type=["pdf"])
if uploaded_file and "uploaded_pdf_text" not in st.session_state:
    extracted_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            extracted_text += page.extract_text() or ""
    st.session_state.uploaded_pdf_text = extracted_text.strip()

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

# --- Render response with formatting ---
def render_response(text):
    # Highlight important keywords
    keywords = ["important", "note", "advantage", "disadvantage", "example", "key points"]
    for kw in keywords:
        text = re.sub(rf"\b{kw}\b", f"<span class='keyword'>{kw}</span>", text, flags=re.IGNORECASE)

    # Heading styles with different colors
    heading_styles = {
        "Immutability": "#673ab7",  # Purple
        "Syntax": "#4CAF50",        # Green
        "Performance": "#2196F3",   # Blue
        "Methods": "#ff9800"        # Orange
    }

    for hd, color in heading_styles.items():
        text = re.sub(
            rf"(?m)^{hd}:",
            f"<h3 style='color:{color}; font-size:20px; font-weight:bold; margin-top:10px;'>{hd}</h3>",
            text
        )

    # Render Markdown + HTML
    st.markdown(f"<div class='message'>{text}</div>", unsafe_allow_html=True)

# --- Display old messages ---
for msg in st.session_state.current_session:
    if msg['role'] == "Agent":
        render_response(f"⚛ {msg['message']}")
    else:
        st.markdown(f"<div class='message' style='text-align:right;'>🧑‍🔬 <b>{msg['message']}</b></div>", unsafe_allow_html=True)

# --- Static header ---
if 'header_rendered' not in st.session_state:
    st.markdown("""
    <h1>What can I help with 😊</h1>
    """, unsafe_allow_html=True)
    st.session_state.header_rendered = True

# --- Chat input ---
prompt = st.chat_input("Say something...", key="main_chat_input")

if prompt:
    add_message("User", prompt)
    st.markdown(f"<div class='message' style='text-align:right;'>🧑‍🔬 <b>{prompt}</b></div>", unsafe_allow_html=True)

    placeholder = st.empty()
    typed_text = ""

    # Typing animation with ⚛
    for char in check_custom_response(prompt.lower()) or chat_with_agent(
        prompt if "uploaded_pdf_text" not in st.session_state else f"Please summarize this document:\n\n{st.session_state.uploaded_pdf_text}",
        st.session_state.index,
        st.session_state.current_session
    ):
        typed_text += char
        placeholder.markdown(f"<div class='message'>⚛ {typed_text}</div>", unsafe_allow_html=True)
        time.sleep(0.002)

    placeholder.empty()

    # Final agent response with styling
    final_answer = check_custom_response(prompt.lower()) or chat_with_agent(
        prompt if "uploaded_pdf_text" not in st.session_state else f"Please summarize this document:\n\n{st.session_state.uploaded_pdf_text}",
        st.session_state.index,
        st.session_state.current_session
    )
    render_response(f"⚛ {final_answer}")
    add_message("Agent", final_answer)

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())

# --- Sidebar helper ---
st.sidebar.markdown(
    "<p style='font-size:14px; color:gray;'>Right-click on the chat input to access emojis and additional features.</p>",
    unsafe_allow_html=True
)
