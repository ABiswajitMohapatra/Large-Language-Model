import streamlit as st
from model import get_base_index, chat_with_agent_stream
import pdfplumber

st.set_page_config(page_title="BiswaLex", page_icon="⚛", layout="wide")

# --- Initialize index and sessions ---
if "index" not in st.session_state:
    st.session_state.index = get_base_index()

if "sessions" not in st.session_state:
    st.session_state.sessions = []

if "current_session" not in st.session_state:
    st.session_state.current_session = []

if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""

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

.meta-tag {
    color: #888;
    font-size: 12px;
    margin: 0 0 8px 0;
}
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.title("B͎i͎s͎w͎a͎L͎e͎x͎⚛")

if st.sidebar.button("New Chat"):
    st.session_state.current_session = []
    st.session_state.uploaded_pdf_text = ""

if st.sidebar.button("Clear Chat"):
    st.session_state.current_session = []

for i, sess in enumerate(st.session_state.sessions):
    if st.sidebar.button(f"Session {i+1}"):
        st.session_state.current_session = sess.copy()

uploaded_file = st.sidebar.file_uploader(
    "",
    label_visibility="collapsed",
    type=["pdf"],
    key="pdf_uploader"
)

if uploaded_file is not None:
    extracted_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            extracted_text += (page.extract_text() or "") + "\n"
    st.session_state.uploaded_pdf_text = extracted_text.strip()


# --- Message handler ---
def add_message(role, message, sources=None, web_used=False):
    st.session_state.current_session.append({
        "role": role,
        "message": message,
        "sources": sources or [],
        "web_used": web_used
    })


# Custom responses take priority over everything, checked with word-boundary
# matching so they don't accidentally fire on unrelated text containing
# substrings like "ok" inside another word.
CUSTOM_RESPONSES = {
    "who created you": "I was created by Biswajit Mohapatra, my owner 🚀",
    "who is your creator": "My creator is Biswajit Mohapatra.",
    "who is your father": "My father is Biswajit Mohapatra 👨‍💻",
    "who trained you": "I was trained and fine-tuned by Biswajit Mohapatra."
}


def check_custom_response(user_input: str):
    normalized = user_input.lower().strip().rstrip("?!.")
    return CUSTOM_RESPONSES.get(normalized)


def render_meta_tag(sources, web_used):
    tags = []
    if web_used:
        tags.append("🌐 used live web search")
    if sources:
        tags.append(f"📄 sources: {', '.join(sources)}")
    if tags:
        st.markdown(
            f"<div class='meta-tag'>{' · '.join(tags)}</div>",
            unsafe_allow_html=True
        )


# --- Display old messages ---
for msg in st.session_state.current_session:
    if msg["role"] == "Agent":
        st.markdown(
            f"<div class='message' style='text-align:left;'>⚛ <b>{msg['message']}</b></div>",
            unsafe_allow_html=True
        )
        render_meta_tag(msg.get("sources"), msg.get("web_used"))
    else:
        st.markdown(
            f"<div class='message' style='text-align:right;'>🧑‍🔬 <b>{msg['message']}</b></div>",
            unsafe_allow_html=True
        )

# --- Show header only before first chat ---
if len(st.session_state.current_session) == 0:
    st.markdown("""
    <div style='text-align:center; font-size:28px; font-weight:bold; color:#b0b0b0; margin-bottom:20px;'>
        What can I help with? 😊
    </div>
    """, unsafe_allow_html=True)

# --- Chat input ---
prompt = st.chat_input("Say something...", key="main_chat_input")

if prompt:
    add_message("User", prompt)

    st.markdown(
        f"<div class='message' style='text-align:right;'>🧑‍🔬 <b>{prompt}</b></div>",
        unsafe_allow_html=True
    )

    placeholder = st.empty()
    custom_reply = check_custom_response(prompt)

    if custom_reply:
        final_answer = custom_reply
        sources, web_used = [], False
        placeholder.markdown(
            f"<div class='message' style='text-align:left;'>⚛ <b>{final_answer}</b></div>",
            unsafe_allow_html=True
        )
    else:
        use_pdf = (
            ("pdf" in prompt.lower() or "file" in prompt.lower() or "document" in prompt.lower())
            and st.session_state.uploaded_pdf_text
        )
        query_text = "Please provide a summary of this document." if use_pdf else prompt
        extra_content = st.session_state.uploaded_pdf_text if use_pdf else ""

        stream, sources, web_used = chat_with_agent_stream(
            query_text,
            st.session_state.index,
            st.session_state.current_session,
            extra_file_content=extra_content
        )

        # Real streaming: render tokens as they arrive from Groq, no artificial delay.
        typed_text = ""
        for chunk in stream:
            typed_text += chunk
            placeholder.markdown(
                f"<div class='message' style='text-align:left;'>⚛ <b>{typed_text}</b></div>",
                unsafe_allow_html=True
            )
        final_answer = typed_text

    render_meta_tag(sources, web_used)
    add_message("Agent", final_answer, sources=sources, web_used=web_used)

# --- Save session ---
if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())

# --- Sidebar helper ---
st.sidebar.markdown(
    "<p class='sidebar-helper'>Right-click on the chat input to access emojis and additional features.</p>",
    unsafe_allow_html=True
)
