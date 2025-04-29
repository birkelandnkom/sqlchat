# frontend.py

import streamlit as st
import pandas as pd
import json
import ast
import sqlparse

from sqlparse.tokens import DML
from backend import build_agent, db

st.set_page_config(page_title="Chatbot", page_icon="🗄️", layout="wide")
st.title("Chatbot PoC")

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

# Initialize session state
if "agent" not in st.session_state:
    st.session_state.agent = build_agent()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_df" not in st.session_state:
    st.session_state.last_df = None
    st.session_state.last_sql = None

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Ask me about your data…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_container = st.empty()

        with st.spinner("Thinking…"):
            try:
                result = st.session_state.agent.invoke({"input": prompt})
                answer = result["output"] if isinstance(result, dict) else str(result)

                sql_query = None
                sql_result = None

                # 🔍 Log intermediate steps for inspection
                if isinstance(result, dict) and "intermediate_steps" in result:
                    st.subheader("🔍 Intermediate Steps (debugging)")
                    for idx, step in enumerate(result["intermediate_steps"]):
                        action, observation = step
                        with st.expander(f"Step {idx + 1}: {getattr(action, 'tool', 'Unknown tool')}"):
                            st.markdown(f"**Tool Input**:\n```\n{action.tool_input}\n```")
                            st.markdown(f"**Observation**:\n```\n{observation}\n```")

                        if hasattr(action, "tool") and "sql_db_query" in action.tool.lower():
                            sql_query = action.tool_input
                            sql_result = observation

                if sql_query and sql_result:
                    try:
                        if isinstance(sql_result, list):
                            if all(isinstance(row, tuple) for row in sql_result):
                                columns = extract_columns_from_sql(sql_query)

                                if not columns or len(columns) != len(sql_result[0]):
                                    columns = [f"col_{i}" for i in range(len(sql_result[0]))]

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
                                    columns = [f"col_{i}" for i in range(len(parsed[0]))]

                                df = pd.DataFrame(parsed, columns=columns)
                            else:
                                df = pd.DataFrame(parsed)

                        else:
                            df = pd.DataFrame([sql_result])

                        st.session_state.last_df = df
                        st.session_state.last_sql = sql_query

                    except Exception as e:
                        st.error(f"⚠️ Failed to parse SQL result: {e}")
                        st.session_state.last_df = None
                        st.session_state.last_sql = None

                else:
                    st.session_state.last_df = None
                    st.session_state.last_sql = None

            except Exception as exc:
                answer = f"⚠️ **Error**: {exc}"
                st.session_state.last_df = None
                st.session_state.last_sql = None

            if st.session_state.last_df is not None and not st.session_state.last_df.empty:
                st.dataframe(st.session_state.last_df, use_container_width=True)
            else:
                # Otherwise fallback to natural language answer
                response_container.markdown(answer)


    st.session_state.messages.append({"role": "assistant", "content": answer})

# Display SQL and table if available
if st.session_state.last_df is not None:
    with st.expander("🔍 SQL Query and Result"):
        st.code(st.session_state.last_sql, language="sql")
        st.dataframe(st.session_state.last_df, use_container_width=True)

        csv = st.session_state.last_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download result as CSV",
            data=csv,
            file_name="query_result.csv",
            mime="text/csv",
        )

st.sidebar.header("Configuration")
st.sidebar.markdown("Edit `.env` to change API keys or credentials and restart the app.")
