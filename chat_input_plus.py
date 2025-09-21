# chat_input_plus.py
import time
import streamlit as st


def run_chat_input(add_message, check_custom_response, chat_with_agent):
    """
    Sticky bottom chat bar styled like your reference:
      • rounded white bar
      • left circular '+' upload button (opens popover -> file_uploader)
      • right mic icon + blue circular action badge (visual only)
      • stays fixed at bottom while scrolling
    No changes to your existing function signatures.
    """

    # ===== CSS: make the bar sticky and style it "ditto" =====
    st.markdown(
        """
<style>
/* keep room so sticky bar doesn't cover content */
.main .block-container { padding-bottom: 110px !important; }

/* sticky wrapper */
#sticky-chatbar {
  position: fixed; 
  left: 50%;
  transform: translateX(-50%);
  bottom: 14px;
  width: min(860px, 94vw);
  z-index: 9999;
}

/* row layout inside the bar */
#sticky-chatbar .bar-wrap {
  display: grid; 
  grid-template-columns: 48px 1fr 72px; 
  gap: 10px; 
  align-items: center;
}

/* the input itself (light, rounded like the screenshot) */
#sticky-chatbar [data-testid="stChatInput"] textarea,
#sticky-chatbar [data-testid="stChatInput"] input{
  background: #ffffff !important;
  color: #111827 !important;                  /* near black */
  border: 1px solid #e5e7eb !important;       /* gray-200 */
  border-radius: 28px !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
  padding: 12px 16px !important;
}
#sticky-chatbar [data-testid="stChatInput"] ::placeholder { color:#9ca3af !important; }

/* left '+' circle (black on white) */
.plus-btn {
  width: 44px; height: 44px; border-radius: 50%;
  background: #ffffff; 
  border: 1px solid #e5e7eb;
  display:flex; align-items:center; justify-content:center;
  font-size: 22px; font-weight: 600; color:#111827;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  cursor: pointer; user-select:none;
  transition: transform .15s ease, background .15s ease;
}
.plus-btn:hover { background:#f9fafb; transform: scale(1.04); }

/* make uploader minimal inside popover */
.plain-uploader [data-testid="stFileUploaderDropzone"]{
  border:none !important; background:transparent !important; padding:0 !important;
}
.plain-uploader svg{ display:none; }
.plain-uploader p{ margin:0 !important; }

/* right-side icons */
.right-icons { display:flex; gap:10px; justify-content:flex-end; align-items:center; }
.mic { font-size: 18px; color:#111827; }

/* blue action badge (light blue outer, blue inner) */
.blue-badge {
  width: 44px; height: 44px; border-radius: 50%;
  background: #e6f0ff;              /* light blue halo */
  display:flex; align-items:center; justify-content:center;
}
.blue-badge-inner {
  width: 32px; height: 32px; border-radius: 50%;
  background: #0a66ff;               /* blue core */
  display:flex; align-items:center; justify-content:center;
  color:#ffffff; font-weight:700; font-size: 12px;
}
</style>
""",
        unsafe_allow_html=True,
    )

    # ===== Sticky container (left + | input | mic + blue badge) =====
    st.markdown('<div id="sticky-chatbar"><div class="bar-wrap">', unsafe_allow_html=True)

    # Left '+' -> popover with uploader
    left_col, mid_col, right_col = st.columns([0.08, 0.84, 0.08], gap="small")

    with left_col:
        st.markdown('<div class="plus-btn">+</div>', unsafe_allow_html=True)
        if hasattr(st, "popover"):
            with st.popover("Attach image", use_container_width=True):
                st.markdown('<div class="plain-uploader">', unsafe_allow_html=True)
                img = st.file_uploader("Upload image", type=["png","jpg","jpeg","webp"], key="chat_img")
                st.markdown('</div>', unsafe_allow_html=True)
                if img is not None:
                    st.success(f"Attached: {img.name}")
        else:
            with st.expander("Attach image"):
                st.markdown('<div class="plain-uploader">', unsafe_allow_html=True)
                img = st.file_uploader("Upload image", type=["png","jpg","jpeg","webp"], key="chat_img")
                st.markdown('</div>', unsafe_allow_html=True)
                if img is not None:
                    st.success(f"Attached: {img.name}")

    with mid_col:
        prompt = st.chat_input("Ask anything")

    with right_col:
        st.markdown(
            '<div class="right-icons">'
            '<span class="mic">🎤</span>'
            '<span class="blue-badge"><span class="blue-badge-inner">﹙﹚</span></span>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div></div>", unsafe_allow_html=True)  # close .bar-wrap & #sticky-chatbar

    # ===== Logic (unchanged) =====
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
