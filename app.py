import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import PyPDF2
import time

st.set_page_config(page_title="BiswaLex", page_icon="⚛", layout="wide")

# --- Initialize index and sessions ---
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
if 'current_session' not in st.session_state:
    st.session_state.current_session = None

# --- Sidebar: PDF uploader ---
uploaded_file = st.sidebar.file_uploader(
    label="Upload PDF",
    label_visibility="collapsed",
    type=["pdf"]
)

if uploaded_file is not None:
    st.sidebar.success(f"Uploaded: {uploaded_file.name}")

# Optional: load PDF text for chat context
pdf_text = ""
if uploaded_file:
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    for page in pdf_reader.pages:
        pdf_text += page.extract_text() + "\n"

# --- Main chat interface ---
st.title("BiswaLex Chat")

if uploaded_file:
    with st.expander("PDF Content Preview", expanded=False):
        st.text_area("Content", pdf_text, height=300)

user_input = st.text_input("Type your message here...")

if st.button("Send") and user_input:
    if st.session_state.current_session is None:
        st.session_state.current_session = []

    response = chat_with_agent(user_input, st.session_state.index)
    st.session_state.current_session.append({"user": user_input, "bot": response})

# --- Display chat history ---
if st.session_state.current_session:
    for chat in st.session_state.current_session:
        st.markdown(f"**You:** {chat['user']}")
        st.markdown(f"**BiswaLex:** {chat['bot']}")
        st.markdown("---")
