import streamlit as st
# I'm assuming your model functions are in a file named model.py
from model import load_documents, create_or_load_index, chat_with_agent 
import time

st.set_page_config(page_title="BiswaLex", page_icon="🧑‍💻", layout="wide")

# --- 1. NEW: CUSTOM CSS FOR THE INPUT BAR ---
# This CSS creates the modern, floating input bar with icons
st.markdown("""
<style>
    /* Hides the default Streamlit footer */
    .reportview-container .main footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Main container for our custom input bar */
    .input-container {
        position: fixed;
        bottom: 2rem;
        left: 50%;
        transform: translateX(-50%);
        width: 65%; /* Feel free to adjust width */
        background-color: #FFFFFF;
        border-radius: 2rem;
        padding: 0.5rem 1.25rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        border: 1px solid #E0E0E0;
        display: flex;
        align-items: center;
        z-index: 100;
    }
    .input-container:hover {
        box-shadow: 0 6px 16px rgba(0,0,0,0.2);
    }
    
    /* Styles the text input field to be borderless and clean */
    .input-container .stTextInput > div > div > input {
        border: none;
        background-color: transparent;
        color: #333;
        font-size: 1rem;
        padding-left: 0.5rem;
    }
    .input-container .stTextInput > div > div > input:focus {
        outline: none;
        box-shadow: none;
    }

    /* Styles the upload button to be a simple '+' icon */
    .input-container .stFileUploader > div > button {
        border: none;
        background: none;
        font-size: 1.5rem;
        padding: 0;
        margin: 0;
        color: #808080;
    }
    .input-container .stFileUploader > div > button:hover {
        color: #000;
    }
    /* Hides the "Browse files" text and file name after upload */
    .input-container .stFileUploader label {
        display: none;
    }

    /* Styles the submit button (arrow) */
    .input-container .stButton > button {
        border: none;
        background: #1E90FF; /* A nice blue */
        color: white;
        border-radius: 50%;
        width: 2.5rem;
        height: 2.5rem;
        font-size: 1.25rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        transition: all 0.2s ease-in-out;
    }
    .input-container .stButton > button:hover {
        background: #0073e6;
        transform: scale(1.1);
    }
</style>
""", unsafe_allow_html=True)


# --- 2. YOUR ORIGINAL CODE (UNCHANGED) ---
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

# --- Display messages with left-right alignment ---
# This part is placed before the input logic to ensure messages are displayed first
for msg in st.session_state.current_session:
    if msg['role'] == "Agent":
        st.markdown(
            f"<div style='color:black; text-align:left; margin:5px 0;'>"
            f"<b>Agent:</b> {msg['message']}</div>",
            unsafe_allow_html=True
        )
    else:  # User
        st.markdown(
            f"<div style='color:black; text-align:right; margin:5px 0;'>"
            f"<b>User:</b> {msg['message']}</div>",
            unsafe_allow_html=True
        )

# --- NEW: Adds space at the bottom to prevent the input bar from overlapping content ---
st.markdown("<div style='height: 10rem;'></div>", unsafe_allow_html=True)


# --- 3. THE NEW CUSTOM INPUT BAR ---
# It's wrapped in a form, so pressing Enter submits it.
st.markdown('<div class="input-container">', unsafe_allow_html=True)
with st.form(key="chat_form", clear_on_submit=True):
    # Use columns for layout
    cols = st.columns([1, 18, 2])
    with cols[0]:
        uploaded_file = st.file_uploader(" ", label_visibility="collapsed")
    with cols[1]:
        prompt = st.text_input("Say something...", label_visibility="collapsed", key="prompt_input")
    with cols[2]:
        submit_button = st.form_submit_button("➤")
st.markdown('</div>', unsafe_allow_html=True)


# --- 4. YOUR ORIGINAL LOGIC, NOW TRIGGERED BY THE FORM SUBMIT ---
if submit_button and prompt:
    # This is the same logic you had before
    add_message("User", prompt)
    if uploaded_file:
        # You can add a message to confirm the file upload
        add_message("Agent", f"Processing your file: {uploaded_file.name}")
        # Note: You'll need to update your 'chat_with_agent' function
        # to actually use the 'uploaded_file' if you want it to be analyzed.
    
    normalized_prompt = prompt.strip().lower()
    
    # Typing indicator
    with st.spinner("Agent is typing..."):
        time.sleep(0.5)  # simulate typing

        custom_answer = check_custom_response(normalized_prompt)
        if custom_answer:
            add_message("Agent", custom_answer)
        else:
            answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
            add_message("Agent", answer)
    
    # Rerun the script to display the new messages immediately
    st.experimental_rerun()


# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
