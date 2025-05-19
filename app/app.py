import streamlit as st
import logging
import sys
import os
from PIL import Image

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.auth import check_password
from services.processing import get_agent
from components.sidebar import render_sidebar 
from components.chat_interface import display_messages, handle_user_input, process_agent_interaction
from services.feedback_logger import process_all_feedback


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logging.getLogger('backend.token_tracer').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAVICON_PATH = os.path.join(PROJECT_ROOT, "public", "favicon.png")
LOGO_SIDEBAR_PATH = os.path.join(PROJECT_ROOT, "public", "logo_wide_text.png")

def initialize_session_state():
    """
    Init av nødvendige streamlit session states.
    """
    defaults = {
        "agent": None,
        "messages": [],
        "session_total_tokens": 0,
        "session_total_gco2e": 0.0,
        "user_identifier": "Unknown User",
        "msg_id_counter": 0,
        "password_correct": False,
        "processed_feedback_ids": set()
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def chatbot_page_main_content():
    """
    Main content for chatbotten.
    Funksjonen lager en st.page som brukes som hovedside.
    """
    
    display_messages()
    process_all_feedback()

    if "processing_prompt" in st.session_state and st.session_state.processing_prompt is not None:
        process_agent_interaction()
    else:
        if prompt := st.chat_input("Still et spørsmål..."):
            handle_user_input(prompt)

    if not st.session_state.get("messages", []) and st.session_state.get("password_correct", False):
        logger.info(f"Chat started by user: {st.session_state.get('user_identifier', 'N/A')}")
        welcome_message_id = f"welcome_{st.session_state.get('msg_id_counter', 0) + 1}"
        st.session_state.msg_id_counter += 1
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Velkommen! Still meg spørsmål om dataene i databasen.",
            "id": welcome_message_id
        })
        st.rerun()
        
if __name__ == "__main__":
    page_icon_img = "🗃️"
    try:
        if os.path.exists(FAVICON_PATH):
            page_icon_img = Image.open(FAVICON_PATH)
        else:
            logger.warning(f"Favicon not found at {FAVICON_PATH}. Using default.")
    except Exception as e:
        logger.error(f"Error loading favicon: {e}. Using default.")

    st.set_page_config(
        page_title="Nkom SQL Chatbot",
        page_icon=page_icon_img,
        layout="wide",
        initial_sidebar_state="expanded"
    )

    initialize_session_state()

    if check_password():

        if st.session_state.agent is None:
            logger.info("User is logged in, attempting to initialize agent.")
            st.session_state.agent = get_agent()
            if st.session_state.agent:
                logger.info("Agent initialized successfully.")
            else:
                logger.error("Agent initialization failed after login.")
                st.error("Chatbot agent kunne ikke lastes. Vennligst sjekk logger eller prøv å laste siden på nytt.")
                st.stop()
        pages_for_navigation = [
            st.Page(chatbot_page_main_content, title="SQL Chatbot", icon="🤖", default=True),
            st.Page("pages/admin_page.py", title="Admin Panel", icon="⚙️")
        ]

        render_sidebar(logo_path=LOGO_SIDEBAR_PATH)
        st.title("Nkom SQL Chatbot")

        pg = st.navigation(pages_for_navigation)
        
        pg.run()

    else:
        pass
