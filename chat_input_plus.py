# chat_input_plus.py
import time
import streamlit as st

def run_chat_input(add_message, check_custom_response, chat_with_agent):
    # compact CSS to round the input; no text rendering of code anywhere
    st.markdown("""
    <style>
      [data-testid="stChatInput"] textarea,[data-testid="stChatInput"] input{
        border-radius:14px!important;border:1px solid rgba(0,0,0,.12)!important;
        box-shadow:0 2px 10px rgba(0,0,0,.06)!important;padding:12px 14px!important;
      }
    </style>
    """, unsafe_allow_html=True)

    prompt = st.chat_input("Say something...")
    if not prompt:
        return

    add_message("User", prompt)
    normalized_prompt = prompt.strip().lower()

    placeholder = st.empty()
    placeholder.markdown(
        "<p style='color:gray; font-style:italic;'>Agent is typing...</p>",
        unsafe_allow_html=True
    )
    time.sleep(0.5)

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        add_message("Agent", custom_answer)
    else:
        answer = chat_with_agent(prompt, st.session_state.index, st.session_state.current_session)
        add_message("Agent", answer)

    placeholder.empty()
