from streamlit.components.v1 import html

if "user_input" not in st.session_state:
    st.session_state.user_input = ""

user_input_html = """
<style>
.chat-container {
    display: flex;
    width: 100%;
    max-width: 600px;
    margin: 10px auto;
}
.chat-input {
    flex: 1;
    padding: 10px 12px;
    border-radius: 25px;
    border: 2px solid #ccc;
    font-size: 16px;
    outline: none;
}
.upload-btn {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    border: 2px solid #333;
    display: flex;
    justify-content: center;
    align-items: center;
    margin-left: 8px;
    cursor: pointer;
    font-size: 24px;
    background-color: #fff;
}
.upload-btn:hover {
    background-color: #f0f0f0;
}
</style>

<div class="chat-container">
    <input type="text" id="chatInput" class="chat-input" placeholder="Say something...">
    <label class="upload-btn" for="fileUpload">+</label>
    <input type="file" id="fileUpload" style="display:none">
</div>

<script>
const input = document.getElementById('chatInput');
input.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        const value = input.value;
        if (value.trim() !== '') {
            window.parent.postMessage({type: 'USER_INPUT', value: value}, '*');
            input.value = '';
        }
    }
});
</script>
"""

html(user_input_html, height=60)

# --- Capture user input from Streamlit's message events ---
import streamlit.components.v1 as components

def handle_custom_input():
    import streamlit as st
    if "messages" not in st.session_state:
        st.session_state.messages = []
    msg = st.session_state.get("user_input")
    if msg:
        st.session_state.messages.append(msg)
        st.session_state.user_input = ""  # clear after processing
        return msg
    return None

user_message = handle_custom_input()

if user_message:
    # add to session
    st.session_state.current_session.append({"role": "User", "message": user_message})
    # generate agent response as before
    normalized_prompt = user_message.strip().lower()
    placeholder = st.empty()
    placeholder.markdown("<p style='color:gray; font-style:italic;'>Agent is typing...</p>", unsafe_allow_html=True)
    time.sleep(0.5)

    custom_answer = check_custom_response(normalized_prompt)
    if custom_answer:
        st.session_state.current_session.append({"role": "Agent", "message": custom_answer})
    else:
        answer = chat_with_agent(user_message, st.session_state.index, st.session_state.current_session)
        st.session_state.current_session.append({"role": "Agent", "message": answer})

    placeholder.empty()
