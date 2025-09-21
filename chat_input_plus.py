# chat_input_plus.py
import time
import streamlit as st

def run_chat_input(add_message, check_custom_response, chat_with_agent):
    # --- CSS for rounded input + icon button style ---
    st.markdown("""
    <style>
      /* round the chat input */
      [data-testid="stChatInput"] textarea,[data-testid="stChatInput"] input{
        border-radius:14px!important;border:1px solid rgba(0,0,0,.12)!important;
        box-shadow:0 2px 10px rgba(0,0,0,.06)!important;padding:12px 14px!important;
      }
      /* make the uploader look like a clean icon button */
      .icon-upload [data-testid="stFileUploaderDropzone"]{
        border:none !important;
        background:transparent !important;
        padding:0 !important;
        text-align:center !important;
      }
      .icon-upload [data-testid="stFileUploaderDropzone"] div[role="button"]{
        border:1px solid rgba(0,0,0,0.4);
        border-radius:50%;
        width:38px; height:38px;
        display:flex; align-items:center; justify-content:center;
        cursor:pointer;
        transition: all .2s ease-in-out;
        background:white;
      }
      .icon-upload [data-testid="stFileUploaderDropzone"] div[role="button"]:hover{
        background:black; color:white;
        transform: scale(1.05);
      }
      .icon-upload svg{ display:none; }  /* hide default svg */
      .icon-upload p{ margin:0; font-size:18px; } /* show emoji instead */
    </style>
    """, unsafe_allow_html=True)

    # --- layout: small icon button left, input right ---
    col1, col2 = st.columns([0.1, 0.9])
    with col1:
        with st.container():
            st.markdown('<div class="icon-upload">', unsafe_allow_html=True)
            img = st.file_uploader("🖼️", type=["png","jpg","jpeg","webp"], label_visibility="collapsed", key="chat_img")
            st.markdown('</div>', unsafe_allow_html=True)
            if img is not None:
                st.toast(f"Image attached: {img.name}")

    with col2:
        prompt = st.chat_input("Say something...")

    if not prompt:
        return

    # log user + file if any
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
