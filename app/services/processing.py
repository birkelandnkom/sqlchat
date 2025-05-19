import streamlit as st
import pandas as pd
import ast
import logging
import json

from backend.agent_builder import build_agent
from backend.db_client import db
from backend.llm_client import llm as llm_instance

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
    # TODO: Vurder å legge til st.pyplot for mer komplekse, men da må LLM generere Python-kode for Matplotlib.
    # TODO: Vurder st.altair_chart for deklarative grafer.

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
      "chart_type": "navn_på_streamlit_funksjon_uten_st_prefiks", // f.eks. "bar_chart", "line_chart"
      "params": {{ // Nødvendige parametere for den valgte graf-funksjonen
        "x": "kolonnenavn_for_x_aksen_eller_null", // Sett til null hvis indeksen skal brukes
        "y": "kolonnenavn_for_y_aksen_eller_liste_med_kolonnenavn_eller_null", // Sett til null hvis alle numeriske kolonner skal brukes
        // Inkluder andre relevante parametere som 'size', 'color', 'lat', 'lon' basert på chart_type
      }},
      "title": "En kort, beskrivende tittel for grafen" // Valgfritt, men anbefalt
    }}
    Sørg for at kolonnenavn i 'params' nøyaktig matcher kolonnenavnene i DataFrame-skjemaet.
    Hvis en parameter (som 'x' eller 'y' for bar_chart/line_chart) ikke er strengt nødvendig fordi Streamlit
    kan utlede den fra data (f.eks. bruke indeksen for x, eller alle numeriske kolonner for y),
    kan du sette verdien til null eller utelate parameteren fra "params" hvis det er mer hensiktsmessig.
    For eksempel, for st.bar_chart(df_med_kategori_som_indeks), kan 'x' være null.
    """

    logger.info("Ber LLM om visualiseringsforslag...")
    try:
        response = llm_instance.invoke(prompt)
        
        content_str = response.content if hasattr(response, 'content') else str(response)
        
        logger.debug(f"LLM-svar for visualisering: {content_str}")

        json_block_match = ast.literal_eval(content_str)
        if isinstance(json_block_match, dict):
            suggestion = json_block_match
        else:
            try:
                start_index = content_str.find('{')
                end_index = content_str.rfind('}') + 1
                if start_index != -1 and end_index != -1:
                    json_str = content_str[start_index:end_index]
                    suggestion = json.loads(json_str)
                else:
                    logger.error("Fant ikke JSON-blokk i LLM-svar for visualisering.")
                    return None
            except json.JSONDecodeError as e:
                logger.error(f"Kunne ikke parse JSON fra LLM-svar for visualisering: {e}. Svar: {content_str}")
                return None
        
        if 'chart_type' in suggestion and 'params' in suggestion:
            logger.info(f"LLM foreslo visualisering: {suggestion}")
            return suggestion
        else:
            logger.error(f"Ugyldig format på visualiseringsforslag fra LLM: {suggestion}")
            return None

    except Exception as e:
        logger.exception(f"Feil under kall til LLM for visualiseringsforslag: {e}")
        return None
