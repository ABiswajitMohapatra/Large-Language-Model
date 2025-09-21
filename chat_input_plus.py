# chat_input_plus.py
import time
import streamlit as st


def run_chat_input(add_message, check_custom_response, chat_with_agent):
    """
    Sticky, pixel-consistent bar like your reference:
      • Centered rounded white input
      • Left circular “+” (opens uploader)
      • Right mic and blue badge (visual)
      • Stays fixed at the bottom while scrolling
    No changes to your existing function signatures.
    """

    # ---------- GLOBAL CSS (make the bar sticky & style exactly) ----------
    st.markdown(
        """
<style>
:root{
  --bar-width: min(860px, 94vw);
  --bar-bottom: 14px;
}

/* give space so fixed bar doesn't cover content */
.main .block-container{ padding-bottom: 110px !important; }

/* FIX the actual Streamlit chat input to the bottom */
[data-testid="stChatInput"]{
  position: fixed !important;
  left: 50% !important;
  transform: translateX(-50%) !important;
  bottom: var(--bar-bottom) !important;
  width: var(--bar-width) !important;
  z-index: 9998 !important;
}

/* exact visual style */
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] input{
  background: #ffffff !important;
  color: #111827 !important;
  border: 1px solid #e5e7eb !important;      /* gray-200 */
  border-radius: 28px !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
  padding: 12px 16px !important;
}
[data-testid="stChatInput"] :is(textarea,input):focus{
  outline: none !important;
  box-shadow: 0 0 0 0 rgba(0,0,0,0) !important;  /* remove teal ring */
  border-color: #e5e7eb !important;
}
[data-testid="stChatInput"] ::placeholder{ color:#9ca3af !important; }

/* LEFT fixed '+' button */
#chat-plus{
  position: fixed; bottom: var(--bar-bottom); 
  left: calc(50% - var(--bar-width)/2 - 56px);
  width: 44px; height: 44px; border-radius: 50%;
  background:#ffffff; border:1px solid #e5e7eb;
  display:flex; align-items:center; justify-content:center;
  color:#111827; font-weight:600; font-size:22px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  cursor:pointer; user-select:none;
  z-index: 9999;
  transition: transform .15s ease, background .15s ease;
}
#chat-plus:hover{ background:#f9fafb; transform: scale(1.04); }

/* make uploader minimal inside popover */
.plain-uploader [data-testid="stFileUploaderDropzone"]{
  border:none !important; background:transparent !important; padding:0 !important;
}
.plain-uploader svg{ display:none; }
.plain-uploader p{ margin:0 !important; }

/* RIGHT fixed mic + blue badge */
#chat-right{
  position: fixed; bottom: var(--bar-bottom);
  left: calc(50% + var(--bar-width)/2 + 12px);
  display:flex; gap:10px; align-items:center; z-index: 9999;
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

    # ---------- LEFT “+” BUTTON (fixed) + POPOVER UPLOADER ----------
    # (We render a tiny element to attach the popover to.)
    left_anchor = st.empty()
    with left_anchor.container():
        st.markdown('<div id="chat-plus">+</div>', unsafe_allow_html=True)
        if hasattr(st, "popover"):
            with st.popover("Attach image", use_container_width=True):
                st.markdown('<div class="plain-uploader">', unsafe_allow_html=True)
                img = st.file_uploader("Upload image", type=["png","jpg","jpeg","webp"], key="chat_img")
                st.markdown("</div>", unsafe_allow_html=True)
                if img is not None:
                    st.success(f"Attached: {img.name}")
        else:
            with st.expander("Attach image"):
                st.markdown('<div class="plain-uploader">', unsafe_allow_html=True)
                img = st.file_uploader("Upload image", type=["png","jpg","jpeg","webp"], key="chat_img")
                st.markdown("</div>", unsafe_allow_html=True)
                if img is not None:
                    st.success(f"Attached: {img.name}")

    # ---------- RIGHT FIXED ICONS ----------
    st.markdown(
        '<div id="chat-right"><span class="mic">🎤</span>'
        '<span class="blue-badge"><span class="blue-inner">﹙﹚</span></span></div>',
        unsafe_allow_html=True,
    )

    # ---------- THE ACTUAL INPUT (now fixed at bottom) ----------
    prompt = st.chat_input("Ask anything")
    if not prompt:
        return

    # ---------- LOGIC (unchanged) ----------
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
