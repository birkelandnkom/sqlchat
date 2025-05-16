import streamlit as st
import pandas as pd
import json
import os
import sys

PROJECT_ROOT_FOR_IMPORT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT_FOR_IMPORT not in sys.path:
    sys.path.append(PROJECT_ROOT_FOR_IMPORT)

from services.auth import check_password

PROJECT_ROOT_FOR_LOGS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FEEDBACK_LOG_FILE = os.path.join(PROJECT_ROOT_FOR_LOGS, "logs", "feedback_log.jsonl")

def load_feedback_data():
    """Laster inn tilbakemeldingsdata fra JSONL-filen."""
    logs = []
    if os.path.exists(FEEDBACK_LOG_FILE):
        try:
            with open(FEEDBACK_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        st.error(f"Kunne ikke dekode en linje i loggfilen: {line.strip()}")
                        continue
        except Exception as e:
            st.error(f"En feil oppstod under lesing av loggfilen: {e}")
            return []
    return logs

def display_admin_page():
    """Viser innholdet på adminsiden."""
    st.set_page_config(page_title="Admin - Logganalyse", layout="wide")
    st.title("Logganalyse")

    if not os.path.exists(FEEDBACK_LOG_FILE):
        st.warning(f"Loggfilen ({FEEDBACK_LOG_FILE}) ble ikke funnet. Ingen data å vise.")
        st.caption("Loggfilen blir opprettet når den første tilbakemeldingen blir gitt.")
        return

    logs = load_feedback_data()

    if not logs:
        st.info("Ingen tilbakemeldinger er logget ennå.")
        return

    st.subheader(f"Fant {len(logs)} loggoppføringer.")

    try:
        df = pd.DataFrame(logs)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        
        columns_to_show = [
            'timestamp', 'feedback_type', 'user_query', 
            'assistant_response', 'message_id', 'preceding_user_message_id'
        ]
        existing_columns_to_show = [col for col in columns_to_show if col in df.columns]
        for col in df.columns:
            if col not in existing_columns_to_show:
                existing_columns_to_show.append(col)
        
        df_display = df[existing_columns_to_show]

        st.dataframe(df_display, use_container_width=True)

        st.markdown("---")
        st.subheader("Rå loggdata (JSON)")
        st.caption("Klikk på en rad for å se detaljer.")
        
        for index, row in df.iterrows():
            with st.expander(f"Logg #{index + 1} - Tidspunkt: {row.get('timestamp', 'N/A')} - Type: {row.get('feedback_type', 'N/A')}"):
                st.json(row.to_dict())

    except Exception as e:
        st.error(f"En feil oppstod under behandling av loggdata for DataFrame: {e}")
        st.write("Rå loggdata:")
        st.json(logs)


# --- Hovedlogikk for siden ---
# Først, sjekk om brukeren er logget inn
if not st.session_state.get("password_correct"):
    st.warning("Vennligst logg inn via hovedsiden for å få tilgang.")
    # Vurder å kalle check_password() her hvis du vil vise login-skjema direkte på denne siden
    # Men det kan være bedre å henvise til hovedsiden for en konsistent opplevelse
    if st.button("Gå til innloggingssiden"):
        st.switch_page("app.py") # Streamlit's måte å bytte side på, navnet er filnavnet
else:
    # Deretter, sjekk om den innloggede brukeren er 'admin'
    if st.session_state.get("user_identifier") == "admin":
        display_admin_page()
    else:
        st.error("Utilgjengelig.")
        st.warning("Du har ikke de nødvendige rettighetene for å se denne siden.")
        st.info(f"Du er logget inn som: {st.session_state.get('user_identifier')}")
