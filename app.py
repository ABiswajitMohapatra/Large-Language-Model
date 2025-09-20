import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
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
    </style>
    """,
    unsafe_allow_html=True
)

def add_message(role, message):
    st.session_state.current_session.append({"role": role, "message": message})

CUSTOM_RESPONSES = {
    "who created you": "I was created by Biswajit Mohapatra, my owner 🚀",
    "creator": "My creator is Biswajit Mohapatra.",
    "who is your father": "My father is Biswajit Mohapatra 👨‍💻",
    "father": "My father is Biswajit Mohapatra.",
    "who trained you": "I was trained by Biswajit Mohapatra.",
    "trained": "I was trained and fine-tuned by Biswajit Mohapatra.",
    "who built you": "I was built by Biswajit Mohapatra.",
    "built": "I was built by Biswajit Mohapatra.",
    "who developed you": "I was developed by Biswajit Mohapatra.",
    "developed": "I was developed by Biswajit Mohapatra.",
    "who established you": "I was established by Biswajit Mohapatra.",
    "established": "I was established by Biswajit Mohapatra.",
    "made you": "I was made by Biswajit Mohapatra.",
    "owner": "My owner is Biswajit Mohapatra.",
    "contribution": "The contribution of Biswajit Mohapatra is creating, developing, training, and establishing me 🚀"
}

def check_custom_response(user_input: str):
    normalized = user_input.lower()
    for keyword, response in CUSTOM_RESPONSES.items():
        if keyword in normalized:
            return response
    return None

# --- Custom search/chat input with upload + send buttons ---
st.markdown(
    """
    <style>
    .chat-input-container {
        display: flex;
        align-items: center;
        max-width: 700px;
        margin-bottom: 20px;
    }
    .upload-btn {
        background: #50dbc0;
        border-radius: 50%;
        width: 36px;
        height: 36px;
        border: none;
        color: white;
        font-size: 24px;
        cursor: pointer;
        margin-right: 10px;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    .chat-text-input {
        flex-grow: 1;
        border: 1.5px solid #50dbc0;
        border-radius: 30px;
        padding: 12px 20px;
        font-size: 18px;
        outline: none;
        transition: box-shadow 0.2s;
    }
    .chat-text-input:focus {
        box-shadow: 0 0 10px #50dbc0;
    }
    .send-btn {
        background: transparent;
        border: none;
        cursor: pointer;
        font-size: 28px;
        color: #50dbc0;
        margin-left: 10px;
        user-select: none;
    }
    input[type="file"] {
        display: none;
    }
    </style>
    <div class="chat-input-container">
        <label for="file-uploader" class="upload-btn" title="Upload File">+</label>
        <input type="file" id="file-uploader" />
        <input type="text" id="chat-input" class="chat-text-input" placeholder="Say something..." />
        <button id="send-btn" class="send-btn" title="Send">&#10148;</button>
    </div>
    <script>
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const fileUploader = document.getElementById('file-uploader');

    sendBtn.onclick = () => {
        const val = input.value.trim();
        if (val) {
            window.parent.postMessage({ type: 'sendMessage', message: val }, '*');
            input.value = '';
        }
    };
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendBtn.click();
            e.preventDefault();
        }
    });
    fileUploader.onchange = () => {
        if (fileUploader.files.length > 0) {
            const reader = new FileReader();
            reader.onload = function(e) {
                window.parent.postMessage({ type: 'fileUpload', 
                  filename: fileUploader.files[0].name, 
                  data: e.target.result }, '*');
            };
            reader.readAsDataURL(fileUploader.files[0]);
        }
    };
    </script>
    """,
    unsafe_allow_html=True,
)

# Listen for messages posted from the embedded script using Streamlit's experimental_event system
def handle_js_messages():
    event = st.experimental_get_query_params().get("message_event")
    # Cannot actually listen to postMessage directly in Streamlit, requires advanced workaround or component library
    # So instead, fall back to below input methods

handle_js_messages()

# Use text_input and file uploader widgets for interactivity while hiding them and syncing with the custom bar if needed
prompt = st.text_input("", key="hidden_prompt", label_visibility="collapsed")
uploaded_file = st.file_uploader("", key="hidden_file_uploader", label_visibility="collapsed")

# React to user input - process prompt whenever it changes (not on every keystroke)
if prompt and prompt.strip() != "":
    user_input = prompt.strip()
    add_message("User", user_input)
    norm_prompt = user_input.lower()

    placeholder = st.empty()
    placeholder.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
    time.sleep(0.5)

    custom_answer = check_custom_response(norm_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(user_input, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)
    placeholder.empty()
    st.session_state.hidden_prompt = ""

# Handle file upload through hidden uploader
if uploaded_file is not None:
    st.success(f"Uploaded file: {uploaded_file.name}")
    # Process uploaded file if needed

# Show messages with styles
for msg in st.session_state.current_session:
    style = "left" if msg['role'] == "Agent" else "right"
    st.markdown(
        f'<div style="color:black; text-align:{style}; margin:5px 0;">'
        f'<b>{msg["role"]}:</b> {msg["message"]}</div>',
        unsafe_allow_html=True
    )

# Sidebar save session button
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
