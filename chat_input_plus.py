# chat_input_plus.py
import time
import streamlit as st

def run_chat_input(add_message, check_custom_response, chat_with_agent):
    st.markdown("""
    <style>
      .upload-box [data-testid="stFileUploaderDropzone"] {
        border: none !important;
        padding: 0 !important;
        background: transparent !important;
      }
      .upload-box [data-testid="stFileUploaderDropzone"] div[role="button"] {
        border: 1px solid rgba(0,0,0,.15);
        border-radius: 8px;
        padding: 4px 6px;
        font-size: 0.9rem;
        cursor: pointer;
      }
      .upload-box [data-testid="stFileUploaderDropzone"] svg {
        display: none;
      }
      .upload-box [data-testid="stFileUploaderDropzone"] p {
        margin: 0;
      }
    </style>
    """, unsafe_allow_html=True)

    # Side-by-side: image button + chat input
    col1, col2 = st.columns([0.12, 0.88])
    with col1:
        with st.container():
            st.markdown('<div class="upload-box">', unsafe_allow_html=True)
            img = st.file_uploader("", type=["png", "jpg", "jpeg"], label_visibility="collapsed", key="chat_img")
            st.markdown('</div>', unsafe_allow_html=True)
            if img is not None:
                st.toast(f"Image attached: {img.name}")

    with col2:
        prompt = st.chat_input("Say something...")

    if not prompt:
        return

    add_message("User", prompt)
    if st.session_state.get("chat_img") is not None:
        add_message("User", f"[image attached: {st.session_state['chat_img'].name}]")

    normalized_prompt = prompt.strip().lower()

    placeholder = st.empty()
    placeholder.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
    time.sleep(0.5)

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    placeholder.empty()
