import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# Convert secrets to dict
cred_dict = dict(st.secrets["FIREBASE"])

# Fix for multiline private_key if needed (only if you see \n instead of actual newlines)
if "\\n" in cred_dict["private_key"]:
    cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")

# Initialize Firebase app if not already done
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_dict)
        st.session_state.firebase_app = firebase_admin.initialize_app(cred)
    else:
        st.session_state.firebase_app = firebase_admin.get_app()
except Exception as e:
    st.error(f"Firebase initialization failed: {e}")

# Set up Firestore client for use in the app (add this if you use Firestore)
try:
    if "db" not in st.session_state:
        st.session_state.db = firestore.client()
except Exception as e:
    st.error(f"Firestore client initialization failed: {e}")


# --- Initialize index and sessions ---
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'current_session' not in st.session_state:
    st.session_state.current_session = []

# --- Sidebar: Load history ---
st.sidebar.title("Chat History")
chats_ref = st.session_state.db.collection("chat_history")
all_chats = chats_ref.stream()
saved_sessions = []
for chat_doc in all_chats:
    saved_sessions.append(chat_doc.to_dict())

for i, sess in enumerate(saved_sessions):
    if st.sidebar.button(f"Session {i+1}"):
        st.session_state.current_session = sess["messages"]

if st.sidebar.button("Clear Chat"):
    st.session_state.current_session = []

# --- Logo ---
st.markdown(
    """
    <div style='text-align: center; margin-bottom: 10px;'>
        <img src='https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.jpg'
             style='width: 100%; max-width: 350px; height: auto; animation: bounce 1s infinite;'>
        <p style='font-size:20px; font-style:italic; color:#333;'>How can I help you! 😊</p>
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

# --- Chat handler ---
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
    placeholder.markdown(
        """
        <div style="display:flex; align-items:center; color:gray; font-style:italic;">
            <span style="margin-right:5px;">Agent is typing</span>
            <span class="arrow">&#10148;</span>
        </div>
        <style>
        .arrow { display:inline-block; animation: moveArrow 1s infinite linear; }
        @keyframes moveArrow {
            0% { transform: translateX(0) rotate(180deg); }
            50% { transform: translateX(-10px) rotate(180deg); }
            100% { transform: translateX(0) rotate(180deg); }
        }
        </style>
        """,
        unsafe_allow_html=True
    )
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

# --- Save to Firebase ---
if st.sidebar.button("Save Session"):
    session_id = str(uuid.uuid4())
    chats_ref.document(session_id).set({"messages": st.session_state.current_session})
    st.sidebar.success("Session saved to Firebase!")


