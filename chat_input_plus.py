# chat_input_plus.py
import time
import streamlit as st

def run_chat_input(
    add_message,
    check_custom_response,
    chat_with_agent,
    *,
    placeholder_text: str = "Say something...",
    typing_delay: float = 0.5,
    show_attached_note: bool = True,
):
    """
    Drop-in replacement for your chat input block, with:
      - a small 🖼️ icon to attach an image (popover/uploader + preview)
      - subtle "ChatGPT-like" input styling
      - no changes to your function signatures

    Parameters
    ----------
    add_message: callable
        Your existing add_message(role, content)
    check_custom_response: callable
        Your existing check_custom_response(normalized_prompt)
    chat_with_agent: callable
        Your existing chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
    placeholder_text: str
        The label for st.chat_input
    typing_delay: float
        Seconds to show the "Agent is typing..." indicator
    show_attached_note: bool
        If True, logs a small user message noting the attached image name

    Behavior
    --------
    - Stores a pending image in st.session_state.uploaded_image until your next message is sent.
    - After sending, it clears the pending image automatically.
    - Does NOT pass the image into your agent (no signature change). If/when you want,
      you can read the bytes inside this function and route them as needed.
    """

    # ---- session state for pending image ----
    if "uploaded_image" not in st.session_state:
        st.session_state.uploaded_image = None

    # ---- one-time styling (very light "chatgpt-ish" look) ----
    _inject_input_css()

    # ---- small image icon above the input (popover -> uploader) ----
    icon_col, info_col = st.columns([0.10, 0.90])
    with icon_col:
        # prefer popover when available; fall back to expander on older Streamlit
        if hasattr(st, "popover"):
            with st.popover("🖼️", use_container_width=True):
                _render_uploader()
        else:
            with st.expander("🖼️ Attach image"):
                _render_uploader()

    with info_col:
        if st.session_state.uploaded_image is not None:
            st.markdown(f"**Attached:** {st.session_state.uploaded_image.name}")

    # ---- your original flow (unchanged logic/signatures) ----
    prompt = st.chat_input(placeholder_text)
    if not prompt:
        return  # nothing to do this run

    # add user text message
    add_message("User", prompt)

    # optionally add a small note that an image is attached (without changing any signatures)
    if show_attached_note and st.session_state.uploaded_image is not None:
        add_message("User", f"[image attached: {st.session_state.uploaded_image.name}]")

    normalized_prompt = prompt.strip().lower()

    # typing indicator
    placeholder = st.empty()
    placeholder.markdown(
        "<p style='color:gray; font-style:italic;'>Agent is typing...</p>",
        unsafe_allow_html=True,
    )
    time.sleep(max(typing_delay, 0.0))

    # try custom response
    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        # If later you want to pass image bytes to your agent, do it here
        # bytes_data = st.session_state.uploaded_image.read() if st.session_state.uploaded_image else None
        # and then decide how you'll handle it without changing the public signature
        answer = chat_with_agent(
            prompt, st.session_state.index, st.session_state.current_session
        )
        add_message("Agent", answer)

    placeholder.empty()

    # clear pending image after sending
    st.session_state.uploaded_image = None


# ----------------- helpers -----------------

def _render_uploader():
    img = st.file_uploader("Attach an image", type=["png", "jpg", "jpeg", "webp"])
    if img is not None:
        st.session_state.uploaded_image = img
        st.image(img, caption=img.name, use_column_width=True)
        st.success("Image attached. It will be sent with your next message.")


def _inject_input_css():
    # very subtle, safe CSS that only targets chat input
    st.markdown(
        """
<style>
/* rounder, softer input like ChatGPT */
[data-testid="stChatInput"] textarea, 
[data-testid="stChatInput"] input {
  border-radius: 14px !important;
  border: 1px solid rgba(0,0,0,0.12) !important;
  box-shadow: 0 2px 10px rgba(0,0,0,0.06) !important;
  padding: 12px 14px !important;
}
/* tighten label spacing */
[data-testid="stChatInput"] label { margin-bottom: 4px !important; }
</style>
""",
        unsafe_allow_html=True,
    )
