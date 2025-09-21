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
st.markdown("""
<style>
:root{
  --bar-width: min(860px, 94vw);
  --bar-bottom: 14px;
}

/* give space so the fixed bar doesn't cover content; remove if not sticky */
.main .block-container{ padding-bottom: 110px !important; }

/* pin & size the chat input (optional – comment these 5 lines if you don't want sticky) */
[data-testid="stChatInput"]{
  position: fixed !important;
  left: 50% !important;
  transform: translateX(-50%) !important;
  bottom: var(--bar-bottom) !important;
  width: var(--bar-width) !important;
  z-index: 9998 !important;
}

/* ----- make the container a proper anchor for pseudo-elements ----- */
[data-testid="stChatInput"]{
  position: relative !important;         /* <— IMPORTANT so ::before/::after show */
  border-radius: 28px !important;
}
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] input{
  background:#ffffff !important;
  color:#111827 !important;
  border:1px solid #e5e7eb !important;
  border-radius: 28px !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
  padding: 12px 16px !important;

  /* leave room for the + (left), mic + badge (right) */
  padding-left: 56px !important;
  padding-right: 92px !important;
}
[data-testid="stChatInput"] ::placeholder{ color:#9ca3af !important; }
[data-testid="stChatInput"] :is(textarea,input):focus{
  outline: none !important;
  box-shadow: none !important;           /* remove blue glow */
}

/* ----- LEFT: + upload (visual) ----- */
[data-testid="stChatInput"]::before{
  content: "+";
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 36px; height: 36px;
  border-radius: 50%;
  display:flex; align-items:center; justify-content:center;
  background:#fff; color:#111827;
  border:1px solid #e5e7eb;
  font-weight: 600; font-size: 20px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  pointer-events: none; /* purely visual */
}

/* ----- RIGHT: mic (visual) ----- */
[data-testid="stChatInput"] .mic-decor{
  position: absolute;
  right: 60px;                           /* sits between text and blue badge */
  top: 50%;
  transform: translateY(-50%);
  font-size: 18px; color:#111827;
  pointer-events: none;
}

/* inject the mic span */
[data-testid="stChatInput"]::marker{ content: ""; } /* silence some browsers */
</style>
""", unsafe_allow_html=True)

# tiny injection to render the mic glyph (no HTML in chat_input itself)
st.markdown(
    "<span class='mic-decor'>🎤</span>",
    unsafe_allow_html=True
)

# SECOND CSS block for the blue badge (kept separate to avoid minification quirks)
st.markdown("""
<style>
/* ----- RIGHT: blue action badge (visual) ----- */
[data-testid="stChatInput"]::after{
  content: "";
  position: absolute;
  right: 12px; top: 50%;
  transform: translateY(-50%);
  width: 36px; height: 36px; border-radius: 50%;
  background: #e6f0ff;
  display:flex; align-items:center; justify-content:center;
}
[data-testid="stChatInput"]::after{
  /* inner blue circle via inset shadow */
  box-shadow: inset 0 0 0 10px #0a66ff;
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




