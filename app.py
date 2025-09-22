import streamlit as st
from model import load_documents, create_or_load_index, chat_with_agent
import time
from datetime import datetime

st.set_page_config(page_title="BiswaLex", page_icon="⚛", layout="wide")

# Initialize session states
if "index" not in st.session_state:
    st.session_state.index = create_or_load_index()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_chat" not in st.session_state:
    st.session_state.current_chat = {
        "id": 0,
        "title": "New Chat",
        "messages": [],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

# Custom responses
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

# Sidebar
with st.sidebar:
    st.title("Chat History")

    # New Chat button
    if st.button("+ New Chat", use_container_width=True):
        if st.session_state.current_chat["messages"]:
            if st.session_state.current_chat not in st.session_state.chat_history:
                st.session_state.chat_history.append(st.session_state.current_chat)

        st.session_state.current_chat = {
            "id": len(st.session_state.chat_history),
            "title": "New Chat",
            "messages": [],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        st.rerun()

    # Clear all chats button
    if st.button("Clear All Chats", type="secondary", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.current_chat = {
            "id": 0,
            "title": "New Chat",
            "messages": [],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        st.rerun()

    # Display chat history
    st.divider()
    for chat in reversed(st.session_state.chat_history):
        if st.button(
            f"💬 {chat['title']}\n{chat['timestamp']}",
            key=f"chat_{chat['id']}",
            use_container_width=True
        ):
            st.session_state.current_chat = chat
            st.rerun()

# Logo and welcome text
st.markdown(
    """
    <div style="text-align: center; margin-bottom: 10px;">
        <img src="https://raw.githubusercontent.com/ABiswajitMohapatra/Large-Language-Model/main/logo.jpg"
             style="width: 100%; max-width: 350px; height: auto; animation: bounce 1s infinite;">
        <p style="font-size:20px; font-style:italic; color:#333;">How can I help with!😊</p>
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

# Display current chat messages
for msg in st.session_state.current_chat["messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Chat input
prompt = st.chat_input("Say something...")

# Handle text input
if prompt:
    # Update chat title if it's the first message
    if not st.session_state.current_chat["messages"]:
        st.session_state.current_chat["title"] = prompt[:30] + "..." if len(prompt) > 30 else prompt

    # Add user message
    st.session_state.current_chat["messages"].append({
        "role": "user",
        "content": prompt
    })

    # Display user message
    with st.chat_message("user"):
        st.write(prompt)

    # Show typing indicator
    placeholder = st.empty()
    placeholder.markdown(
        """
        <div style="display:flex; align-items:center; color:gray; font-style:italic;">
            <span style="margin-right:5px;">Agent is typing</span>
            <span class="arrow">&#10148;</span>
        </div>
        <style>
        .arrow {
            display:inline-block;
            animation: moveArrow 1s infinite linear;
        }
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

    # Generate response
    custom_answer = check_custom_response(prompt.lower())
    if custom_answer:
        response = custom_answer
    else:
        response = chat_with_agent(prompt, st.session_state.index, st.session_state.current_chat["messages"])

    # Remove typing indicator and display response
    placeholder.empty()
    with st.chat_message("assistant"):
        st.write(response)

    # Add assistant message
    st.session_state.current_chat["messages"].append({
        "role": "assistant",
        "content": response
    })

    # Auto-save current chat
    if st.session_state.current_chat not in st.session_state.chat_history:
        st.session_state.chat_history.append(st.session_state.current_chat.copy())

# Add styling
st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #f0f2f6;
        padding: 1rem;
    }
    .stButton button {
        width: 100%;
        text-align: left;
        padding: 0.5rem;
        background-color: white;
        margin-bottom: 0.5rem;
    }
    .stButton button:hover {
        background-color: #e6e6e6;
    }
    </style>
""", unsafe_allow_html=True)
