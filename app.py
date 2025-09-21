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


# st markdown overrides - 
# --- Chat input CSS overrides (add this BEFORE st.chat_input) ---
st.markdown("""
<style>
:root{
  --bar-width: min(860px, 94vw);
  --bar-bottom: 14px;
}

/* keep space so fixed bar doesn't overlap content */
.main .block-container{ padding-bottom: 110px !important; }

/* pin the chat input to bottom & style it */
[data-testid="stChatInput"]{
  position: fixed !important;
  left: 50% !important;
  transform: translateX(-50%) !important;
  bottom: var(--bar-bottom) !important;
  width: var(--bar-width) !important;
  z-index: 9998 !important;
}

/* rounded white bar look */
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] input{
  background:#ffffff !important;
  color:#111827 !important;
  border:1px solid #e5e7eb !important;
  border-radius:28px !important;
  box-shadow:0 1px 2px rgba(0,0,0,0.04) !important;
  padding:12px 16px !important;
  /* extra padding so pseudo-icons don't overlap text */
  padding-left: 56px !important;
  padding-right: 64px !important;
}
[data-testid="stChatInput"] ::placeholder{ color:#9ca3af !important; }
[data-testid="stChatInput"] :is(textarea,input):focus{
  outline:none !important; box-shadow:none !important;
}

/* draw a small '+' circle on the LEFT (visual only) */
[data-testid="stChatInput"]::before{
  content: "+";
  position: absolute;
  left: 12px; bottom: 50%;
  transform: translateY(50%);
  width: 34px; height: 34px; border-radius: 50%;
  display:flex; align-items:center; justify-content:center;
  background:#ffffff; color:#111827;
  border:1px solid #e5e7eb;
  font-weight:600; font-size:20px;
  box-shadow:0 1px 2px rgba(0,0,0,0.04);
  pointer-events: none; /* purely visual */
}

/* draw a blue action badge on the RIGHT (visual only) */
[data-testid="stChatInput"]::after{
  content: "⏵";
  position: absolute;
  right: 16px; bottom: 50%;
  transform: translateY(50%);
  width: 36px; height: 36px; border-radius:50%;
  background:#e6f0ff; color:#ffffff;
  display:flex; align-items:center; justify-content:center;
  box-shadow: none;
  font-weight:700; font-size:12px;
}
[data-testid="stChatInput"]::after{
  /* inner blue circle via shadow trick */
  box-shadow: inset 0 0 0 10px #0a66ff;
  color: transparent; /* hide ⏵ text color in outer circle */
}
</style>
""", unsafe_allow_html=True)





# --- Chat input ---
prompt = st.chat_input("Ask anthing...")

if prompt:
    add_message("User", prompt)
    normalized_prompt = prompt.strip().lower()

    # Typing indicator
    placeholder = st.empty()
    placeholder.markdown(
        "<p style='color:gray; font-style:italic;'>Agent is typing...</p>",
        unsafe_allow_html=True
    )
    time.sleep(0.5)  # simulate typing

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    placeholder.empty()  # Remove typing indicator

# --- Display messages with left-right alignment ---
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

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())



