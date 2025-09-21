import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent, extract_text_from_pdf, extract_text_from_image
import time

st.set_page_config(page_title="BiswaLex", page_icon="🧑‍💻", layout="wide")

# --- Initialize index and sessions ---
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
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

# --- Logo with animation and welcome text ---
st.markdown(
    """
    <div style='text-align: center; margin-bottom: 10px;'>
        <img src='https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.jpg'
             style='width: 100%; max-width: 350px; height: auto; animation: bounce 1s infinite;'>
        <p style='font-size:20px; font-style:italic; color:#333;'>Welcome to BiswaLex AI Chat!</p>
    </div>
    <style>
    @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-10px); }
    }
    .chat-input-wrapper {
        display: flex;
        align-items: center;
        justify-content: center;
        max-width: 640px;
        margin: auto;
        margin-bottom: 10px;
    }
    .chat-input {
        flex: 1;
        font-size: 16px;
        padding: 12px 16px;
        border-radius: 24px;
        border: 1px solid #ccc;
        outline: none;
    }
    .upload-button {
        margin-left: 8px;
        font-size: 28px;
        cursor: pointer;
        user-select: none;
        color: #555;
    }
    input[type="file"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- State to hold uploaded file content ---
if 'uploaded_content' not in st.session_state:
    st.session_state.uploaded_content = ""

# --- File uploader with custom UI ---
file_uploaded = st.file_uploader("", type=["pdf", "png", "jpg", "jpeg"], label_visibility='collapsed')

if file_uploaded:
    if file_uploaded.type == "application/pdf":
        st.session_state.uploaded_content = extract_text_from_pdf(file_uploaded)
    elif "image" in file_uploaded.type:
        st.session_state.uploaded_content = extract_text_from_image(file_uploaded)
    else:
        st.session_state.uploaded_content = ""
    if st.session_state.uploaded_content:
        st.markdown("**Extracted content from uploaded file:**")
        st.write(st.session_state.uploaded_content[:500] + ("..." if len(st.session_state.uploaded_content) > 500 else ""))

# --- Chat input and upload bar ---
with st.form(key="chat_form", clear_on_submit=True):
    text_message = st.text_input("Say something...", key="chat_input", max_chars=500)

    # Upload button acting as label for hidden file uploader, style visible only on hover or focus
    submit_button = st.form_submit_button("Send")

if submit_button and text_message:
    add_message = lambda role, msg: st.session_state.current_session.append({"role": role, "message": msg})
    add_message("User", text_message)
    normalized_prompt = text_message.strip().lower()

    placeholder = st.empty()
    placeholder.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
    time.sleep(0.5)

    from model import check_custom_response
    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        from model import chat_with_agent
        answer = chat_with_agent(text_message, st.session_state.index, st.session_state.current_session, extra_file_content=st.session_state.uploaded_content)
        add_message("Agent", answer)

    placeholder.empty()

# --- Messages display ---
for msg in st.session_state.current_session:
    if msg['role'] == "Agent":
        st.markdown(f"<div style='text-align:left; margin:6px 0;'><b>Agent:</b> {msg['message']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align:right; margin:6px 0;'><b>User:</b> {msg['message']}</div>", unsafe_allow_html=True)

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
