import streamlit as st
from io import BytesIO

st.set_page_config(page_title="Biswa Search", page_icon="🔍", layout="wide")

st.markdown("""
    <style>
        .search-container {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-top: 50px;
        }
        .search-box {
            display: flex;
            align-items: center;
            border: 2px solid #ccc;
            border-radius: 25px;
            padding: 8px 15px;
            width: 500px;
            background-color: white;
        }
        .search-box input {
            border: none;
            outline: none;
            flex: 1;
            font-size: 16px;
        }
        .plus-icon {
            font-size: 22px;
            font-weight: bold;
            color: #555;
            margin-right: 10px;
            cursor: pointer;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="search-container">
        <div class="search-box">
            <label for="file_input" class="plus-icon">+</label>
            <input type="file" id="file_input" style="display:none" accept=".pdf,.png,.jpg,.jpeg">
            <input type="text" placeholder="Search or type something...">
        </div>
    </div>
""", unsafe_allow_html=True)

def add_message(role, message):
    st.session_state.current_session.append({"role": role, "message": message})

CUSTOM_RESPONSES = {
    "who created you": "I was created by *Biswajit Mohapatra*, my owner 🚀",
    "creator": "My creator is *Biswajit Mohapatra*.",
    "who is your father": "My father is *Biswajit Mohapatra* 👨‍💻",
    "trained": "I was trained and fine-tuned by *Biswajit Mohapatra*.",
    "owner": "My owner is *Biswajit Mohapatra*."
}

def check_custom_response(user_input: str):
    normalized = user_input.lower()
    for keyword, response in CUSTOM_RESPONSES.items():
        if keyword in normalized:
            return response
    return None

# --- Custom Search/Chat Bar ---
with st.form("chat_form", clear_on_submit=True):
    st.markdown(
        """
        <div class="chat-bar">
            <label for="fileUpload">+</label>
            <input type="file" id="fileUpload" name="fileUpload" accept=".pdf,.png,.jpg,.jpeg">
            <input type="text" name="user_input" placeholder="Say something...">
            <button type="submit">➤</button>
        </div>
        """,
        unsafe_allow_html=True
    )
    submitted = st.form_submit_button("")

# Handle uploaded file
uploaded_file = st.file_uploader("hidden", type=["pdf","png","jpg","jpeg"], label_visibility="collapsed")
if uploaded_file:
    if uploaded_file.type == "application/pdf":
        st.session_state.uploaded_content = extract_text_from_pdf(uploaded_file)
    elif uploaded_file.type.startswith("image/"):
        st.session_state.uploaded_content = extract_text_from_image(uploaded_file)

# Handle chat input
if submitted and "user_input" in st.query_params:
    prompt = st.query_params["user_input"]
    if prompt:
        add_message("User", prompt)
        normalized_prompt = prompt.strip().lower()

        placeholder = st.empty()
        placeholder.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
        time.sleep(0.5)

        custom_answer = check_custom_response(normalized_prompt)
        if custom_answer:
            add_message("Agent", custom_answer)
        else:
            context = prompt
            if st.session_state.uploaded_content:
                context += "\n\n" + st.session_state.uploaded_content
            answer = chat_with_agent(context, st.session_state.index, st.session_state.current_session)
            add_message("Agent", answer)

        placeholder.empty()

# Display chat history
for msg in st.session_state.current_session:
    align = "left" if msg['role'] == "Agent" else "right"
    st.markdown(
        f"<div style='color:black; text-align:{align}; margin:5px 0;'><b>{msg['role']}:</b> {msg['message']}</div>",
        unsafe_allow_html=True
    )

if st.sidebar.button("Save Session"):
    if st.session_state.current_session not in st.session_state.sessions:
        st.session_state.sessions.append(st.session_state.current_session.copy())

