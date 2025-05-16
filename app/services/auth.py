import streamlit as st
import logging
import os

logger = logging.getLogger(__name__)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGO_PATH = os.path.join(PROJECT_ROOT, "public", "logo_dark.png")


def check_password() -> bool:
    if st.session_state.get("password_correct"):
        return True

    _col_left_spacer, col_form, _col_right_spacer = st.columns([0.5, 1, 0.5])
    
    with col_form:
        
        logo_col1, logo_col2, logo_col3 = st.columns([1, 2, 1])
        
        with logo_col2:
            st.image(LOGO_PATH, width=200, use_container_width=True)
        
        #st.write("SQL Chatbot")
        with st.form("login_form"):
            st.text_input(
                "Brukernavn",
                key="username", 
                placeholder="admin"
            )
            st.text_input(
                "Passord",
                type="password",
                key="password",
                placeholder="admin" 
            )
            
            submitted = st.form_submit_button("Logg inn", use_container_width=True, type="primary")

            if submitted:
                correct_username = "admin" 
                correct_password = "admin"

                if st.session_state.username == correct_username and st.session_state.password == correct_password:
                    st.session_state["password_correct"] = True
                    st.session_state["user_identifier"] = st.session_state.username
                    logger.info(f"User '{st.session_state['user_identifier']}' logged in.")
                    
                    if "login_attempt_failed" in st.session_state:
                        del st.session_state["login_attempt_failed"]
                    st.rerun()
                else:
                    st.session_state["password_correct"] = False
                    st.error("😕 Brukernavn eller passord er feil.")
            
    return False