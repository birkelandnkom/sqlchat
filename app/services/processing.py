import streamlit as st
import pandas as pd
import ast
import logging

from backend.agent_builder import build_agent
from backend.db_client import db

logger = logging.getLogger(__name__)

TOKEN_TO_GCO2E_FACTOR = 0.0001

@st.cache_resource
def get_agent():
    """
    Bygger og returnerer LangChain SQL-agenten.

    Bruker Streamlits mellomlagring (@st.cache_resource) for å sikre at agenten
    kun bygges én gang per sesjon. Logger informasjon om byggeprosessen
    og håndterer potensielle feil.

    Returns:
        AgentExecutor | None: Den initialiserte LangChain agent executoren,
                              eller None hvis byggingen feiler.
    """
    logger.info("Attempting to build agent...")
    try:
        agent_executor = build_agent()
        logger.info("Agent built successfully.")
        return agent_executor
    except Exception as e:
        logger.exception("Failed to build agent in get_agent")
        st.error(f"Kritisk feil: Kunne ikke initialisere chatbot-agenten: {e}")
        return None

def process_sql_to_dataframe(sql_query: str, original_agent_text: str) -> tuple[str, pd.DataFrame | None]:
    """
    Utfører en gitt SQL-spørring mot databasen og forsøker å konvertere resultatet
    til en Pandas DataFrame.

    Args:
        sql_query (str): SQL-spørringen som skal utføres.
        original_agent_text (str): Den opprinnelige teksten fra agenten, brukt som
                                   en fallback-melding hvis DataFrame-konvertering feiler
                                   eller hvis det ikke er noe tabulært resultat.

    Returns:
        tuple[str, pd.DataFrame | None]: En tuple som inneholder:
            - final_output_text (str): En melding som beskriver resultatet,
                                       eller selve dataene hvis de ikke er tabulære.
            - df (pd.DataFrame | None): Den resulterende Pandas DataFrame hvis vellykket,
                                        ellers None.
    """
    df = None
    final_output_text = original_agent_text
    try:
        logger.info(f"Executing SQL via db.run: {sql_query}")
        sql_result_structured = db.run(sql_query, fetch="all", include_columns=True)
        logger.info(f"db.run finished, result type: {type(sql_result_structured)}")

        parsed_data_for_df = None

        if isinstance(sql_result_structured, list) and sql_result_structured:
            if all(isinstance(row, dict) for row in sql_result_structured):
                parsed_data_for_df = sql_result_structured
            else:
                logger.warning(f"SQL result is a list but not of dicts. Type of first element: {type(sql_result_structured[0]) if sql_result_structured else 'N/A'}. Attempting conversion.")
                parsed_data_for_df = sql_result_structured
        elif isinstance(sql_result_structured, str):
            potential_data_str = sql_result_structured.strip()
            if potential_data_str.startswith('[') and potential_data_str.endswith(']'):
                try:
                    parsed_data_for_df = ast.literal_eval(potential_data_str)
                    if not (isinstance(parsed_data_for_df, list) and all(isinstance(row, dict) for row in parsed_data_for_df)):
                        logger.warning(f"Parsed string to list, but it's not a list of dicts. Type: {type(parsed_data_for_df)}")
                except Exception as parse_err:
                    logger.warning(f"Could not parse SQL result string as list: {parse_err}. Raw data: {potential_data_str}")
                    final_output_text = f"Spørringen ble utført, men resultatformatet var uventet (streng som ikke kunne tolkes): {sql_result_structured}"
            elif potential_data_str:
                final_output_text = potential_data_str
            else:
                final_output_text = "Spørringen ble utført, men returnerte ingen resultater (tom streng)."
        elif sql_result_structured is None:
             final_output_text = "Spørringen ble utført, men returnerte ingen data (None)."
        else:
            logger.warning(f"SQL result has an unexpected type: {type(sql_result_structured)}. Attempting direct DataFrame conversion.")
            parsed_data_for_df = sql_result_structured

        if parsed_data_for_df is not None:
            try:
                if isinstance(parsed_data_for_df, list) and not parsed_data_for_df:
                    df = pd.DataFrame()
                elif not isinstance(parsed_data_for_df, (list, dict)):
                     df = pd.DataFrame([parsed_data_for_df])
                else:
                    df = pd.DataFrame(parsed_data_for_df)

                if df is not None and not df.empty:
                    if not any(keyword in final_output_text.lower() for keyword in ["beklager", "error", "feil", "kunne ikke"]):
                        final_output_text = "Her er resultatene for spørringen din:"
                else:
                    if isinstance(parsed_data_for_df, list) and not parsed_data_for_df:
                        final_output_text = "Spørringen kjørte vellykket, men returnerte ingen treff."
                    elif df is not None and df.empty:
                         final_output_text = "Spørringen resulterte i et tomt datasett."
                    df = None
            except Exception as df_err:
                logger.error(f"Kunne ikke lage DataFrame fra resultater: {df_err}. Rådata: {str(parsed_data_for_df)[:500]}", exc_info=True)
                final_output_text = f"Kunne ikke lage DataFrame fra SQL-resultater: {df_err}\nRådata mottatt: {str(parsed_data_for_df)[:200]}..."
                df = None
        elif sql_result_structured is None or (isinstance(sql_result_structured, str) and not sql_result_structured.strip()):
             if not final_output_text or final_output_text == original_agent_text:
                final_output_text = "Spørringen ble utført, men returnerte ingen data."
    except Exception as db_err:
        logger.error(f"Feil under SQL-kjøring eller resultatbehandling: {db_err}", exc_info=True)
        final_output_text = f"Beklager, en feil oppstod under kjøring av SQL eller behandling av resultat: {db_err}"
        df = None
    return final_output_text, df
