import streamlit as st
import os
from PIL import Image

# Oppdaterte konverteringsfaktorer for gCO₂e
# Basert på 19 gCO₂e/kWh for strøm i Norge (NVE 2019-tall for varedeklarasjon)
GCO2E_PER_HOUR_LED_10W = 0.01 * 19  # 0.01 kWh/time * 19 gCO₂e/kWh = 0.19 gCO₂e/time

def get_gco2e_equivalence_text(gco2e_value: float) -> str | None:
    """
    Genererer en tekst som setter gCO₂e-verdien i perspektiv med bruk av en 10W LED-pære.
    Velger en passende tidsenhet (sekunder, minutter, timer) basert på størrelsen på gCO₂e-verdien.

    Args:
        gco2e_value (float): Mengden gCO₂e som skal konverteres.

    Returns:
        str | None: En formatert streng med ekvivalensen, eller None hvis verdien er for liten.
    """
    if gco2e_value <= 0: # Endret til <= for å fange nøyaktig 0 også
        return None

    gco2e_per_minute_led = GCO2E_PER_HOUR_LED_10W / 60
    gco2e_per_second_led = gco2e_per_minute_led / 60

    # Prioriter den mest leselige enheten
    if gco2e_value >= GCO2E_PER_HOUR_LED_10W * 0.5: # Hvis det er 0.5 timer eller mer
        hours_led = gco2e_value / GCO2E_PER_HOUR_LED_10W
        return f" tilsvarer ca. {hours_led:.1f} timer med en 10W LED-pære."
    elif gco2e_value >= gco2e_per_minute_led * 0.8: # Hvis det er ca. 1 minutt eller mer (og mindre enn 0.5 timer)
        minutes_led = gco2e_value / gco2e_per_minute_led
        return f" tilsvarer ca. {minutes_led:.0f} minutter med en 10W LED-pære."
    elif gco2e_value >= gco2e_per_second_led: # Hvis det er minst 1 sekund (og mindre enn ca. 1 minutt)
        seconds_led = gco2e_value / gco2e_per_second_led
        return f" tilsvarer ca. {seconds_led:.0f} sekunder med en 10W LED-pære."
    
    return None


def render_sidebar(logo_path: str | None = None):
    """
    Renderer sidepanelet for Streamlit-applikasjonen.

    Viser logo hvis `logo_path` er gyldig.
    Viser informasjon om innlogget bruker, øktens totale tokenforbruk,
    og estimert gCO₂e-utslipp med en tekstlig ekvivalens.
    Hvis ingen tokens er brukt, vises en alternativ melding for gCO₂e.
    Inkluderer også en hjelpetekst for hvordan chatboten brukes og
    informasjon om datakilder og modell.

    Args:
        logo_path (str | None): Valgfri sti til en logofil som skal vises øverst i sidepanelet.
    """
    if logo_path:
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path) 
                st.sidebar.image(logo_path, use_container_width=True) # Endret til use_container_width
            except FileNotFoundError:
                st.sidebar.warning(f"Logofil ikke funnet: {logo_path}")
            except Exception as e:
                st.sidebar.error(f"Kunne ikke laste logofil: {e}")
        else:
            st.sidebar.warning(f"Logofil ikke funnet på sti: {logo_path}")
    
    st.sidebar.markdown("---")

    user_identifier = st.session_state.get('user_identifier', 'N/A')
    total_tokens = st.session_state.get('session_total_tokens', 0)
    total_gco2e = st.session_state.get('session_total_gco2e', 0.0)

    st.sidebar.markdown(f"👤 **Bruker:** {user_identifier}")
    st.sidebar.markdown(f"⚡ **Tokens brukt:** {total_tokens:,}")
    
    st.sidebar.markdown("---")

    gco2e_metric_label = "Estimert gCO₂e for økten 🌳"
    
    if total_gco2e > 0:
        gco2e_metric_value = f"{total_gco2e:.4f} gCO₂e"
        st.sidebar.markdown(f"**{gco2e_metric_label}**")
        st.sidebar.markdown(gco2e_metric_value)
        
        equivalence_text = get_gco2e_equivalence_text(total_gco2e)
        if equivalence_text:
            st.sidebar.caption(equivalence_text)
    else:
        # Vis en alternativ tekst hvis ingen gCO2e er generert enda
        st.sidebar.markdown(f"**{gco2e_metric_label}**")
        st.sidebar.markdown("Ingen aktivitet enda.") # Eller en annen passende melding


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
        *Strømmiks for LED-ekvivalent: 19 gCO₂e/kWh (Norge 2019)*
        """
    )
