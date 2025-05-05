import logging
from logging import getLogger
import streamlit as st
from backend.agent_builder import build_agent
from backend.db_client import db 
import pandas as pd
import time
import ast

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = getLogger(__name__)

st.set_page_config(page_title='Chatbot', page_icon='🗄️', layout='wide')
st.title('Chatbot PoC')

st.sidebar.title("Hvordan bruke Chatbot PoC")
st.sidebar.markdown("""
**1. Spørsmål → SQL**
- Chatbotten er **ikke** en generell samtaleagent.
- Skriv kun tekster som kan **oversettes til en SQL-spørring**.
- Unngå åpne, ustrukturerte spørsmål (f.eks. “Fortell meg om…”).

**2. Tilgjengelige tabeller**
Se hele schemas og tabeller her:
[Olist Brazilian E-Commerce Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
- `customers`
- `orders`
- `order_items`
- `products`
- `sellers`
- …og flere.

**3. Tips for bedre resultater**
- Vær presis: “Vis antall ordrer per måned for 2020”
- Inkluder gjerne kolonnenavn fra tabellen i spørsmålet.
- Store datamengder kan ta noe tid å kjøre — vær tålmodig.

**4. Feilmeldinger & debug**
- Hvis du får feil, sjekk at spørsmålet ditt er SQL-orientert.
- Bruk “🔍 Intermediate Steps” for å se hvilke verktøy (og SQL) som kjøres.
""")

if 'agent' not in st.session_state:
    logger.info('Initialiserer agent i session_state')
    st.session_state.agent = build_agent()
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'last_df' not in st.session_state:
    st.session_state.last_df = None
    st.session_state.last_sql = None

def display_intermediate_steps(intermediate_steps):
    """Displays the intermediate agent steps in an expander."""
    if intermediate_steps:
        with st.expander('🔍 Intermediate Steps (debugging)'):
            for idx, (action, obs) in enumerate(intermediate_steps):
                st.markdown(f"### Step {idx+1}: {getattr(action, 'tool', 'Unknown tool')}")
                tool_input_str = str(action.tool_input) if action.tool_input else "None"
                st.markdown(f"**Tool Input**:\n```\n{tool_input_str}\n```")
                st.markdown(f"**Observation**:\n{obs}")
                logger.debug('Viser steg %d i expander', idx+1)

def display_results(response_container, agent_output_text):
    """Displays the final results: DataFrame or text."""
    if st.session_state.last_df is not None and not st.session_state.last_df.empty:
        response_container.dataframe(st.session_state.last_df, use_container_width=True)
        try:
            csv = st.session_state.last_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label='📥 Download result as CSV',
                data=csv,
                file_name='query_result.csv',
                mime='text/csv',
                key=f'download_button_{len(st.session_state.messages)}',
            )
            logger.info('Last ned-knapp vist for DataFrame')
        except Exception as e:
            logger.error(f"Error generating CSV: {e}")
            st.error("Could not generate CSV for download.")
    elif agent_output_text:
        streamed_text = ""
        for chunk in agent_output_text.split():
            streamed_text += chunk + " "
            response_container.markdown(streamed_text)
            time.sleep(0.02)
        response_container.markdown(streamed_text)
        logger.info('Viste tekstlig svar fra agent.')
    else:
        response_container.markdown("Jeg kunne ikke finne et svar eller generere data for dette spørsmålet.")
        logger.info('Ingen DataFrame eller tekstlig svar å vise.')


def process_agent_response(result):
    """Processes the agent's response, attempts to fetch data via db.run if SQL was used."""
    sql_query = None
    agent_original_output = result.get('output', '')
    final_output_text = agent_original_output
    intermediate_steps = result.get('intermediate_steps', [])
    df = None
    st.session_state.last_df = None
    st.session_state.last_sql = None

    for action, observation in intermediate_steps:
        tool_name = getattr(action, 'tool', '').lower()
        if 'sql' in tool_name and 'query' in tool_name:
            sql_query_input = action.tool_input
            if isinstance(sql_query_input, dict) and 'query' in sql_query_input:
                 sql_query = str(sql_query_input['query']) # Handle dict input
            elif isinstance(sql_query_input, str):
                 sql_query = sql_query_input
            else:
                 logger.warning(f"Unexpected SQL tool input type: {type(sql_query_input)}. Trying to convert to string.")
                 sql_query = str(sql_query_input)

            if sql_query:
                logger.info(f"Agent generated SQL: {sql_query}")
                break 

    if sql_query:
        st.session_state.last_sql = sql_query
        try:
            sql_result_structured = db.run(sql_query, fetch="all", include_columns=True)
            logger.info(f"db.run returned type: {type(sql_result_structured)}") # Log the type

            # --- Start Modification ---
            parsed_data_for_df = None

            if isinstance(sql_result_structured, list) and sql_result_structured:
                 if all(isinstance(row, dict) for row in sql_result_structured):
                    logger.info(f"db.run returned list of {len(sql_result_structured)} dicts.")
                    parsed_data_for_df = sql_result_structured
                 else:
                    logger.warning("db.run returned list, but not list of dicts. Attempting basic list processing.")
                    parsed_data_for_df = sql_result_structured

            elif isinstance(sql_result_structured, str):
                logger.info(f"db.run returned a string: '{sql_result_structured[:100]}...'") # Log snippet
                potential_data_str = sql_result_structured.strip()
                if potential_data_str.startswith('[') and potential_data_str.endswith(']'):
                    try:
                        parsed_result = ast.literal_eval(potential_data_str)
                        if isinstance(parsed_result, list):
                            logger.info(f"Successfully parsed string from db.run into a list of {len(parsed_result)} items.")
                            parsed_data_for_df = parsed_result
                        else:
                            logger.warning("Parsed string from db.run but did not result in a list.")
                            final_output_text = f"Query executed, but result format was unexpected (parsed non-list): {sql_result_structured}"
                    except (ValueError, SyntaxError, MemoryError) as parse_err:
                        logger.error(f"Failed to parse string from db.run: {parse_err}")
                        final_output_text = f"Query executed, but result format was unexpected (unparseable string): {sql_result_structured}"
                elif potential_data_str:
                     logger.info("db.run returned a simple string (e.g., count or status message).")
                     final_output_text = potential_data_str
                else: 
                     logger.info("db.run returned an empty string.")
                     final_output_text = "Query executed successfully but returned no results (empty string)."


            elif sql_result_structured is not None:
                 logger.warning(f"db.run returned unexpected type: {type(sql_result_structured)}. Attempting direct processing.")
                 parsed_data_for_df = sql_result_structured

            if parsed_data_for_df is not None:
                try:
                    df = pd.DataFrame(parsed_data_for_df)
                    if not df.empty:
                        logger.info(f'DataFrame generated via db.run/parsing with {len(df)} rows')
                        st.session_state.last_df = df
                        if final_output_text == agent_original_output:
                           final_output_text = f"Here are the results for your query:" 
                    elif isinstance(parsed_data_for_df, list) and not parsed_data_for_df:
                        logger.info("SQL query executed successfully but returned no results (empty list).")
                        final_output_text = "The query ran successfully but returned no matching data."
                        st.session_state.last_df = None 
                    else: 
                         logger.info("DataFrame created but is empty.")
                         final_output_text = "The query resulted in an empty dataset."
                         st.session_state.last_df = None

                except Exception as df_err:
                    logger.error(f"Error creating DataFrame from parsed data: {df_err}", exc_info=True)
                    st.error(f"⚠️ Error creating table from results: {df_err}")
                    final_output_text = f"Could not display the results as a table. Raw data: {parsed_data_for_df}"
                    st.session_state.last_df = None


        except Exception as db_err:
            logger.error(f'Error executing SQL via db.run or processing result: {db_err}', exc_info=True)
            st.error(f'⚠️ Error running SQL or processing results: {db_err}')
            final_output_text = f"Sorry, I encountered an error when trying to fetch the data: {db_err}"
            st.session_state.last_df = None

    else:
        logger.info("Agent did not execute a SQL query. Using agent's direct output.")
        st.session_state.last_df = None
        st.session_state.last_sql = None

    return final_output_text, intermediate_steps

for msg in st.session_state.messages:
    with st.chat_message(msg['role']):
        if isinstance(msg.get('content'), pd.DataFrame):
            st.dataframe(msg['content'], use_container_width=True)
        else:
            st.markdown(str(msg.get('content', ''))) 

if prompt := st.chat_input('Ask me about your data…'):
    logger.info(f'User asked: {prompt}')
    st.session_state.messages.append({'role': 'user', 'content': prompt})
    with st.chat_message('user'):
        st.markdown(prompt)

    with st.chat_message('assistant'):
        response_container = st.empty()
        intermediate_steps_data = []
        agent_final_output = "Thinking..."
        st.session_state.last_df = None 
        st.session_state.last_sql = None 


        with st.spinner('Thinking…'):
            try:
                agent_response = st.session_state.agent.invoke({'input': prompt})
                logger.info('LLM response received')

                agent_final_output, intermediate_steps_data = process_agent_response(agent_response)

            except Exception as exc:
                logger.exception('Feil i agent.invoke eller process_agent_response')
                st.error(f'⚠️ **Agent Error**: {exc}')
                agent_final_output = f"An error occurred: {exc}"
                intermediate_steps_data = [] 
                
        display_results(response_container, agent_final_output)

        display_intermediate_steps(intermediate_steps_data)

    st.session_state.messages.append({
        'role': 'assistant',
        'content': agent_final_output 
    })