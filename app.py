import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time

st.set_page_config(page_title="BiswaLex", page_icon="⚛", layout="wide")

# --- Initialize index and sessions ---
if "index" not in st.session_state:
    st.session_state.index = create_or_load_index()
if "sessions" not in st.session_state:
    st.session_state.sessions = []
if "current_session" not in st.session_state:
    st.session_state.current_session = []
if "show_uploader" not in st.session_state:
    st.session_state.show_uploader = False

# --- Custom CSS ---
st.markdown("""
    <style>
    .uploadedFile {
        border: 1px solid #ccc;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
    .stChatInput {
        padding-right: 40px;
    }
    </style>
""", unsafe_allow_html=True)

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
    <div style="text-align: center; margin-bottom: 10px;">
        <img src="https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.jpg"
             style="width: 100%; max-width: 350px; height: auto; animation: bounce 1s infinite;">
        <p style="font-size:20px; font-style:italic; color:#333;">How can I help with!😊</p>
    </div>
    <style>
    @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-10px); }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Message handler ---
def add_message(role, message):
    st.session_state.current_session.append({"role": role, "message": message})

def process_uploaded_file(uploaded_file):
    try:
        if uploaded_file.type == "text/plain":
            content = uploaded_file.getvalue().decode()
        elif uploaded_file.type == "application/pdf":
            # Add your PDF processing logic here
            content = "PDF content processed"  # placeholder
        else:
            content = f"File type {uploaded_file.type} processing not implemented"
        return content
    except Exception as e:
        return f"Error processing file: {str(e)}"

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

# --- Chat interface with upload functionality ---
chat_container = st.container()

# Chat input with upload icon
prompt = st.chat_input(
    "Say something...",
    key="chat_input",
    icon=":material_upload:"
)

# Handle file upload when icon is clicked
if prompt is None:  # Icon clicked but no text entered
    st.session_state.show_uploader = True

if st.session_state.show_uploader:
    uploaded_file = st.file_uploader(
        "Upload your document",
        type=["txt", "pdf", "doc", "docx"],
        key="file_uploader"
    )
    if uploaded_file:
        content = process_uploaded_file(uploaded_file)
        st.success(f"File {uploaded_file.name} uploaded successfully!")
        add_message("User", f"Uploaded file: {uploaded_file.name}")
        add_message("User", f"File content: {content[:500]}...")  # Show first 500 chars
        st.session_state.show_uploader = False

# Handle text input
if prompt:
    add_message("User", prompt)
    normalized_prompt = prompt.strip().lower()

    # Typing indicator
    placeholder = st.empty()
    placeholder.markdown(
        """
        <div style="display:flex; align-items:center; color:gray; font-style:italic;">
            <span style="margin-right:5px;">Agent is typing</span>
            <span class="arrow">&#10148;</span>
        </div>
        <style>
        .arrow {
            display:inline-block;
            animation: moveArrow 1s infinite linear;
        }
        @keyframes moveArrow {
            0% { transform: translateX(0) rotate(180deg); }
            50% { transform: translateX(-10px) rotate(180deg); }
            100% { transform: translateX(0) rotate(180deg); }
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    time.sleep(1)  # simulate typing

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    placeholder.empty()  # Remove typing indicator

# --- Display messages ---
with chat_container:
    for msg in st.session_state.current_session:
        content = msg["message"]
        if msg["role"] == "Agent":
            st.markdown(
                f"<div style='text-align:left; margin:5px 0;'>⚛ <b>{content}</b></div>",
                unsafe_allow_html=True
            )
        else:  # User
            st.markdown(
                f"<div style='text-align:right; margin:5px 0;'>🧑‍🔬 <b>{content}</b></div>",
                unsafe_allow_html=True
            )

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())


