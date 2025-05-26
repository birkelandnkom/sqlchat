import streamlit as st

st.set_page_config(layout="wide", page_title="Chatbot UI/UX Demo")

def display_chat_interface(chat_history_key: str, bot_name: str, initial_message: str):
    """
    Displays a generic chat interface.
    - chat_history_key: The key in st.session_state to store messages.
    - bot_name: The name of the bot for display purposes.
    - initial_message: The first message from the bot.
    """
    if chat_history_key not in st.session_state:
        st.session_state[chat_history_key] = [{"role": "assistant", "content": initial_message}]

    for message in st.session_state[chat_history_key]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input(f"Melding til {bot_name}..."):
        st.session_state[chat_history_key].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response = f"Dette er et simulert svar fra {bot_name} på meldingen din: '{prompt}'. I et reelt scenario ville dette vært et LLM-generert svar."
            if "hei" in prompt.lower() or "hallo" in prompt.lower():
                response = f"Hallo der! Dette er {bot_name} som svarer."
            elif "hvordan går det" in prompt.lower() or "går det bra" in prompt.lower():
                response = f"Jeg er bare en demo, men jeg har det kjempefint! Takk som spør, {bot_name} her."
            st.markdown(response)
            st.session_state[chat_history_key].append({"role": "assistant", "content": response})


@st.dialog("Diagram: Forhåndsvalg før Chatbot", width="large")
def show_alt1_diagram_dialog():
    """Displays the diagram for Alternative 1 in a dialog."""
    try:
        st.image("demo/images/1.png", caption="Alternativ 1: Forhåndsvalg før Chatbot", use_container_width=True)
    except Exception as e:
        st.error(f"Kunne ikke laste bildet for Alternativ 1: demo/images/1.png. Feil: {e}")
    if st.button("Lukk", key="close_diag_alt1_dialog_btn"):
        st.rerun()

@st.dialog("Diagram: Chatbot med automatisk routing", width="large")
def show_alt2_diagram_dialog():
    """Displays the diagram for Alternative 2 in a dialog."""
    image_url = "demo/images/2.png"
    try:
        st.image(image_url, caption="Alternativ 2: Chatbot med automatisk routing", use_container_width=True)
    except Exception as e:
        st.error(f"Kunne ikke laste bildet for Alternativ 2: {image_url}. Feil: {e}")
    if st.button("Lukk", key="close_diag_alt2_dialog_btn"):
        st.rerun()

@st.dialog("Diagram: Separate chatboter", width="large")
def show_alt3_diagram_dialog():
    """Displays the diagram for Alternative 3 in a dialog."""
    try:
        st.image("demo/images/3.png", caption="Alternativ 3: Separate chatboter", use_container_width=True)
    except Exception as e:
        st.error(f"Kunne ikke laste bildet for Alternativ 3: demo/images/3.png. Feil: {e}")
    if st.button("Lukk", key="close_diag_alt3_dialog_btn"):
        st.rerun()


def render_alternative_1():
    st.header("Alternativ 1: Forhåndsvalg før Chatbot")
    
    if st.button("Vis diagram: Forhåndsvalg", key="show_diag_alt1_btn"):
        show_alt1_diagram_dialog()

    st.markdown("""
    I denne modellen velger brukeren først konteksten eller verktøyet de vil at chatboten skal bruke.
    Når valget er gjort, routes LLMen til å kun ha den tilgjengelige MCPen som tilsvarer valget deres.
    """)

    if 'alt1_selection' not in st.session_state:
        st.session_state.alt1_selection = None
    if 'alt1_chat_history' not in st.session_state:
        st.session_state.alt1_chat_history = []

    options = ["MCP: Datakatalog", "MCP: Postgres", "RAG"]
    option_keys = ["MCP_Data_Catalog", "MCP_Postgres", "RAG"]

    if st.session_state.alt1_selection is None:
        st.subheader("Vennligst velg din interaksjonsmodus:")
        cols = st.columns(len(options))
        for i, option_text in enumerate(options):
            if cols[i].button(option_text, key=f"alt1_btn_{option_keys[i]}", use_container_width=True):
                st.session_state.alt1_selection = option_text
                st.session_state.alt1_chat_history = [{"role": "assistant", "content": f"Velkommen! Du chatter nå med den spesialiserte boten for {st.session_state.alt1_selection}. Hvordan kan jeg hjelpe deg?"}]
                st.rerun()

    if st.session_state.alt1_selection:
        st.subheader(f"Chatter med: {st.session_state.alt1_selection}")
        if st.button("Endre valg", key="alt1_change_selection"):
            st.session_state.alt1_selection = None
            st.session_state.alt1_chat_history = []
            st.rerun()

        display_chat_interface(
            chat_history_key='alt1_chat_history',
            bot_name=st.session_state.alt1_selection,
            initial_message=f"Du har valgt {st.session_state.alt1_selection}."
        )

def render_alternative_2():
    st.header("Alternativ 2: Chatbot med automatisk routing")
    st.markdown("""
    Chatboten analyserer spørringen
    og router den til riktig backend (MCP: Datakatalog, MCP: Postgres, eller RAG).
    """)

    if st.button("Vis diagram: Automatisk ruting", key="show_diag_alt2_btn"):
        show_alt2_diagram_dialog() 
                
    st.markdown("---")
    if 'alt2_chat_history' not in st.session_state:
        st.session_state.alt2_chat_history = [{"role": "assistant", "content": "Spør meg om hva som helst, så skal jeg prøve å route spørringen din riktig."}]

    for message in st.session_state.alt2_chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Melding til unified chatbot..."):
        st.session_state.alt2_chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            routing_info = ""
            if "katalog" in prompt.lower():
                routing_info = "(Simulert ruting til MCP: Datakatalog)"
            elif "postgres" in prompt.lower() or "database" in prompt.lower() or "sql" in prompt.lower():
                routing_info = "(Simulert ruting til MCP: Postgres)"
            elif "rag" in prompt.lower() or "dokument" in prompt.lower() or "søk" in prompt.lower():
                routing_info = "(Simulert ruting til RAG)"
            else:
                routing_info = "(Simulert ruting til Generell)"

            response = f"{routing_info} Dette er et simulert svar på din henvendelse: '{prompt}'"
            st.markdown(response)
            st.session_state.alt2_chat_history.append({"role": "assistant", "content": response})

def render_alternative_3():
    st.header("Alternativ 3: Separate chatboter")
    
    if st.button("Vis diagram: Separate chatboter", key="show_diag_alt3_btn"):
        show_alt3_diagram_dialog() 

    st.markdown("""
    To separate, tydelig avgrensede chatbot-grensesnitt:
    ett spesifikt for RAG-baserte spørringer og et annet for MCP verktøy.
    """)

    if 'alt3_rag_chat_history' not in st.session_state:
        st.session_state.alt3_rag_chat_history = [{"role": "assistant", "content": "Velkommen til RAG Chatboten! Hvordan kan jeg hjelpe deg med å finne informasjon i dokumenter?"}]
    if 'alt3_mcp_chat_history' not in st.session_state:
        st.session_state.alt3_mcp_chat_history = [{"role": "assistant", "content": "Velkommen til MCP Chatboten! Hvordan kan jeg bistå med dine datakatalog- eller postgres-spørringer?"}]

    tab1, tab2 = st.tabs(["RAG Chatbot", "MCP Chatbot"])

    with tab1:
        st.subheader("RAG Chatbot Grensesnitt")
        st.caption("Denne chatboten spesialiserer seg på Retrieval Augmented Generation fra din kunnskapsbase.")
        display_chat_interface(
            chat_history_key='alt3_rag_chat_history',
            bot_name="RAG Bot",
            initial_message="Spør meg om dokumentene dine!"
        )

    with tab2:
        st.subheader("MCP Chatbot Grensesnitt")
        st.caption("Denne chatboten er aktivert med MCP for å interagere med verktøy som datakataloger og postgres-databaser.")
        display_chat_interface(
            chat_history_key='alt3_mcp_chat_history',
            bot_name="MCP Bot",
            initial_message="Hvordan kan jeg hjelpe med dine dataverktøy?"
        )

st.sidebar.title("Chatbot arkitekturvalg")

if 'selected_alternative' not in st.session_state:
    st.session_state.selected_alternative = "Alternativ 1" 

if st.sidebar.button("Forhåndsvalg", key="sidebar_alt1", use_container_width=True):
    st.session_state.selected_alternative = "Alternativ 1"
    st.rerun() 

if st.sidebar.button("Intern routing", key="sidebar_alt2", use_container_width=True):
    st.session_state.selected_alternative = "Alternativ 2"
    st.rerun()

if st.sidebar.button("RAG / MCP seperat", key="sidebar_alt3", use_container_width=True):
    st.session_state.selected_alternative = "Alternativ 3"
    st.rerun()

if st.session_state.selected_alternative == "Alternativ 1":
    render_alternative_1()
elif st.session_state.selected_alternative == "Alternativ 2":
    render_alternative_2()
elif st.session_state.selected_alternative == "Alternativ 3":
    render_alternative_3()

st.sidebar.markdown("---")
st.sidebar.info("Ingen faktisk LLM- eller backend-prosessering er implementert.")
