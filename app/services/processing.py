import streamlit as st
import pandas as pd
import ast
import logging
import json

from backend.agent_builder import build_agent
from backend.db_client import db
from backend.llm_client import llm as llm_instance
from backend.token_tracer import TokenUsageCallbackHandler 

logger = logging.getLogger(__name__)

TOKEN_TO_GCO2E_FACTOR = 0.0001

@st.cache_resource
def get_agent():
    """
    Bygger og returnerer LangChain SQL-agenten.

    Bruker Streamlits cache (@st.cache_resource) for å sikre at agenten
    kun bygges én gang per session. 

    Returns:
        AgentExecutor | None: Langchain agent executoren,
                              eller None ved error.
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
    Utfører en SQL-spørring mot databasen og prøver å konvertere resultatet
    til en Pandas DataFrame.

    Args:
        sql_query (str): SQL-spørringen .
        original_agent_text (str): Den opprinnelige teksten fra agenten, brukt som
                                   en fallback-melding hvis DataFrame-konvertering feiler
                                   eller hvis det ikke er noe resultat.

    Returns:
        tuple[str, pd.DataFrame | None]: En tuple som inneholder:
            - final_output_text (str): En melding som beskriver resultatet,
                                       eller selve dataene hvis de ikke er tabulære.
            - df (pd.DataFrame | None): Den resulterende Pandas DataFrame,
                                        None ved error.
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
                logger.warning(f"SQL result is a list but not of dicts. Type of first element: {type(sql_result_structured[0]) if sql_result_structured else 'N/A'}. Attempting direct conversion.")
                parsed_data_for_df = sql_result_structured
        elif isinstance(sql_result_structured, str):
            potential_data_str = sql_result_structured.strip()
            if potential_data_str.startswith('[') and potential_data_str.endswith(']'):
                try:
                    parsed_data_for_df = ast.literal_eval(potential_data_str)
                    if not (isinstance(parsed_data_for_df, list) and all(isinstance(row, dict) for row in parsed_data_for_df)):
                        logger.warning(f"Parsed string to list, but it's not a list of dicts. Type: {type(parsed_data_for_df)}. Fallback to original string.")
                        final_output_text = f"Spørringen ble utført, men resultatformatet var uventet (streng som ikke kunne tolkes til tabell): {sql_result_structured}"
                        parsed_data_for_df = None
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

def get_visualization_suggestion(df: pd.DataFrame) -> dict | None:
    """
    Ber en LLM om å foreslå en passende visualisering.

    Args:
        df (pd.DataFrame): df som skal visualiseres.

    Returns:
        dict | None: En dictionary med forslag til 'chart_type' og 'params' hvis vellykket,
                      ellers None. Format:
                      {
                          "chart_type": "bar_chart",
                          "params": {"x": "col_x", "y": "col_y"},
                          "title": "Foreslått tittel"
                      }
    """
    if df is None or df.empty:
        return None

    schema_parts = ["Kolonnenavn (Datatype):"]
    for col, dtype in df.dtypes.items():
        schema_parts.append(f"- {col} ({dtype})")
    schema_str = "\n".join(schema_parts)
    
    data_sample_str = df.head(3).to_string()
    available_charts = """
    - 'bar_chart': For søylediagram. Bruk st.bar_chart(data=df, x='kol_x', y='kol_y'). Hvis y er en liste med kolonner, lages grupperte søyler. Hvis x ikke er satt, brukes indeksen.
    - 'line_chart': For linjediagram. Bruk st.line_chart(data=df, x='kol_x', y='kol_y'). Hvis y er en liste med kolonner, lages flere linjer. Hvis x ikke er satt, brukes indeksen.
    - 'scatter_chart': For punktdiagram. Bruk st.scatter_chart(data=df, x='kol_x', y='kol_y', size='kol_size', color='kol_color'). 'size' og 'color' er valgfrie.
    - 'area_chart': For arealdiagram. Bruk st.area_chart(data=df, x='kol_x', y='kol_y').
    - 'map': For kartplot (hvis data inneholder lat/lon kolonner). Bruk st.map(data=df, lat='lat_kol', lon='lon_kol').
    """

    prompt = f"""
    Du er en ekspert på datavisualisering. Gitt følgende Pandas DataFrame-skjema og et dataeksempel,
    foreslå den mest passende Streamlit-graf-typen og de nødvendige parameterne for å visualisere dataene.
    Fokuser på å lage en meningsfull og lettfattelig visualisering.

    Tilgjengelige Streamlit graf-funksjoner og deres typiske bruk:
    {available_charts}

    DataFrame Skjema:
    {schema_str}

    Dataeksempel (de første 3 radene):
    {data_sample_str}

    Basert på dette, returner et JSON-objekt med følgende struktur:
    {{
      "chart_type": "navn_på_streamlit_funksjon_uten_st_prefiks",
      "params": {{
        "x": "kolonnenavn_for_x_aksen_eller_null",
        "y": "kolonnenavn_for_y_aksen_eller_liste_med_kolonnenavn_eller_null",
      }},
      "title": "En kort, beskrivende tittel for grafen"
    }}
    Sørg for at kolonnenavn i 'params' nøyaktig matcher kolonnenavnene i DataFrame-skjemaet.
    Hvis en parameter (som 'x' eller 'y') ikke er strengt nødvendig fordi Streamlit
    kan utlede den, sett verdien til null eller utelat parameteren.
    """

    logger.info("Requesting LLM for visualization suggestion...")
    
    vis_token_callback = TokenUsageCallbackHandler()
    suggestion = None

    try:
        response = llm_instance.invoke(
            prompt,
            config={"callbacks": [vis_token_callback]}
        )
        
        content_str = response.content if hasattr(response, 'content') else str(response)
        logger.debug(f"LLM response for visualization: {content_str}")

        json_block_match = None
        try:
            json_block_match = ast.literal_eval(content_str)
        except (ValueError, SyntaxError):
            try:
                start_index = content_str.find('{')
                end_index = content_str.rfind('}') + 1
                if start_index != -1 and end_index != -1:
                    json_str = content_str[start_index:end_index]
                    json_block_match = json.loads(json_str)
                else:
                    logger.error("Could not find JSON block in LLM response for visualization.")
            except json.JSONDecodeError as e:
                logger.error(f"Could not parse JSON from LLM response for visualization: {e}. Response: {content_str}")

        if isinstance(json_block_match, dict) and 'chart_type' in json_block_match and 'params' in json_block_match:
            suggestion = json_block_match
            logger.info(f"LLM suggested visualization: {suggestion}")
        else:
            logger.error(f"Invalid or incomplete visualization suggestion format from LLM: {json_block_match}")

    except Exception as e:
        logger.exception(f"Error during LLM call for visualization suggestion: {e}")
        st.toast(f"Feil under henting av visualiseringsforslag: {e}", icon="⚠️")
    finally:
        usage_report = vis_token_callback.get_report()
        
        viz_tokens_used = usage_report.get('total_tokens_used', 0)
        viz_prompt_tokens = usage_report.get('prompt_tokens_used', 0)
        viz_completion_tokens = usage_report.get('completion_tokens_used', 0)
        logger.info(
            f"Token Usage for Visualization Suggestion: "
            f"Total={viz_tokens_used} (Prompt={viz_prompt_tokens}, Completion={viz_completion_tokens}), "
            f"LLM Calls={usage_report.get('successful_llm_requests',0)}, "
            f"Errors={usage_report.get('llm_errors',0)}"
        )

        if viz_tokens_used > 0:
            current_message_gco2e = viz_tokens_used * TOKEN_TO_GCO2E_FACTOR
            
            if 'session_total_tokens' not in st.session_state:
                st.session_state.session_total_tokens = 0
            if 'session_total_gco2e' not in st.session_state: 
                st.session_state.session_total_gco2e = 0.0

            st.session_state.session_total_tokens += viz_tokens_used
            st.session_state.session_total_gco2e += current_message_gco2e
            
            logger.info(f"Session totals updated after visualization: Tokens={st.session_state.session_total_tokens}, gCO2e={st.session_state.session_total_gco2e:.4f}")

    return suggestion