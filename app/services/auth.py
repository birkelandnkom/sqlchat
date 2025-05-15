import streamlit as st
import logging

logger = logging.getLogger(__name__)

def check_password() -> bool:
    """
    Håndterer brukerautentisering via en enkel sjekk av brukernavn og passord.

    Bruker Streamlits session state for å lagre autentiseringsstatus.
    Ber om brukernavn og passord hvis brukeren ikke er autentisert.
    Tillater innloggingsforsøk og viser feilmeldinger ved feil legitimasjon.

    Returns:
        bool: True hvis brukeren er autentisert, ellers False.
    """
    if "password_correct" not in st.session_state:
        st.text_input("Username", key="username", placeholder="admin")
        st.text_input("Password", type="password", key="password", placeholder="admin")
        if st.button("Logg inn"):
            if st.session_state["username"] == "admin" and st.session_state["password"] == "admin":
                st.session_state["password_correct"] = True
                st.session_state["user_identifier"] = "admin"
                logger.info(f"User '{st.session_state['user_identifier']}' logged in.")
                st.rerun()
            else:
                st.error("😕 Brukernavn eller passord er feil.")
                st.session_state["password_correct"] = False
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Username", key="username", placeholder="admin")
        st.text_input("Password", type="password", key="password", placeholder="admin")
        if st.button("Logg inn"):
            if st.session_state["username"] == "admin" and st.session_state["password"] == "admin":
                st.session_state["password_correct"] = True
                st.session_state["user_identifier"] = "admin"
                logger.info(f"User '{st.session_state['user_identifier']}' logged in.")
                st.rerun()
            else:
                st.error("😕 Brukernavn eller passord er feil.")
                st.session_state["password_correct"] = False
        return False
    else:
        return True
