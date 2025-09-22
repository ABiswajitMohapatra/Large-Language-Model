import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time
import uuid
import firebase_admin
from firebase_admin import credentials, firestore

st.set_page_config(page_title="BiswaLex", page_icon="⚛", layout="wide")

# --- Initialize Firebase ---
if not firebase_admin._apps:
    cred_dict = {
        "type": st.secrets["FIREBASE"]["type"],
        "project_id": st.secrets["FIREBASE"]["project_id"],
        "private_key_id": st.secrets["FIREBASE"]["private_key_id"],
        "private_key": st.secrets["FIREBASE"]["private_key"].replace("\\n", "\n"),
        "client_email": st.secrets["FIREBASE"]["client_email"],
        "client_id": st.secrets["FIREBASE"]["client_id"],
        "auth_uri": st.secrets["FIREBASE"]["auth_uri"],
        "token_uri": st.secrets["FIREBASE"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["FIREBASE"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["FIREBASE"]["client_x509_cert_url"]
    }
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- Initialize index and sessions ---
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
if 'current_session' not in st.session_state:
    st.session_state.current_session = []
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

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
st.markdown("""
<div style='text-align: center; margin-bottom: 10px;'>
    <img src='https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.jpg'
         style='width: 100%; max-width: 350px; height: auto; animation: bounce 1s infinite;'>
    <p style='font-size:20px; font-style:italic; color:#333;'>How can i help with!😊</p>
</div>
<style>
@keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
</style>
""", unsafe_allow_html=True)

# --- Message handler ---
def add_message(role, message):
    st.session_state.current_session.append({"role": role, "message": message})

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

# --- Chat input ---
prompt = st.chat_input("Say something...")
if prompt:
    add_message("User", prompt)
    normalized_prompt = prompt.strip().lower()

    placeholder = st.empty()
    placeholder.markdown("""
    <div style="display:flex; align-items:center; color:gray; font-style:italic;">
        <span style="margin-right:5px;">Agent is typing</span>
        <span class="arrow">&#10148;</span>
    </div>
    <style>
    .arrow { display:inline-block; animation: moveArrow 1s infinite linear; }
    @keyframes moveArrow { 0% { transform: translateX(0) rotate(180deg); } 50% { transform: translateX(-10px) rotate(180deg); } 100% { transform: translateX(0) rotate(180deg); } }
    </style>
    """, unsafe_allow_html=True)
    time.sleep(1)

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    placeholder.empty()

# --- Display messages ---
for msg in st.session_state.current_session:
    content = msg['message']
    if msg['role'] == "Agent":
        st.markdown(f"<div style='text-align:left; margin:5px 0;'>⚛ <b>{content}</b></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align:right; margin:5px 0;'>🧑‍🔬 <b>{content}</b></div>", unsafe_allow_html=True)

# --- Save session to Firebase ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())
    # Save in Firebase
    db.collection("chat_sessions").document(st.session_state.session_id).set({
        "messages": st.session_state.current_session
    })

# --- Generate shareable link ---
shareable_link = f"{st.request.url}?session={st.session_state.session_id}"
st.sidebar.markdown(f"**Share this chat:** [Click Here]({shareable_link})")

# --- Share buttons ---
whatsapp_link = f"https://wa.me/?text={shareable_link}"
st.sidebar.markdown(f"[Share on WhatsApp]({whatsapp_link})")
telegram_link = f"https://t.me/share/url?url={shareable_link}&text=Check%20out%20this%20chat!"
st.sidebar.markdown(f"[Share on Telegram]({telegram_link})")
email_link = f"mailto:?subject=Check%20this%20chat&body={shareable_link}"
st.sidebar.markdown(f"[Share via Email]({email_link})")
