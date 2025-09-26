# app.py
import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import pdfplumber
import time

st.set_page_config(page_title="BiswaLex", page_icon="⚛", layout="wide")

if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
if 'current_session' not in st.session_state:
    st.session_state.current_session = []

# --- Mobile-friendly CSS ---
st.markdown("""
<style>
div.message { margin: 2px 0; font-size: 17px; }
div[data-testid="stHorizontalBlock"] { margin-bottom: 0px; padding-bottom: 0px; }
@media only screen and (max-width: 600px) { section[data-testid="stSidebar"] { max-width: 250px; } }
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

# --- PDF upload (multiple) ---
uploaded_files = st.sidebar.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)
if uploaded_files:
    if "uploaded_pdf_texts" not in st.session_state:
        st.session_state.uploaded_pdf_texts = []
    for file in uploaded_files:
        text = ""
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        if text.strip() not in st.session_state.uploaded_pdf_texts:
            st.session_state.uploaded_pdf_texts.append(text.strip())

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

GREETING_RESPONSES = {
    "hi": "Hello! How’s your day going?",
    "hey": "Hey! How can I help you today?",
    "hello": "Hi there! What’s up?",
    "good morning": "Good morning! Hope you have a wonderful day ahead.",
    "good night": "Good night! Sleep well and have sweet dreams.",
    "good evening": "Good evening! How was your day?"
}

def check_greeting_response(user_input: str):
    normalized = user_input.lower()
    for keyword, response in GREETING_RESPONSES.items():
        if keyword in normalized:
            return response
    return None

# --- Display old messages ---
for msg in st.session_state.current_session:
    if msg['role'] == "Agent":
        st.markdown(f"<div class='message' style='text-align:left;'>⚛ {msg['message']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='message' style='text-align:right;'>🧑‍🔬 {msg['message']}</div>", unsafe_allow_html=True)

# --- Static header ---
if 'header_rendered' not in st.session_state:
    st.markdown("<div style='text-align:center; font-size:28px; font-weight:bold; color:#b0b0b0; margin-bottom:20px;'>What can I help with😊</div>", unsafe_allow_html=True)
    st.session_state.header_rendered = True

# --- Chat input ---
prompt = st.chat_input("Say something...", key="main_chat_input")

if prompt:
    add_message("User", prompt)
    st.markdown(f"<div class='message' style='text-align:right;'>🧑‍🔬 {prompt}</div>", unsafe_allow_html=True)

    placeholder = st.empty()
    final_answer = check_custom_response(prompt.lower()) or check_greeting_response(prompt.lower())

    # --- PDF / Document processing ---
    if not final_answer:
        if ("pdf" in prompt.lower() or "file" in prompt.lower() or "document" in prompt.lower()) \
           and "uploaded_pdf_texts" in st.session_state:

            if st.session_state.uploaded_pdf_texts:
                combined_pdf_text = "\n\n".join(st.session_state.uploaded_pdf_texts)
                final_answer = chat_with_agent(
                    f"Please provide a structured summary of all uploaded documents (use bullets, tables, bold where needed):\n\n{combined_pdf_text}",
                    st.session_state.index,
                    st.session_state.current_session
                )
            else:
                final_answer = "⚛ Sorry, no readable text was found in your PDFs."
        else:
            final_answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)

    typed_text = ""
    for char in final_answer:
        typed_text += char
        placeholder.markdown(f"⚛ {typed_text}", unsafe_allow_html=False)
        time.sleep(0.001)

    add_message("Agent", final_answer)

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())

st.sidebar.markdown("<p style='font-size:14px; color:gray;'>Right-click on the chat input to access emojis and additional features.</p>", unsafe_allow_html=True)
