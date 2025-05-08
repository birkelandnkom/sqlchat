import chainlit as cl
import pandas as pd
import ast
import logging
from logging import getLogger
from io import BytesIO

from backend.agent_builder import build_agent
from backend.db_client import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = getLogger(__name__)

@cl.password_auth_callback
def auth_callback(username: str, password: str) -> cl.User | None:
    """
    Enkel passordautentisering for Proof of Concept.

    VIKTIG: Denne metoden er usikker og KUN for testing/PoC.
    I prod - bruk SSO/Oauth eller lignende.

    Args:
        username (str): Brukernavnet oppgitt av brukeren.
        password (str): Passordet oppgitt av brukeren.

    Returns:
        cl.User | None: Et cl.User objekt ved vellykket autentisering,
                       ellers None.
    """
    if username == "admin" and password == "admin":
        logger.info(f"Bruker '{username}' logget inn.")
        return cl.User(identifier="admin", metadata={"role": "admin", "provider": "credentials"})
    else:
        logger.warning(f"Feilet innloggingsforsøk for bruker '{username}'.")
        return None

@cl.on_chat_start
async def start_chat():
    """
    Initialiserer og konfigurerer chatbot-agenten ved starten av en ny chat.

    Funksjonen blir automatisk kalt av Chainlit via `@cl.on_chat_start`.
    Den bygger agenten ved hjelp av `build_agent()`, lagrer den i `cl.user_session`,
    og sender en velkomstmelding til brukeren. 
    """
    logger.info("Starter en ny chat...")
    user = cl.user_session.get("user")
    
    if user:
        logger.info(f"Chat startet av bruker: {user.identifier}")
    else:
        logger.info("Chat startet (ingen brukerinfo funnet i session - auth deaktivert?).")


    try:
        agent_executor = build_agent()
        cl.user_session.set("agent", agent_executor)
        logger.info("Agent bygget og lagret i minne.")
        await cl.Message(
            content="Velkommen! Still meg spørsmål om dataene i databasen.",
            author="chatbot"
        ).send()
    except Exception as e:
        logger.exception("Feilet i å bygge agent ved chat start")
        await cl.ErrorMessage(content=f"Klarte ikke initialisere chatboten: {e}").send()


async def process_sql_to_dataframe(sql_query: str, original_agent_text: str) -> tuple[str, pd.DataFrame | None]:
    """
    Utfører en gitt SQL-spørring mot databasen og forsøker å konvertere resultatet til en Pandas DataFrame.

    Funksjonen håndterer ulike returformater fra databaseklienten (`db.run`),
    inkludert lister av dicts og stringlists.
    
    Den oppdaterer også den opprinnelige agent-teksten for å reflektere
    resultatet av spørringen (suksess, ingen data, feil).

    Args:
        sql_query (str): SQL-spørringen som skal kjøres.
        original_agent_text (str): Den opprinnelige tekstresponsen fra agenten før SQL-prosessering.

    Returns:
        tuple[str, pd.DataFrame | None]: En tuple som inneholder:
            - Den endelige tekstbeskjeden som skal vises til brukeren.
            - En Pandas DataFrame med spørringsresultatene hvis vellykket og data finnes, ellers None.
    """
    df = None
    final_output_text = original_agent_text
    try:
        logger.info(f"Kjører SQL via db.run: {sql_query}")
        sql_result_structured = await cl.make_async(db.run)(sql_query, fetch="all", include_columns=True)
        logger.info(f"db.run ferdig, resultat type: {type(sql_result_structured)}")

        parsed_data_for_df = None

        if isinstance(sql_result_structured, list) and sql_result_structured:
            if all(isinstance(row, dict) for row in sql_result_structured):
                parsed_data_for_df = sql_result_structured
            else:
                 parsed_data_for_df = sql_result_structured # La Pandas prøve å håndtere det
        elif isinstance(sql_result_structured, str):
            potential_data_str = sql_result_structured.strip()
            if potential_data_str.startswith('[') and potential_data_str.endswith(']'):
                try:
                    parsed_data_for_df = ast.literal_eval(potential_data_str)
                except Exception:
                    # Hvis parsing feiler, behold string som tekstresultat
                    final_output_text = f"Spørring utført, men resultatformatet var uventet (ikke-tolkbar streng): {sql_result_structured}"
            elif potential_data_str: # Hvis det er en annen type string (f.eks. en statusmelding)
                 final_output_text = potential_data_str
            else: # Tom string
                 final_output_text = "Spørringen ble utført, men returnerte ingen resultater (tom streng)."
        elif sql_result_structured is not None:
             parsed_data_for_df = sql_result_structured

        # Forsøker å lage DataFrame hvis vi har parset data
        if parsed_data_for_df is not None:
            try:
                df = pd.DataFrame(parsed_data_for_df) if parsed_data_for_df else pd.DataFrame()
                if df is not None and not df.empty:
                    # Dårlig problemhåndtering...
                    if "beklager" not in final_output_text.lower() and "error" not in final_output_text.lower() and "feil" not in final_output_text.lower():
                         final_output_text = f"Her er resultatene for spørringen din:"
                else:
                    # Håndterer tilfeller der DataFrame blir tom
                    if isinstance(parsed_data_for_df, list) and not parsed_data_for_df: # Tom liste som input
                         final_output_text = "Spørringen kjørte vellykket, men returnerte ingen treff."
                    else:
                         final_output_text = "Spørringen resulterte i et tomt datasett."
                    df = None
            except Exception as df_err:
                final_output_text = f"Kunne ikke lage DataFrame fra resultatene: {df_err}\nRådata: {parsed_data_for_df}"
                df = None
    except Exception as db_err: # Generelle feil som ikke er håndtert over
        final_output_text = f"Beklager, en feil oppstod under kjøring av SQL eller behandling av resultat: {db_err}"
        df = None 

    return final_output_text, df


@cl.on_message
async def main(message: cl.Message):
    """
    Behandler meldinger fra brukeren.

    Denne funksjonen blir automatisk kalt av Chainlit via `@cl.on_message`.
    Den henter agenten, sender brukerens melding til agenten
    for behandling, og analyserer agentens respons og mellomsteg ('intermediate_steps').

    Hvis et int_step inneholdt en SQL-spørring (identifisert ved tool_name = getattr(action, 'tool')),
    kalles `process_sql_to_dataframe` for å utføre spørringen og formatere resultatene.

    Sender til slutt et svar tilbake til brukeren, som kan inkludere tekst,
    en tabellvisning (DataFrame) og en nedlastingslenke for CSV-fil av resultatene.
    Bruker Chainlit Steps for å visualisere agentens tankeprosess.

    Args:
        message (cl.Message): Chainlit-meldingsobjektet som inneholder brukerens input.
    """
    agent = cl.user_session.get("agent")
    if not agent:
        await cl.ErrorMessage(content="Chatbot agent er ikke startet").send()
        return

    prompt = message.content
    logger.info(f"Processing message: {prompt}")

    final_response_text = "Behandler..."
    final_df = None
    sql_query_found = None

    # Bruker cl.Step for å vise agentens tankeprosess i UI
    async with cl.Step(name="Agent Execution", show_input=True, language="text") as agent_step:
        agent_step.input = prompt
        try:
            response = await agent.ainvoke({"input": prompt})
            logger.info("Agent invoke ferdig.")
            agent_output_text = response.get('output', 'Beklager, jeg fikk ikke noe svar fra agenten.')
            intermediate_steps = response.get('intermediate_steps', [])

            if intermediate_steps:
                for idx, (action, observation) in enumerate(intermediate_steps):
                    tool_name = getattr(action, 'tool', 'Unknown Tool')
                    tool_input = str(getattr(action, 'tool_input', '')) 
                    step_name = f"Step {idx+1}: {tool_name}"
                    async with cl.Step(name=step_name, parent_id=agent_step.id) as tool_step:
                        tool_step.input = tool_input
                        tool_step.output = str(observation) 
                        # Sjekker om steget brukte et SQL-verktøy
                        if 'sql' in tool_name.lower() and 'query' in tool_name.lower():
                            sql_query_found = tool_input #Lagrer SQL
                            logger.info(f"Found SQL query in step {idx+1}: {sql_query_found}")
            else:
                 logger.info("Agenten meldte ingen intermediate steps")

            if sql_query_found:
                 final_response_text, final_df = await process_sql_to_dataframe(sql_query_found, agent_output_text)
                 agent_step.output = final_response_text # Oppdaterer hovedstegets output
            else:
                 logger.info("Ingen SQL ble kjørt av agenten")
                 final_response_text = agent_output_text
                 agent_step.output = final_response_text

        except Exception as e:
            logger.exception(f"Error når agenten kjørte eller prosesserte data")
            final_response_text = f"En feil oppstod: {e}"
            agent_step.is_error = True 
            agent_step.output = final_response_text
            final_df = None

    elements = []

    if final_df is not None and not final_df.empty:
        try:
            df_element = cl.Dataframe(data=final_df, name="Resultater", display="inline")
            elements.append(df_element)
            logger.info("Dataframe-element ble laget OK")

            output = BytesIO()
            final_df.to_csv(output, index=False)
            csv_bytes = output.getvalue()
            output.close()

            csv_file_element = cl.File(
                name="query_result.csv",
                content=csv_bytes,
                display="inline", 
                mime="text/csv"
            )
            elements.append(csv_file_element)
            logger.info("CSV for nedlastning ble laget OK")

        except Exception as el_err:
             logger.error(f"Error i å lage fil for nedlastning: {el_err}", exc_info=True)
             elements = [] # Resetter delvis opprettede elementer
             final_response_text += "\n\n*(Beklager, kunne ikke vise tabellen og/eller nedlastingslink.)*"

    # Sender meldingen til brukeren
    await cl.Message(
        content=final_response_text,
        elements=elements, 
        author="chatbot"
    ).send()