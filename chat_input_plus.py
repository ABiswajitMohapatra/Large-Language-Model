# chat_input_plus.py
import time
import streamlit as st

def run_chat_input(add_message, check_custom_response, chat_with_agent):
    """
    Sticky bottom chat bar (like your ref) + a real '+' image uploader
    pinned to the left of the bar. We *only* render one uploader and
    hard-scope all CSS to that uploader so nothing big shows in the middle.
    """

    # ===== CSS (scoped + robust) =====
    st.markdown("""
<style>
:root{
  --bar-width: min(860px, 94vw);
  --bar-bottom: 14px;
}

/* keep space so the fixed bar doesn't overlap content */
.main .block-container{ padding-bottom: 110px !important; }

/* Fix Streamlit's chat input to bottom center */
[data-testid="stChatInput"]{
  position: fixed !important;
  left: 50% !important;
  transform: translateX(-50%) !important;
  bottom: var(--bar-bottom) !important;
  width: var(--bar-width) !important;
  z-index: 9998 !important;
}
[data-testid="stChatInput"] textarea,[data-testid="stChatInput"] input{
  background:#fff !important; color:#111827 !important;
  border:1px solid #e5e7eb !important; border-radius:28px !important;
  box-shadow:0 1px 2px rgba(0,0,0,0.04) !important; padding:12px 16px !important;
}
[data-testid="stChatInput"] ::placeholder{ color:#9ca3af !important; }
[data-testid="stChatInput"] :is(textarea,input):focus{ outline:none !important; box-shadow:none !important; }

/* ---------- STRICTLY scope our uploader by id ---------- */
#chat-uploader [data-testid="stFileUploader"]{
  position: fixed !important;
  left: calc(50% - var(--bar-width)/2 - 56px) !important;   /* left of the bar */
  bottom: var(--bar-bottom) !important;
  width: 44px !important; height: 44px !important;
  z-index: 9999 !important;
  margin: 0 !important;
}
#chat-uploader [data-testid="stFileUploaderDropzone"]{
  width: 44px !important; height: 44px !important;
  border-radius: 50% !important;
  border: 1px solid #e5e7eb !important;
  background: #ffffff !important;
  padding: 0 !important; margin: 0 !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
}
#chat-uploader [data-testid="stFileUploaderDropzone"] div[role="button"]{
  width: 44px !important; height: 44px !important;
  display:flex; align-items:center; justify-content:center;
  background: transparent !important; border:none !important; cursor:pointer;
}
#chat-uploader [data-testid="stFileUploaderDropzone"] svg,
#chat-uploader [data-testid="stFileUploaderDropzone"] p{ display:none !important; }
#chat-uploader [data-testid="stFileUploaderDropzone"] div[role="button"]::before{
  content: "+"; font-size:22px; font-weight:600; color:#111827; line-height:1;
}
#chat-uploader [data-testid="stFileUploaderDropzone"]:hover{
  background:#f9fafb !important; transform: scale(1.05);
  transition: transform .15s ease;
}

/* Hide ANY other file uploaders on the page (safety net) */
[data-testid="stFileUploader"]:not(:has(> div > #chat-uploader-inner)) {
  display: none !important;
}

/* right-side icons fixed to the right of the bar */
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
""", unsafe_allow_html=True)

    # ===== OUR ONLY uploader, wrapped with a unique id =====
    st.markdown('<div id="chat-uploader"><div id="chat-uploader-inner"></div></div>', unsafe_allow_html=True)
    img = st.file_uploader(
        "Attach image",
        type=["png","jpg","jpeg","webp"],
        key="chat_img",
        label_visibility="collapsed",
    )
    if img is not None:
        st.toast(f"Image attached: {img.name}")

    # ===== right-side visuals (unchanged) =====
    st.markdown(
        '<div id="chat-right"><span class="mic">🎤</span>'
        '<span class="blue-badge"><span class="blue-inner">⏵</span></span></div>',
        unsafe_allow_html=True
    )

    # ===== the fixed input =====
    prompt = st.chat_input("Ask anything")
    if not prompt:
        return

    # ===== your chat logic (unchanged) =====
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
