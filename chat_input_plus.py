# chat_input_plus.py
import time
import streamlit as st

def run_chat_input(add_message, check_custom_response, chat_with_agent):
    """
    Sticky bottom chat bar (like your reference) + a TRUE '+' image button
    pinned to the left of the bar. No big uploader in the middle.

    IMPORTANT: Make sure you do NOT call st.file_uploader() anywhere else
    in your app, or you'll still see another (big) uploader on the page.
    """

    # ====== STYLES: pin chat input, style it, and convert our uploader to a small '+' ======
    st.markdown(
        """
<style>
:root{
  --bar-width: min(860px, 94vw);
  --bar-bottom: 14px;
}

/* leave room so the fixed bar doesn't overlap content */
.main .block-container{ padding-bottom: 110px !important; }

/* Fix the Streamlit chat input to bottom center */
[data-testid="stChatInput"]{
  position: fixed !important;
  left: 50% !important;
  transform: translateX(-50%) !important;
  bottom: var(--bar-bottom) !important;
  width: var(--bar-width) !important;
  z-index: 9998 !important;
}
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] input{
  background:#ffffff !important;
  color:#111827 !important;
  border:1px solid #e5e7eb !important;
  border-radius:28px !important;
  box-shadow:0 1px 2px rgba(0,0,0,0.04) !important;
  padding:12px 16px !important;
}
[data-testid="stChatInput"] ::placeholder{ color:#9ca3af !important; }
[data-testid="stChatInput"] :is(textarea,input):focus{
  outline:none !important; box-shadow:none !important;
}

/* ---------- Our uploader wrapper made into a small '+' circle (FIXED) ---------- */
.uploader-circle [data-testid="stFileUploader"]{
  position: fixed !important;
  left: calc(50% - var(--bar-width)/2 - 56px) !important; /* to the left of bar */
  bottom: var(--bar-bottom) !important;
  width: 44px !important; height: 44px !important;
  z-index: 9999 !important;
}

/* kill default look of the dropzone */
.uploader-circle [data-testid="stFileUploaderDropzone"]{
  width: 44px !important; height: 44px !important;
  border-radius: 50% !important;
  border: 1px solid #e5e7eb !important;
  background: #ffffff !important;
  padding: 0 !important; margin: 0 !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
}
.uploader-circle [data-testid="stFileUploaderDropzone"] svg,
.uploader-circle [data-testid="stFileUploaderDropzone"] p{
  display:none !important;
}

/* center the (now invisible) inner button and draw a '+' ourselves */
.uploader-circle [data-testid="stFileUploaderDropzone"] div[role="button"]{
  width: 44px !important; height: 44px !important;
  display:flex; align-items:center; justify-content:center;
  background: transparent !important; border:none !important;
  cursor: pointer;
}
.uploader-circle [data-testid="stFileUploaderDropzone"] div[role="button"]::before{
  content: "+";
  font-size: 22px; font-weight: 600; color: #111827;
}
.uploader-circle [data-testid="stFileUploaderDropzone"]:hover{
  background:#f9fafb !important; transform: scale(1.05);
  transition: transform .15s ease;
}

/* ---------- Right-side icons fixed to the right of the bar ---------- */
#chat-right{
  position: fixed !important; 
  bottom: var(--bar-bottom) !important;
  left: calc(50% + var(--bar-width)/2 + 12px) !important;
  display:flex; gap:10px; align-items:center;
  z-index: 9999 !important;
}
#chat-right .mic{ font-size:18px; color:#111827; }
#chat-right .blue-badge{
  width:44px; height:44px; border-radius:50%;
  background:#e6f0ff; display:flex; align-items:center; justify-content:center;
}
#chat-right .blue-inner{
  width:32px; height:32px; border-radius:50%;
  background:#0a66ff; color:#fff; font-weight:700; font-size:12px;
  display:flex; align-items:center; justify-content:center;
}
</style>
""",
        unsafe_allow_html=True,
    )

    # ====== Render just ONE uploader, wrapped so CSS can target it ======
    with st.container():
        st.markdown('<div class="uploader-circle">', unsafe_allow_html=True)
        img = st.file_uploader(
            "Attach image",
            type=["png", "jpg", "jpeg", "webp"],
            key="chat_img",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    if img is not None:
        st.toast(f"Image attached: {img.name}")

    # ====== Right-side icons (visual only) ======
    st.markdown(
        '<div id="chat-right">'
        '<span class="mic">🎤</span>'
        '<span class="blue-badge"><span class="blue-inner">⏵</span></span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ====== The (fixed) input bar ======
    prompt = st.chat_input("Ask anything")
    if not prompt:
        return

    # ====== Your logic (unchanged) ======
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
