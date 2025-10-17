import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import pdfplumber
import time
from fpdf import FPDF
import io
import os
import requests

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
div.message {
    margin: 2px 0;
    font-size: 17px;
}

div[data-testid="stHorizontalBlock"] {
    margin-bottom: 0px;
    padding-bottom: 0px;
}

@media only screen and (max-width: 600px) {
    section[data-testid="stSidebar"] {
        max-width: 250px;
    }
}

.sidebar-helper {
    color: blue !important;
    font-size: 14px;
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

uploaded_file = st.sidebar.file_uploader("", label_visibility="collapsed", type=["pdf"])
if uploaded_file and "uploaded_pdf_text" not in st.session_state:
    extracted_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
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

# --- Static header ---
if 'header_rendered' not in st.session_state:
    st.markdown("""
    <div style='text-align:center; font-size:28px; font-weight:bold; color:#b0b0b0; margin-bottom:20px;'>
        What can I help with?😊
    </div>
    """, unsafe_allow_html=True)
    st.session_state.header_rendered = True

# --- Fixed generate_chat_pdf function ---
def generate_chat_pdf(messages):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Load a Unicode font (DejaVuSans)
    font_path = "DejaVuSans.ttf"
    font_url = "https://github.com/dejavu-fonts/dejavu-fonts/raw/version_2_37/ttf/DejaVuSans.ttf"
    if not os.path.exists(font_path):
        try:
            r = requests.get(font_url)
            if r.status_code == 200:
                with open(font_path, "wb") as f:
                    f.write(r.content)
        except Exception as e:
            st.error("Font download failed, using default Arial font.")
            font_path = None

    if os.path.exists(font_path):
        pdf.add_font("DejaVu", fname=font_path, uni=True)
        pdf.set_font("DejaVu", size=12)
    else:
        pdf.set_font("Arial", size=12)

    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('message', '')
        if role.lower() == 'user':
            pdf.set_text_color(0, 0, 255)
        else:
            pdf.set_text_color(0, 128, 0)
        pdf.multi_cell(0, 10, f"{role}: {content}")
        pdf.ln(3)

    pdf_output = pdf.output(dest='S').encode('utf-8')
    return io.BytesIO(pdf_output)

# --- Chat input ---
prompt = st.chat_input("Say something...", key="main_chat_input")

if prompt:
    add_message("User", prompt)
    st.markdown(f"<div class='message' style='text-align:right;'>🧑‍🔬 <b>{prompt}</b></div>", unsafe_allow_html=True)

    placeholder = st.empty()
    typed_text = ""

    if ("pdf" in prompt.lower() or "file" in prompt.lower() or "document" in prompt.lower()) and "uploaded_pdf_text" in st.session_state:
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
    st.balloons()

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())

# --- Sidebar Download Chat ---
if st.sidebar.button("Download Chat as PDF"):
    pdf_file = generate_chat_pdf(st.session_state.current_session)
    st.sidebar.download_button(
        label="Download Current Chat as PDF",
        data=pdf_file,
        file_name="chat_session.pdf",
        mime="application/pdf"
    )

st.sidebar.markdown(
    "<p class='sidebar-helper'>Right-click on the chat input to access emojis and additional features.</p>",
    unsafe_allow_html=True
)
