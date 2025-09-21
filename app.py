import streamlit as st
import time

st.set_page_config(page_title="BiswaLex", page_icon="🧑‍💻", layout="wide")

# --- Session state for chat ---
if "current_session" not in st.session_state:
    st.session_state.current_session = []

# --- Function to add message ---
def add_message(role, message):
    st.session_state.current_session.append({"role": role, "message": message})

# --- Custom GPT-style input with + upload ---
st.markdown(
    """
    <style>
    .chat-container {
        display: flex;
        align-items: center;
        max-width: 800px;
        margin: 10px auto;
        border: 1px solid #ccc;
        border-radius: 25px;
        padding: 5px 10px;
        background-color: #f9f9f9;
    }
    .chat-input {
        flex: 1;
        border: none;
        outline: none;
        padding: 10px;
        font-size: 16px;
        border-radius: 25px;
        background-color: #f9f9f9;
    }
    .upload-btn {
        background-color: transparent;
        border: none;
        font-size: 20px;
        cursor: pointer;
        margin-left: 5px;
    }
    </style>

    <div class="chat-container">
        <input id="chat_input" class="chat-input" type="text" placeholder="Ask anything...">
        <label for="file_upload" class="upload-btn">+</label>
        <input type="file" id="file_upload" style="display:none;">
    </div>
    """,
    unsafe_allow_html=True
)

# --- Capture user input and uploaded file ---
user_input = st.text_input("", key="hidden_input")  # hidden Streamlit input to capture value
uploaded_file = st.file_uploader("", key="hidden_file", label_visibility="collapsed")

if user_input:
    add_message("User", user_input)
    # Simulate agent typing
    placeholder = st.empty()
    placeholder.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
    time.sleep(0.5)
    add_message("Agent", f"You said: {user_input}")  # Replace with your chat_with_agent()
    placeholder.empty()
    st.experimental_rerun()

if uploaded_file:
    add_message("User", f"Uploaded file: {uploaded_file.name}")
    st.experimental_rerun()

# --- Display chat messages ---
for msg in st.session_state.current_session:
    if msg['role'] == "Agent":
        st.markdown(f"<div style='text-align:left; color:black; margin:5px 0;'><b>Agent:</b> {msg['message']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align:right; color:black; margin:5px 0;'><b>User:</b> {msg['message']}</div>", unsafe_allow_html=True)
