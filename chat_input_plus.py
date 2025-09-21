# chat_input_plus.py
import time
import streamlit as st


def run_chat_input(add_message, check_custom_response, chat_with_agent):
    """
    Sticky bottom bar styled like reference:
      • '+' circular button at bottom-left for image upload
      • rounded white chat input centered
      • mic + blue badge on right
      • input bar stays fixed at bottom when scrolling
    """

    # ===== CSS =====
    st.markdown("""
    <style>
    :root{
      --bar-width: min(860px, 94vw);
      --bar-bottom: 14px;
    }

    /* space for fixed bar */
    .main .block-container{ padding-bottom: 110px !important; }

    /* Fix chat input at bottom */
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
      background:#fff !important;
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

    /* left '+' circle */
    #chat-plus{
      position: fixed; bottom: var(--bar-bottom);
      left: calc(50% - var(--bar-width)/2 - 56px);
      width: 44px; height: 44px; border-radius: 50%;
      background:#fff; border:1px solid #e5e7eb;
      display:flex; align-items:center; justify-content:center;
      color:#111827; font-weight:600; font-size:22px;
      box-shadow:0 1px 2px rgba(0,0,0,0.04);
      cursor:pointer; z-index:9999;
      transition: transform .15s ease, background .15s ease;
    }
    #chat-plus:hover{ background:#f9fafb; transform:scale(1.05); }

    /* hide uploader UI (we'll show filename only) */
    .hidden-upload [data-testid="stFileUploaderDropzone"]{
      border:none !important; background:transparent !important; padding:0 !important;
    }
    .hidden-upload svg, .hidden-upload p{ display:none !important; }

    /* right icons */
    #chat-right{
      position: fixed; bottom: var(--bar-bottom);
      left: calc(50% + var(--bar-width)/2 + 12px);
      display:flex; gap:10px; align-items:center; z-index:9999;
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

    # ===== LEFT “+” BUTTON =====
    st.markdown('<div id="chat-plus">+</div>', unsafe_allow_html=True)
    # invisible uploader (still works, triggered manually)
    with st.container():
        st.markdown('<div class="hidden-upload">', unsafe_allow_html=True)
        img = st.file_uploader("Attach image", type=["png","jpg","jpeg","webp"], key="chat_img")
        st.markdown('</div>', unsafe_allow_html=True)
        if img is not None:
            st.toast(f"Attached: {img.name}")

    # ===== RIGHT ICONS =====
    st.markdown(
        '<div id="chat-right">'
        '<span class="mic">🎤</span>'
        '<span class="blue-badge"><span class="blue-inner">⏵</span></span>'
        '</div>',
        unsafe_allow_html=True
    )

    # ===== INPUT =====
    prompt = st.chat_input("Ask anything")
    if not prompt:
        return

    # ===== LOGIC (unchanged) =====
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
