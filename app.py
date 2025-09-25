import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import PyPDF2
import time

st.set_page_config(page_title="BiswaLex", page_icon="⚛", layout="wide")

# --- Initialize index and sessions ---
if 'index' not in st.session_state:
    st.session_state.index = create_or_load_index()
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
if 'current_session' not in st.session_state:
    st.session_state.current_session = []

# --- Mobile-friendly CSS ---
st.markdown("""
<style>
/* Reduce vertical spacing of messages */
div.message {
    margin: 2px 0;
    font-size: 17px;
}

/* Adjust chat input block */
div[data-testid="stHorizontalBlock"] {
    margin-bottom: 0px;
    padding-bottom: 0px;
}

/* Optional: slightly smaller sidebar on mobile */
@media only screen and (max-width: 600px) {
    section[data-testid="stSidebar"] {
        max-width: 250px;
    }
}
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.title("B͎i͎s͎w͎a͎L͎e͎x͎⚛")
if st.sidebar.button("New Chat"):
    st.session_state.current_session = []
if st.sidebar.button("Clear Chat"):
    st.session_state.current_session = []

for i, sess in enumerate(st.session_state.sessions):
    if st.sidebar.button(f"Session {i+1}"):
        st.session_state.current_session = sess.copy()

uploaded_file = st.sidebar.file_uploader(
    "Upload a file",
    label_visibility="collapsed",
    type=["pdf", "jpg", "jpeg", "png", "doc", "docx", "ppt", "pptx"]
)
if uploaded_file and "uploaded_pdf_text" not in st.session_state:
    if uploaded_file.type == "application/pdf":
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        extracted_text = ""
        for page in pdf_reader.pages:
            extracted_text += page.extract_text() or ""
        st.session_state.uploaded_pdf_text = extracted_text.strip()

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

# --- Display old messages ---
for msg in st.session_state.current_session:
    if msg['role'] == "Agent":
        st.markdown(f"<div class='message' style='text-align:left;'>⚛ <b>{msg['message']}</b></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='message' style='text-align:right;'>🧑‍🔬 <b>{msg['message']}</b></div>", unsafe_allow_html=True)
# --- Text above chat input (sticky) ---
# --- Static header above chat area ---
if 'header_rendered' not in st.session_state:
    st.markdown("""
    <div style='text-align:center; font-size:28px; font-weight:bold; color:#b0b0b0; margin-bottom:20px;'>
        What can I help with😊
    </div>
    """, unsafe_allow_html=True)
    st.session_state.header_rendered = True


# --- Chat input ---
prompt = st.chat_input("Say something...", key="main_chat_input")

if prompt:
    add_message("User", prompt)
    st.markdown(f"<div class='message' style='text-align:right;'>🧑‍🔬 <b>{prompt}</b></div>", unsafe_allow_html=True)

    placeholder = st.empty()
    typed_text = ""

    if ("pdf" in prompt.lower() or "file" in prompt.lower() or "document" in prompt.lower()) \
       and "uploaded_pdf_text" in st.session_state:

        if st.session_state.uploaded_pdf_text:
            final_answer = chat_with_agent(
                f"Please provide a summary of this document:\n\n{st.session_state.uploaded_pdf_text}",
                st.session_state.index,
                st.session_state.current_session
            )
        else:
            final_answer = "⚛ Sorry, no readable text was found in your PDF."
    else:
        final_answer = check_custom_response(prompt.lower()) or chat_with_agent(
            prompt, st.session_state.index, st.session_state.current_session
        )

    for char in final_answer:
        typed_text += char
        placeholder.markdown(f"<div class='message' style='text-align:left;'>⚛ <b>{typed_text}</b></div>", unsafe_allow_html=True)
        time.sleep(0.002)

    add_message("Agent", final_answer)

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())

# --- Sidebar helper ---
st.sidebar.markdown(
    "<p style='font-size:14px; color:gray;'>Right-click on the chat input to access emojis and additional features.</p>",
    unsafe_allow_html=True
)






