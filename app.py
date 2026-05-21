import os
import re
import streamlit as st
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Set page config for a clean, minimal centered layout
st.set_page_config(
    page_title="DeskMate — AI IT Helpdesk Assistant",
    page_icon="🖥️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom premium styling
st.markdown("""
<style>
    /* Google Fonts import */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* Main body background matching a premium dark theme */
    .stApp {
        background-color: #0b0f17;
        color: #e2e8f0;
        font-family: 'Inter', sans-serif;
    }
    
    /* Headers styling */
    h2 {
        color: #f8fafc !important;
        font-weight: 700 !important;
        font-size: 2.2rem !important;
        letter-spacing: -0.05em !important;
        margin-bottom: 5px !important;
    }

    /* Subtitle */
    .subtitle {
        text-align: center;
        color: #94a3b8;
        font-size: 1rem;
        font-weight: 400;
        margin-bottom: 30px;
    }

    /* Chat bubble container styling */
    .chat-container {
        border-radius: 16px;
        background-color: #111827;
        border: 1px solid #1f2937;
        padding: 20px;
        margin-bottom: 20px;
    }

    /* Reset button style */
    .reset-btn-container {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 10px;
    }

    .stButton>button {
        background-color: #1f2937 !important;
        border: 1px solid #374151 !important;
        color: #9ca3af !important;
        border-radius: 8px !important;
        padding: 4px 12px !important;
        font-size: 0.8rem !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        border-color: #3b82f6 !important;
        color: #3b82f6 !important;
        background-color: rgba(59, 130, 246, 0.05) !important;
    }

    /* Scrollbar customization */
    ::-webkit-scrollbar {
        width: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #0b0f17;
    }
    ::-webkit-scrollbar-thumb {
        background: #1f2937;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #374151;
    }
</style>
""", unsafe_allow_html=True)

# Imports from codebase
from agent import DeskMateAgent
from mock_data import EMPLOYEES
from db import is_db_configured, get_db_cursor

# ── Session State Initialisation ───────────────────────────────────────────
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "employee_id" not in st.session_state:
    st.session_state.employee_id = None

# ── Main Layout ──
st.markdown("<h2 style='text-align: center; margin-top: 20px;'>🖥️ DeskMate</h2>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Your virtual IT helpdesk assistant. Ask any question or raise support requests.</div>", unsafe_allow_html=True)

# Clean "Reset Conversation" button in top right
col_empty, col_reset = st.columns([8, 2])
with col_reset:
    if st.button("Reset Conversation", use_container_width=True):
        st.session_state.chat_messages = []
        st.session_state.conversation_history = []
        st.session_state.employee_id = None
        st.rerun()

# Chat Loop Helper
def trigger_agent_run(user_query):
    # Proactive check for employee ID in user query (e.g., emp_003)
    match = re.search(r'\bemp_\d+\b', user_query, re.IGNORECASE)
    if match:
        st.session_state.employee_id = match.group(0).lower()

    # Initialize agent
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        st.session_state.chat_messages.append({
            "role": "assistant", 
            "content": "Error: Gemini API key is missing. Please set the `GEMINI_API_KEY` in your `.env` file."
        })
        return


    # Add user message to UI state
    st.session_state.chat_messages.append({"role": "user", "content": user_query})

    # Call agent
    with st.spinner("DeskMate is typing..."):
        try:
            agent = DeskMateAgent(api_key=api_key)
            result = agent.process(
                employee_id=st.session_state.employee_id,
                message=user_query,
                history=st.session_state.conversation_history
            )
            
            # Post-call check: extract resolved employee ID from tools trace if any tool was called
            for step in result.get("trace", []):
                if step.get("step") == "Tool called":
                    args = step.get("arguments", {})
                    if "employee_id" in args:
                        st.session_state.employee_id = args["employee_id"]

            # Update state
            st.session_state.chat_messages.append({"role": "assistant", "content": result["response"]})
            st.session_state.conversation_history = result["conversation_history"]
        except Exception as e:
            err_msg = str(e)
            if "API key" in err_msg or "API_KEY" in err_msg or "Key not valid" in err_msg or "400" in err_msg:
                st.session_state.chat_messages.append({
                    "role": "assistant", 
                    "content": "⚠️ **Invalid Gemini API Key**: The current API key is invalid. Please update the `GEMINI_API_KEY` in your `.env` file."
                })
            else:
                st.session_state.chat_messages.append({
                    "role": "assistant", 
                    "content": "The service is temporarily unavailable. Please try again later."
                })

# Render Chat History Container
chat_container = st.container(height=450)
with chat_container:
    if not st.session_state.chat_messages:
        st.markdown(f"""
        <div style="text-align: center; color: #64748b; padding-top: 100px;">
            <div style="font-size: 3.5rem; margin-bottom: 10px;">💬</div>
            <h4 style="color: #cbd5e1; font-weight: 500;">Hello! I'm DeskMate.</h4>
            <p>How can I assist you with your IT requests today?</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

# Chat Input
user_input = st.chat_input("Type your IT query (e.g., 'I want to check my VPN status' or 'I need help resetting my password')...")
if user_input:
    trigger_agent_run(user_input)
    st.rerun()
