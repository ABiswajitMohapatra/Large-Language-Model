# chat_input_simple.py
import time
import streamlit as st


def run_chat_input(
    add_message,
    check_custom_response,
    chat_with_agent,
    *,
    placeholder_text: str = "Say something...",
    typing_delay: float = 0.5,
):
    """
    Minimal, safe drop-in for your chat input flow.
    Keeps your function signatures unchanged.

    Parameters
    ----------
    add_message : callable
        Your existing add_message(role, content)
    check_custom_response : callable
        Your existing check_custom_response(normalized_prompt)
    chat_with_agent : callable
        Your existing chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
    placeholder_text : str
        Label shown in st.chat_input
    typing_delay : float
        Seconds to show the 'Agent is typing...' indicator
    """
    # Chat input
    prompt = st.chat_input(placeholder_text)
    if not prompt:
        return

    # Add user message
    add_message("User", prompt)

    # Normalize prompt
    normalized_prompt = prompt.strip().lower()

    # Typing indicator
    placeholder = st.empty()
    placeholder.markdown(
        "<p style='color:gray; font-style:italic;'>Agent is typing...</p>",
        unsafe_allow_html=True,
    )
    time.sleep(max(typing_delay, 0.0))

    # Generate answer
    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(
            prompt,
            st.session_state.index,
            st.session_state.current_session,
        )
        add_message("Agent", answer)

    # Remove typing indicator
    placeholder.empty()

