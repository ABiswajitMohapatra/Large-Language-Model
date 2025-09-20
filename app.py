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

# --- Message handler ---
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

# --- Custom chat input bar with embedded upload icon ---
st.markdown(
    """
    <style>
    .custom-bar {
        display: flex;
        align-items: center;
        border: 1.5px solid #50dbc0;
        border-radius: 30px;
        padding: 8px 12px;
        background: #F3F7FA;
        margin-bottom: 10px;
        max-width: 700px;
    }
    .custom-bar input[type="text"] {
        border: none;
        outline: none;
        flex-grow: 1;
        font-size: 18px;
        background: transparent;
        padding-left: 10px;
    }
    .upload-btn {
        background: #50dbc0;
        color: white;
        border-radius: 50%;
        border: none;
        width: 36px;
        height: 36px;
        font-size: 24px;
        cursor: pointer;
        margin-right: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .send-btn {
        background: transparent;
        border: none;
        cursor: pointer;
        font-size: 24px;
        color: #50dbc0;
        padding: 0;
    }
    </style>
    <div class="custom-bar">
        <label for="file-uploader" class="upload-btn" title="Upload File">+</label>
        <input type="file" id="file-uploader" style="display:none;" />
        <input type="text" id="custom-chat-input" placeholder="Say something..." />
        <button class="send-btn" title="Send">&#8594;</button>
    </div>
    """,
    unsafe_allow_html=True,
)

# JavaScript interaction bridge for file input and send button
js_code = """
<script>
    const inputBox = document.getElementById('custom-chat-input');
    const sendBtn = document.querySelector('.send-btn');
    const fileUploader = document.getElementById('file-uploader');
    const uploadBtn = document.querySelector('label[for="file-uploader"]');

    sendBtn.onclick = () => {
        const text = inputBox.value.trim();
        if (text !== "") {
            const evt = new CustomEvent("streamlit:custom_input", { detail: text });
            window.dispatchEvent(evt);
            inputBox.value = "";
        }
    };

    inputBox.addEventListener("keypress", function(event) {
        if (event.key === "Enter") {
            event.preventDefault();
            sendBtn.click();
        }
    });

    fileUploader.onchange = () => {
        if (fileUploader.files.length > 0) {
            const fileName = fileUploader.files[0].name;
            const evt = new CustomEvent("streamlit:file_upload", { detail: fileName });
            window.dispatchEvent(evt);
            // Optional: handle the file further using Streamlit's file uploader widget if desired
        }
    };
</script>
"""
st.components.v1.html(js_code, height=0, width=0)

# Helper flags and input tracking
if 'custom_input_value' not in st.session_state:
    st.session_state.custom_input_value = ""

uploaded_file_name = None

# Streamlit event listener emulation
def handle_custom_input():
    input_val = st.experimental_get_query_params().get("custom_input", [""])[0]
    if input_val:
        st.session_state.custom_input_value = input_val

def handle_file_upload():
    uploaded_filename = st.experimental_get_query_params().get("uploaded_file", [""])[0]
    if uploaded_filename:
        st.session_state.uploaded_file_name = uploaded_filename

# Capturing events via query params (alternative, limited)
# Real integration requires Streamlit advanced features or workarounds; as workaround, let's do:

# Fallback: Use regular Streamlit input and file uploader for interaction binding
prompt = st.text_input("Say something...", key="custom_input_value")

uploaded_file = st.file_uploader("Upload your file", type=["txt", "pdf", "docx", "jpg", "png"])

if prompt and prompt.strip() != "":
    user_input = prompt.strip()
    add_message("User", user_input)
    normalized_prompt = user_input.lower()

    placeholder = st.empty()
    placeholder.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
    time.sleep(0.5)

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(user_input, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)
    placeholder.empty()
    st.session_state.custom_input_value = ""  # clear input box

if uploaded_file is not None:
    st.success(f"Uploaded file: {uploaded_file.name}")
    # You can add processing logic here for the uploaded file if needed

# --- Display messages with left-right alignment ---
for msg in st.session_state.current_session:
    if msg['role'] == "Agent":
        st.markdown(
            f"<div style='color:black; text-align:left; margin:5px 0;'>"
            f"<b>Agent:</b> {msg['message']}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div style='color:black; text-align:right; margin:5px 0;'>"
            f"<b>User:</b> {msg['message']}</div>",
            unsafe_allow_html=True,
        )

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
