# app.py — Streamlit frontend for DeskMate

import os
import re
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="DeskMate — IT Helpdesk", page_icon="🖥️", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
.stApp { background-color: #0b0f17; color: #e2e8f0; font-family: 'Inter', sans-serif; }
h2 { color: #f8fafc !important; font-weight: 700 !important; font-size: 2.2rem !important; letter-spacing: -0.05em !important; }
.subtitle { text-align: center; color: #94a3b8; font-size: 1rem; margin-bottom: 30px; }
.stButton>button { background-color: #1f2937 !important; border: 1px solid #374151 !important; color: #9ca3af !important; border-radius: 8px !important; font-size: 0.8rem !important; transition: all 0.2s ease !important; }
.stButton>button:hover { border-color: #3b82f6 !important; color: #3b82f6 !important; }
</style>
""", unsafe_allow_html=True)

from agent import DeskMateAgent

# ── Session state ──────────────────────────────────────────────────────────────
for key, default in [("history", []), ("messages", []), ("employee_id", None)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("<h2 style='text-align:center;margin-top:20px;'>🖥️ DeskMate</h2>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Your virtual IT helpdesk assistant.</div>", unsafe_allow_html=True)

col_empty, col_reset = st.columns([8, 2])
with col_reset:
    if st.button("Reset", use_container_width=True):
        st.session_state.history = []
        st.session_state.messages = []
        st.session_state.employee_id = None
        st.rerun()

# ── Chat history ────────────────────────────────────────────────────────────────
chat_box = st.container(height=450)
with chat_box:
    if not st.session_state.messages:
        st.markdown("""
        <div style="text-align:center;color:#64748b;padding-top:100px;">
            <div style="font-size:3.5rem;margin-bottom:10px;">💬</div>
            <h4 style="color:#cbd5e1;font-weight:500;">Hello! I'm DeskMate.</h4>
            <p>How can I assist you with your IT requests today?</p>
        </div>""", unsafe_allow_html=True)
    else:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

# ── Input handling ──────────────────────────────────────────────────────────────
def handle_message(user_input: str):
    # Detect employee ID mentioned inline (e.g. "I'm emp_003")
    match = re.search(r'\bemp_\d+\b', user_input, re.IGNORECASE)
    if match:
        st.session_state.employee_id = match.group(0).lower()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        st.session_state.messages.append({"role": "assistant", "content": "⚠️ `GEMINI_API_KEY` is not set. Please add it to your `.env` file."})
        return

    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.spinner("DeskMate is typing..."):
        try:
            agent = DeskMateAgent(api_key=api_key)
            result = agent.process(
                employee_id=st.session_state.employee_id,
                message=user_input,
                history=st.session_state.history,
            )
            # Update employee_id from any tool call that used one
            for step in result.get("trace", []):
                if step.get("step") == "Tool called" and "employee_id" in step.get("arguments", {}):
                    st.session_state.employee_id = step["arguments"]["employee_id"]

            st.session_state.messages.append({"role": "assistant", "content": result["response"]})
            st.session_state.history = result["conversation_history"]

        except Exception as exc:
            err = str(exc)
            if any(k in err for k in ("API key", "API_KEY", "Key not valid", "400")):
                content = "⚠️ **Invalid Gemini API Key.** Please update `GEMINI_API_KEY` in your `.env` file."
            else:
                content = "The service is temporarily unavailable. Please try again later."
            st.session_state.messages.append({"role": "assistant", "content": content})


user_input = st.chat_input("Ask an IT question (e.g. 'Check my VPN status' or 'Reset my password')...")
if user_input:
    handle_message(user_input)
    st.rerun()
