import logging
from logging import getLogger
import streamlit as st
from agent_builder import build_agent
from db_client import db  # brukes for metadata om nødvendig
import pandas as pd
import json
import ast
import time
import sqlparse
from sqlparse.tokens import DML

# Logging-konfigurasjon
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = getLogger(__name__)

# Streamlit-oppsett
st.set_page_config(page_title='Chatbot', page_icon='🗄️', layout='wide')
st.title('Chatbot PoC')

# Initialize session state
if 'agent' not in st.session_state:
    logger.info('Initialiserer agent i session_state')
    st.session_state.agent = build_agent()
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'last_df' not in st.session_state:
    st.session_state.last_df = None
    st.session_state.last_sql = None

# Hjelpefunksjon for å ekstrahere kolonner fra SQL
def extract_columns_from_sql(sql_query: str):
    """Extract clean column names from a SQL SELECT query."""
    parsed = sqlparse.parse(sql_query)[0]
    columns = []
    in_select = False
    for token in parsed.tokens:
        if token.ttype == DML and token.value.upper() == "SELECT":
            in_select = True
        elif in_select:
            if token.ttype is None:
                columns_part = token.value.split("FROM")[0]
                columns_raw = [col.strip() for col in columns_part.split(",")]

                for col in columns_raw:
                    if " as " in col.lower():
                        clean_name = col.split(" as ")[-1].strip()
                    else:
                        if "(" in col and ")" in col:
                            func_name = col.split("(")[0].strip()
                            clean_name = func_name.lower()
                        else:
                            clean_name = col.strip()
                    columns.append(clean_name)
                break
    return columns

# Vis chat-historikk
for msg in st.session_state.messages:
    with st.chat_message(msg['role']):
        st.markdown(msg['content'])

# Chat-input
if prompt := st.chat_input('Ask me about your data…'):
    logger.info('Bruker spurte: %s', prompt)
    st.session_state.messages.append({'role': 'user', 'content': prompt})
    with st.chat_message('user'):
        st.markdown(prompt)

    # Assistant-respons
    with st.chat_message('assistant'):
        response_container = st.empty()
        intermediate_steps = []
        with st.spinner('Thinking…'):
            try:
                result = st.session_state.agent.invoke({'input': prompt})
                logger.info('LLM-resultat mottatt')

                # Hent SQL-spørring og resultat
                sql_query = None
                sql_result = None
                for idx, (action, observation) in enumerate(result.get('intermediate_steps', [])):
                    intermediate_steps.append((idx, action, observation))
                    if hasattr(action, 'tool') and 'sql_db_query' in action.tool.lower():
                        sql_query = action.tool_input
                        sql_result = observation
                        logger.info('SQL-spørring utført: %s', sql_query)

                # Konverter SQL-resultat til DataFrame
                if sql_query and sql_result:
                    try:
                        if isinstance(sql_result, list):
                            if all(isinstance(row, tuple) for row in sql_result):
                                columns = extract_columns_from_sql(sql_query)
                                if not columns or len(columns) != len(sql_result[0]):
                                    columns = [f'col_{i}' for i in range(len(sql_result[0]))]
                                df = pd.DataFrame(sql_result, columns=columns)
                            else:
                                df = pd.DataFrame(sql_result)
                        elif isinstance(sql_result, str):
                            try:
                                parsed = json.loads(sql_result)
                            except json.JSONDecodeError:
                                parsed = ast.literal_eval(sql_result)
                            if isinstance(parsed, list) and all(isinstance(row, tuple) for row in parsed):
                                columns = extract_columns_from_sql(sql_query)
                                if not columns or len(columns) != len(parsed[0]):
                                    columns = [f'col_{i}' for i in range(len(parsed[0]))]
                                df = pd.DataFrame(parsed, columns=columns)
                            else:
                                df = pd.DataFrame(parsed)
                        else:
                            df = pd.DataFrame([sql_result])

                        st.session_state.last_df = df
                        st.session_state.last_sql = sql_query
                        logger.info('DataFrame generert med %d rader', len(df))
                    except Exception as parse_err:
                        logger.error('Parsing av SQL-resultat feilet: %s', parse_err)
                        st.error(f'⚠️ Parsing feilet: {parse_err}')
                        st.session_state.last_df = None
                        st.session_state.last_sql = None
                else:
                    st.session_state.last_df = None
                    st.session_state.last_sql = None

            except Exception as exc:
                logger.exception('Feil i agent.invoke')
                st.error(f'⚠️ **Error**: {exc}')
                st.session_state.last_df = None
                st.session_state.last_sql = None

            # Hoved-output
            if st.session_state.last_df is not None and not st.session_state.last_df.empty:
                st.dataframe(st.session_state.last_df, use_container_width=True)
                csv = st.session_state.last_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label='📥 Download result as CSV',
                    data=csv,
                    file_name='query_result.csv',
                    mime='text/csv',
                    key='download_button_main',
                )
                logger.info('Last ned-knapp vist')
            else:
                if isinstance(result, dict) and 'output' in result:
                    response_text = ''
                    for chunk in result['output'].split():
                        response_text += chunk + ' '
                        response_container.markdown(response_text)
                        time.sleep(0.05)
                else:
                    response_container.markdown(result)

            # Debugging-expander
            if intermediate_steps:
                with st.expander('🔍 Intermediate Steps (debugging)'):
                    for idx, action, obs in intermediate_steps:
                        st.markdown(f"### Step {idx+1}: {getattr(action, 'tool', 'Unknown tool')}")
                        st.markdown(f"**Tool Input**:\n```\n{action.tool_input}\n```")
                        st.markdown(f"**Observation**:\n{obs}")
                        logger.debug('Viser steg %d i expander', idx+1)

    # Legg til i historikk
    st.session_state.messages.append({
        'role': 'assistant',
        'content': result.get('output') if isinstance(result, dict) else str(result)
    })
