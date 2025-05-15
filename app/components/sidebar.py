import streamlit as st
import os
from PIL import Image

def render_sidebar(logo_path: str | None = None):
    """
    Renderer sidepanelet for Streamlit-applikasjonen.

    Viser logo hvis `logo_path` er gyldig.
    Viser øktens totale tokenforbruk og estimert gCO₂e-utslipp.
    Inkluderer også en hjelpetekst for hvordan chatboten brukes og
    informasjon om datakilder og modell.

    Args:
        logo_path (str | None): Valgfri sti til en logofil som skal vises øverst i sidepanelet.
    """
    if logo_path:
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path) 
                st.sidebar.image(logo_path)
            except FileNotFoundError:
                st.sidebar.warning(f"Logofil ikke funnet: {logo_path}")
            except Exception as e:
                st.sidebar.error(f"Kunne ikke laste logofil: {e}")
        else:
            st.sidebar.warning(f"Logofil ikke funnet på sti: {logo_path}")


    st.sidebar.title("Øktinformasjon")
    st.sidebar.metric(label="Totalt brukte tokens i økten", value=f"{st.session_state.get('session_total_tokens', 0):,}")
    st.sidebar.metric(label="Estimert gCO₂e for økten 🌳", value=f"{st.session_state.get('session_total_gco2e', 0.0):.4f} gCO₂e")
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        **Hvordan bruke chatboten:**
        1. Still et spørsmål i chat-feltet.
        2. Vær tydelig for best resultat.
        3. Chatboten vil generere SQL, kjøre den, og vise resultater.

        **Tilgjengelige data:**
        Spørsmål kan stilles mot tabeller som `employees`, `customers`, `invoices`, etc. (Se `db_client.py` for full liste).
        
        *Modell brukt: o3-mini*
        *Estimert utslipp per token: 0.0001 gCO₂e*
        """
    )
