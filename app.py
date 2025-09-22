import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time

st.set_page_config(page_title="BiswaLex", page_icon="⚛", layout="wide")

# --- Custom CSS for chat interface ---
st.markdown("""
<style>
/* Chat container */
.chat-container {
    height: calc(100vh - 250px);
    overflow-y: auto;
    padding: 20px;
    margin-bottom: 60px;
    scroll-behavior: smooth;
    background: white;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

/* Scroll to bottom button */
.scroll-button {
    position: fixed;
    bottom: 100px;
    right: 30px;
    background: #ffffff;
    border: 1px solid #ddd;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    display: none;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    z-index: 1000;
}

/* Message animations */
@keyframes messageAppear {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.message {
    animation: messageAppear 0.3s ease-out;
    margin: 10px 0;
    padding: 10px;
    border-radius: 10px;
}

.user-message {
    background: #f0f2f6;
    margin-left: 20%;
    text-align: right;
}

.agent-message {
    background: #e3f2fd;
    margin-right: 20%;
    text-align: left;
}
</style>

<script>
function initializeChat() {
    const container = document.querySelector('.chat-container');
    const scrollButton = document.querySelector('.scroll-button');

    if (!container || !scrollButton) {
        setTimeout(initializeChat, 100);
        return;
    }

    container.addEventListener('scroll', () => {
        const isScrolledUp = container.scrollTop < container.scrollHeight - container.clientHeight - 100;
        scrollButton.style.display = isScrolledUp ? 'flex' : 'none';
    });

    scrollButton.addEventListener('click', () => {
        container.scrollTo({
            top: container.scrollHeight,
            behavior: 'smooth'
        });
    });

    const autoScrollToBottom = () => {
        container.scrollTo({
            top: container.scrollHeight,
            behavior: 'smooth'
        });
    };

    const observer = new MutationObserver(autoScrollToBottom);
    observer.observe(container, { childList: true, subtree: true });
}

document.addEventListener('DOMContentLoaded', initializeChat);
</script>
""", unsafe_allow_html=True)

# --- Initialize state ---
if "index" not in st.session_state:
    st.session_state.index = create_or_load_index()
if "sessions" not in st.session_state:
    st.session_state.sessions = []
if "current_session" not in st.session_state:
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

# --- Logo with animation ---
st.markdown(
    """
    <div style="text-align: center; margin-bottom: 10px;">
        <img src="https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.jpg"
             style="width: 100%; max-width: 350px; height: auto; animation: bounce 1s infinite;">
        <p style="font-size:20px; font-style:italic; color:#333;">How can I help with!😊</p>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Message handler ---
def add_message(role, message):
    st.session_state.current_session.append({"role": role, "message": message})

# --- Custom responses ---
CUSTOM_RESPONSES = {
    "who created you": "I was created by Biswajit Mohapatra, my owner 🚀",
    # ... (rest of your custom responses)
}

def check_custom_response(user_input: str):
    normalized = user_input.lower()
    for keyword, response in CUSTOM_RESPONSES.items():
        if keyword in normalized:
            return response
    return None

# --- Chat container ---
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

# Display messages
for msg in st.session_state.current_session:
    if msg["role"] == "Agent":
        st.markdown(
            f"""<div class="message agent-message">
                ⚛ <b>{msg["message"]}</b>
            </div>""",
            unsafe_allow_html=True
        )
    else:  # User
        st.markdown(
            f"""<div class="message user-message">
                🧑‍🔬 <b>{msg["message"]}</b>
            </div>""",
            unsafe_allow_html=True
        )

st.markdown('</div>', unsafe_allow_html=True)

# --- Scroll to bottom button ---
st.markdown("""
    <div class="scroll-button">
        <span style="font-size: 20px;">↓</span>
    </div>
""", unsafe_allow_html=True)

# --- Chat input ---
prompt = st.chat_input("Say something...")
if prompt:
    add_message("User", prompt)

    # Typing indicator
    with st.empty():
        st.markdown(
            """
            <div style="display:flex; align-items:center; color:gray; font-style:italic;">
                <span style="margin-right:5px;">Agent is typing</span>
                <span class="arrow">&#10148;</span>
            </div>
            """,
            unsafe_allow_html=True
        )
        time.sleep(1)

        custom_answer = check_custom_response(prompt.lower())
        if custom_answer:
            answer = custom_answer
        else:
            answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)

        add_message("Agent", answer)

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
