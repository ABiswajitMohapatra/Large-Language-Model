# chat_input_plus.py
import time
import streamlit as st

def run_chat_input(add_message, check_custom_response, chat_with_agent):
    """
    Chat input styled like the reference bar:
    - dark rounded bar
    - left circular (+) image-upload icon (opens popover with uploader)
    - right-side mic + blue action badge (decorative)
    - keeps your function signatures unchanged
    """

    # ---------- CSS: dark bar + icons ----------
    st.markdown("""
    <style>
      /* Dark rounded input like your reference */
      [data-testid="stChatInput"] textarea,[data-testid="stChatInput"] input{
        background:#2b2b2b !important; color:#eaeaea !important;
        border-radius:28px !important; border:1px solid #3a3a3a !important;
        box-shadow:inset 0 1px 0 rgba(255,255,255,0.04), 0 0 0 2px rgba(0,0,0,0.12) !important;
        padding:14px 16px !important;
      }
      [data-testid="stChatInput"] ::placeholder{ color:#a7a7a7 !important; }

      /* Align columns nicely */
      .chat-row { margin-top: .25rem; margin-bottom: .25rem; }

      /* Left circular + button */
      .icon-circle{
        width:40px; height:40px; border-radius:50%;
        background:#3a3a3a; color:#fff; display:flex;
        align-items:center; justify-content:center;
        border:1px solid #4a4a4a;
        transition:transform .15s ease, background .15s ease;
        user-select:none;
        font-weight:600; font-size:22px;
      }
      .icon-circle:hover{ background:#505050; transform:scale(1.05); }

      /* Make uploader look invisible until popover opens */
      .plain-uploader [data-testid="stFileUploaderDropzone"]{
        border:none !important; background:transparent !important; padding:0 !important;
      }
      .plain-uploader svg{ display:none; }
      .plain-uploader p{ margin:0 !important; }

      /* Right-side mic + blue badge */
      .right-icons{ display:flex; gap:.5rem; align-items:center; justify-content:flex-end; }
      .mic{ color:#cfcfcf; font-size:18px; }
      .blue-badge{
        width:40px; height:40px; border-radius:50%;
        background:#0a66ff; color:white; display:flex; align-items:center; justify-content:center;
        box-shadow: 0 0 0 3px rgba(10,102,255,0.25);
        font-weight:700;
      }
    </style>
    """, unsafe_allow_html=True)

    # ---------- Layout: [+] | chat_input | (mic • blue badge) ----------
    left, mid, right = st.columns([0.08, 0.84, 0.08], gap="small")
    with left:
        # The circular "+" that opens a popover with the uploader
        st.markdown('<div class="icon-circle">+</div>', unsafe_allow_html=True)
        # Position the popover right under the icon
        if hasattr(st, "popover"):
            with st.popover("Attach image", use_container_width=True):
                with st.container():
                    st.markdown('<div class="plain-uploader">', unsafe_allow_html=True)
                    img = st.file_uploader("Upload", type=["png","jpg","jpeg","webp"], key="chat_img")
                    st.markdown('</div>', unsafe_allow_html=True)
                    if img is not None:
                        st.success(f"Attached: {img.name}")
        else:
            # Fallback for older Streamlit versions
            with st.expander("Attach image"):
                with st.container():
                    st.markdown('<div class="plain-uploader">', unsafe_allow_html=True)
                    img = st.file_uploader("Upload", type=["png","jpg","jpeg","webp"], key="chat_img")
                    st.markdown('</div>', unsafe_allow_html=True)
                    if img is not None:
                        st.success(f"Attached: {img.name}")

    with mid:
        prompt = st.chat_input("Ask anything")

    with right:
        st.markdown(
            '<div class="right-icons">'
            '<span class="mic">🎤</span>'
            '<span class="blue-badge">◦◦</span>'
            '</div>',
            unsafe_allow_html=True
        )

    # ---------- Logic (unchanged) ----------
    if not prompt:
        return

    add_message("User", prompt)
    if st.session_state.get("chat_img") is not None:
        add_message("User", f"[image attached: {st.session_state['chat_img'].name}]")

    normalized = prompt.strip().lower()
    ph = st.empty()
    ph.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
    time.sleep(0.5)

    custom = check_custom_response(normalized)
    if custom:
        add_message("Agent", custom)
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    ph.empty()
