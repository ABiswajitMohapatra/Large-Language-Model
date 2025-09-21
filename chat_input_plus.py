# chat_input_plus.py
import time
import streamlit as st

def run_chat_input(add_message, check_custom_response, chat_with_agent):
    """
    Sticky bottom chat bar styled like your reference.
    The image uploader is a real, clickable '+' circle pinned to the
    bottom-left of the bar (no big uploader in the middle).
    Your function signatures remain unchanged.
    """

    # ---------- CSS: fix bar to bottom + make uploader a '+' circle ----------
    st.markdown("""
    <style>
    :root{
      --bar-width: min(860px, 94vw);
      --bar-bottom: 14px;
    }

    /* keep space so the fixed bar doesn't overlap page content */
    .main .block-container{ padding-bottom: 110px !important; }

    /* Fix the Streamlit chat input to the bottom center */
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

    /* REAL uploader styled as a '+' circle and pinned at bottom-left */
    #upload-hotspot [data-testid="stFileUploaderDropzone"]{
      position: fixed !important;
      left: calc(50% - var(--bar-width)/2 - 56px) !important;
      bottom: var(--bar-bottom) !important;
      width:44px !important; height:44px !important;
      border-radius:50% !important;
      border:1px solid #e5e7eb !important;
      background:#ffffff !important;
      box-shadow:0 1px 2px rgba(0,0,0,0.04) !important;
      padding:0 !important; margin:0 !important;
      z-index: 9999 !important;
    }
    /* kill default look & center inner button */
    #upload-hotspot [data-testid="stFileUploaderDropzone"] div[role="button"]{
      background: transparent !important;
      border: none !important;
      width:44px !important; height:44px !important;
      display:flex; align-items:center; justify-content:center;
      cursor:pointer;
    }
    /* hide default icon/text and draw a '+' */
    #upload-hotspot [data-testid="stFileUploaderDropzone"] svg,
    #upload-hotspot [data-testid="stFileUploaderDropzone"] p{ display:none !important; }
    #upload-hotspot [data-testid="stFileUploaderDropzone"] div[role="button"]::before{
      content: "+";
      font-size:22px; font-weight:600; color:#111827;
      line-height:1;
    }
    #upload-hotspot [data-testid="stFileUploaderDropzone"]:hover{
      background:#f9fafb !important;
      transform: scale(1.05);
      transition: transform .15s ease;
    }

    /* Right-side mic + blue badge pinned to bottom-right of the bar */
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

    # ---------- Render ONLY ONE uploader (our fixed '+' hotspot) ----------
    with st.container():
        st.markdown('<div id="upload-hotspot">', unsafe_allow_html=True)
        img = st.file_uploader(
            "Attach image",
            type=["png","jpg","jpeg","webp"],
            key="chat_img",
            label_visibility="collapsed",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        if img is not None:
            st.toast(f"Image attached: {img.name}")

    # ---------- Right-side decorative icons ----------
    st.markdown(
        '<div id="chat-right">'
        '<span class="mic">🎤</span>'
        '<span class="blue-badge"><span class="blue-inner">⏵</span></span>'
        '</div>',
        unsafe_allow_html=True
    )

    # ---------- The actual input (fixed to bottom) ----------
    prompt = st.chat_input("Ask anything")
    if not prompt:
        return

    # ---------- Logic (unchanged) ----------
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
