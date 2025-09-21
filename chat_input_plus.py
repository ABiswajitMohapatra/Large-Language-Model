# chat_input_plus.py
import time
import streamlit as st

def run_chat_input(add_message, check_custom_response, chat_with_agent):
    # very light, safe input rounding (no extra HTML wrappers)
    st.markdown("""
    <style>
      [data-testid="stChatInput"] textarea,[data-testid="stChatInput"] input{
        border-radius:14px!important;border:1px solid rgba(0,0,0,.12)!important;
        box-shadow:0 2px 10px rgba(0,0,0,.06)!important;padding:12px 14px!important;
      }
    </style>
    """, unsafe_allow_html=True)

    # small toolbar with an image popover to the left of the chat input
    left, right = st.columns([0.10, 0.90])
    with left:
        # popover avoids custom HTML and keeps the UI compact
        if hasattr(st, "popover"):
            with st.popover("🖼️", use_container_width=True):
                img = st.file_uploader("Attach an image", type=["png","jpg","jpeg","webp"], key="chat_img")
                if img is not None:
                    st.success(f"Attached: {img.name}")
        else:
            # fallback for older Streamlit versions
            with st.expander("🖼️ Attach image"):
                img = st.file_uploader("Attach an image", type=["png","jpg","jpeg","webp"], key="chat_img")
                if img is not None:
                    st.success(f"Attached: {img.name}")

    with right:
        prompt = st.chat_input("Say something...")

    if not prompt:
        return

    # user message(s)
    add_message("User", prompt)
    if st.session_state.get("chat_img") is not None:
        add_message("User", f"[image attached: {st.session_state['chat_img'].name}]")

    # typing indicator
    normalized = prompt.strip().lower()
    ph = st.empty()
    ph.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
    time.sleep(0.5)

    # response
    custom = check_custom_response(normalized)
    if custom:
        add_message("Agent", custom)
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    ph.empty()
