import streamlit as st
import time

def run_chat_input(add_message_func, check_custom_response_func, chat_with_agent_func):
    prompt = st.chat_input("Say something...")
    if prompt:
        add_message_func("User", prompt)
        normalized_prompt = prompt.strip().lower()

        placeholder = st.empty()
        placeholder.markdown(
            "<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True
        )
        time.sleep(0.5)  # simulate typing

        custom_answer = check_custom_response_func(normalized_prompt)
        if custom_answer:
            add_message_func("Agent", custom_answer)
        else:
            answer = chat_with_agent_func(prompt, st.session_state.index, st.session_state.current_session)
            add_message_func("Agent", answer)

        placeholder.empty()
