# chat_input_plus.py
import time
import streamlit as st

def run_chat_input(add_message, check_custom_response, chat_with_agent):
    # --- light CSS to make a single "bar" with an image button on the left ---
    st.markdown("""
    <style>
      .chatbar { display:flex; gap:.5rem; align-items:center; }
      .chatbar .uploader > div { margin:0 !important; padding:0 !important; }
      .chatbar .uploader [data-testid="stFileUploaderDropzone"]{
        border:none !important; padding:0 !important; background:transparent !important;
      }
      .chatbar .uploader [data-testid="stFileUploaderDropzone"] div[role="button"]{
        border:1px solid rgba(0,0,0,.15); border-radius:12px; padding:.45rem .6rem;
        font-size:1rem; line-height:1; cursor:pointer;
      }
      .chatbar .uploader [data-testid="stFileUploaderDropzone"] svg{ display:none; }
      .chatbar .uploader [data-testid="stFileUploaderDropzone"] p{ margin:0; }
      /* rounder input like ChatGPT */
      [data-testid="stChatInput"] textarea,[data-testid="stChatInput"] input{
        border-radius:14px !important; border:1px solid rgba(0,0,0,.12) !important;
        box-shadow:0 2px 10px rgba(0,0,0,.06) !important; padding:12px 14px !important;
      }
    </style>
    """, unsafe_allow_html=True)

    # --- inline "image button" + chat input (short & simple) ---
    c1, c2 = st.columns([0.12, 0.88])
    with c1:
        with st.container():  # keeps uploader compact
            st.markdown('<div class="chatbar">', unsafe_allow_html=True)
            img = st.file_uploader(" ", type=["png","jpg","jpeg","webp"], key="__img__", label_visibility="collapsed")
            st.markdown('</div>', unsafe_allow_html=True)
            if img is not None:
                st.toast(f"Attached: {img.name}")

    with c2:
        prompt = st.chat_input("Say something...")

    if not prompt:
        return

    add_message("User", prompt)
    if st.session_state.get("__img__") is not None:
        add_message("User", f"[image attached: {st.session_state['__img__'].name}]")

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
