import streamlit as st
import model

st.set_page_config(page_title="My RAG Chatbot", page_icon="🤖", layout="wide")
st.title("🤖 My Chatbot")
st.caption("Powered by Groq · live web search · your own documents")

if not model.GROQ_API_KEY:
    st.error(
        "GROQ_API_KEY is not set. Add it to a local `.env` file for development, "
        "or under **Settings → Secrets** in Streamlit Cloud for the deployed app."
    )
    st.stop()

# --- session state -----------------------------------------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_index" not in st.session_state:
    st.session_state.session_index = model.empty_index()
if "added_files" not in st.session_state:
    st.session_state.added_files = set()

base_index = model.get_base_index()  # shared knowledge base from the `documents/` folder

# --- sidebar -------------------------------------------------------------
with st.sidebar:
    st.header("📄 Add your own files")
    st.caption("Files uploaded here are only visible in this session and aren't saved permanently.")
    uploaded_files = st.file_uploader(
        "PDF, DOCX, TXT, MD, or images",
        type=["pdf", "docx", "txt", "md", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )
    if uploaded_files:
        for f in uploaded_files:
            if f.name not in st.session_state.added_files:
                text = model.load_file(f, f.name)
                if text.strip():
                    st.session_state.session_index = model.add_to_index(
                        st.session_state.session_index, f.name, text
                    )
                    st.session_state.added_files.add(f.name)
                    st.success(f"Added '{f.name}' to this session's knowledge")
                else:
                    st.warning(f"Couldn't extract any text from '{f.name}'")

    if st.session_state.added_files:
        st.write("Session files:", ", ".join(sorted(st.session_state.added_files)))

    st.divider()
    if st.button("🗑️ Clear conversation"):
        st.session_state.chat_history = []
        st.rerun()

# --- chat history ----------------------------------------------------------
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["message"])

# --- chat input --------------------------------------------------------------
user_query = st.chat_input("Ask me anything...")
if user_query:
    st.session_state.chat_history.append({"role": "user", "message": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    combined_index = model.merge_indexes(base_index, st.session_state.session_index)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer, doc_sources, used_web = model.chat_with_agent(
                user_query, combined_index, st.session_state.chat_history[:-1]
            )
        st.markdown(answer)
        tags = []
        if used_web:
            tags.append("🌐 used live web search")
        if doc_sources:
            tags.append(f"📄 referenced: {', '.join(doc_sources)}")
        if tags:
            st.caption(" · ".join(tags))

    st.session_state.chat_history.append({"role": "assistant", "message": answer})
