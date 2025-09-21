# chat_input_plus.py
import time
import streamlit as st

def run_chat_input(add_message, check_custom_response, chat_with_agent):
    """
    Minimal chat input block (clean + simple).
    Keeps your function signatures unchanged.
    """

    prompt = st.chat_input("Say something...")

    if prompt:
        # Add user message
        add_message("User", prompt)

        # Normalize prompt
        normalized_prompt = prompt.strip().lower()

        # Typing indicator
        placeholder = st.empty()
        placeholder.markdown(
            "<p style='color:gray; font-style:italic;'>Agent is typing...</p>",
            unsafe_allow_html=True
        )
        time.sleep(0.5)  # simulate typing

        # Generate answer
        custom_answer = check_custom_response(normalized_prompt)
        if custom_answer:
            add_message("Agent", custom_answer)
        else:
            answer = chat_with_agent(
                prompt,
                st.session_state.index,
                st.session_state.current_session
            )
            add_message("Agent", answer)

        # Remove typing indicator
        placeholder.empty()
