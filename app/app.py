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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logging.getLogger('backend.token_tracer').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAVICON_PATH = os.path.join(PROJECT_ROOT, "public", "favicon.png")
LOGO_SIDEBAR_PATH = os.path.join(PROJECT_ROOT, "public", "logo_wide_text.png") # Or another logo

def initialize_session_state():
    """
    Initialiserer nødvendige nøkler i Streamlits session state.

    Setter standardverdier for agent, meldingshistorikk, token-tellere,
    brukeridentifikator, meldings-ID-teller og autentiseringsstatus
    hvis de ikke allerede eksisterer i session state.
    Forsøker også å initialisere agenten hvis brukeren er logget inn
    og agenten ikke allerede er lastet.
    """
    defaults = {
        "agent": None,
        "messages": [],
        "session_total_tokens": 0,
        "session_total_gco2e": 0.0,
        "user_identifier": "Unknown User",
        "msg_id_counter": 0,
        "password_correct": False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if st.session_state.agent is None and st.session_state.password_correct:
        st.session_state.agent = get_agent()


def run_chatbot_app():
    """
    Hovedfunksjonen for å kjøre Streamlit chatbot-applikasjonen.

    Setter opp sidekonfigurasjon (inkludert favicon) og tittel.
    Initialiserer session state.
    Håndterer visning av sidepanel (inkludert logo) og meldingshistorikk.
    Styrer logikken for å motta brukerinput, prosessere det via agenten
    (i en to-stegs prosess for å vise en spinner), og vise resultatet.
    Viser også en velkomstmelding.
    """
    page_icon_img = None
    try:
        page_icon_img = Image.open(FAVICON_PATH)
    except FileNotFoundError:
        logger.warning(f"Favicon not found at {FAVICON_PATH}. Using default.")
        page_icon_img = "🗃️" 

    st.set_page_config(
        page_title="Nkom SQL Chatbot",
        page_icon=page_icon_img,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.title("Nkom SQL Chatbot")

    initialize_session_state()

    if st.session_state.agent is None and st.session_state.password_correct:
        st.error("Chatbot agent kunne ikke lastes. Vennligst sjekk logger eller prøv å laste siden på nytt.")
        return

    render_sidebar(logo_path=LOGO_SIDEBAR_PATH)
    display_messages()

    if "processing_prompt" in st.session_state and st.session_state.processing_prompt is not None:
        process_agent_interaction()
    else:
        if prompt := st.chat_input("Still et spørsmål..."):
            handle_user_input(prompt)

    if not st.session_state.messages and st.session_state.password_correct:
        logger.info(f"Chat started by user: {st.session_state.user_identifier}")
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Velkommen! Still meg spørsmål om dataene i databasen.",
            "id": "welcome_msg"
        })
        st.rerun()


if __name__ == "__main__":
    if check_password():
        run_chatbot_app()

