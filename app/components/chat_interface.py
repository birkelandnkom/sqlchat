import streamlit as st
import pandas as pd
from io import BytesIO
import copy
import logging

from backend.token_tracer import TokenUsageCallbackHandler
from services.processing import process_sql_to_dataframe, TOKEN_TO_GCO2E_FACTOR

logger = logging.getLogger(__name__)

def display_messages():
    """
    Displays chat messages stored in Streamlit's session state.

    Iterates through messages and renders them according to their role (user or assistant).
    Handles the display of message content, Pandas DataFrames, CSV download buttons,
    and expandable sections for agent's intermediate steps.
    """
    for message in st.session_state.get("messages", []):
        avatar_icon = "🧑‍💻" if message["role"] == "user" else "🤖"
        with st.chat_message(message["role"], avatar=avatar_icon):
            st.markdown(message["content"])
            if "dataframe" in message and message["dataframe"] is not None:
                df_to_display = message["dataframe"]
                if not isinstance(df_to_display, pd.DataFrame):
                    try:
                        df_to_display = pd.DataFrame(df_to_display)
                    except Exception as e:
                        logger.error(f"Failed to convert message['dataframe'] to DataFrame: {e}")
                        st.error("Kunne ikke vise tabellen.")
                        continue
                
                if not df_to_display.empty:
                    st.dataframe(df_to_display)
                elif "dataframe" in message: 
                    st.caption("Tomt resultatsett.")

            if "csv_data" in message and message["csv_data"] is not None:
                st.download_button(
                    label="Last ned CSV",
                    data=message["csv_data"],
                    file_name="query_result.csv",
                    mime="text/csv",
                    key=f"download_{message.get('id', message['content'][:10])}"
                )
            if "agent_steps" in message and message["agent_steps"]:
                with st.expander("Vis agentens tankeprosess og SQL"):
                    for step in message["agent_steps"]:
                        st.markdown(f"**{step['type']}**: {step.get('name', 'N/A')}")
                        if "input" in step: st.code(step["input"], language="sql" if "sql" in step.get('name','').lower() else "text")
                        if "output" in step: st.text(str(step["output"])[:1000] + "..." if len(str(step["output"])) > 1000 else str(step["output"]))
                        if "log" in step: st.text(f"Log: {step['log']}")

def handle_user_input(prompt: str):
    """
    Manages new user input from the chat interface.

    Adds the user's message to the session state.
    Prepares a placeholder for the assistant's upcoming response.
    Stores the prompt and a unique ID for the assistant's message in session state
    to facilitate asynchronous-like processing.
    Triggers a Streamlit rerun to update the UI immediately with the user's message
    and the assistant's placeholder (which can show a spinner).

    Args:
        prompt (str): The text input provided by the user.
    """
    if not st.session_state.agent:
        st.error("Chatbot agent er ikke lastet. Prøv å laste siden på nytt.")
        st.session_state.messages.append({"role": "assistant", "content": "Chatbot agent er ikke lastet. Prøv å laste siden på nytt."})
        return

    msg_id_counter = st.session_state.get("msg_id_counter", 0) + 1
    st.session_state.msg_id_counter = msg_id_counter
    user_msg_id = f"user_{msg_id_counter}"
    st.session_state.messages.append({"role": "user", "content": prompt, "id": user_msg_id})

    asst_msg_id = f"asst_{msg_id_counter}"
    assistant_initial_content = "Behandler forespørselen din..."
    assistant_message_data = {
        "role": "assistant",
        "content": assistant_initial_content,
        "id": asst_msg_id
    }
    st.session_state.messages.append(assistant_message_data)
    
    st.session_state.processing_prompt = prompt 
    st.session_state.current_asst_msg_id = asst_msg_id
    st.rerun()


def process_agent_interaction():
    """
    Handles the core logic of interacting with the LangChain agent and processing its response.

    This function is intended to be called after `handle_user_input` has triggered a rerun
    and the UI shows a placeholder for the assistant's message.
    It retrieves the stored prompt and assistant message ID from session state.
    Invokes the agent, processes SQL queries if generated, calculates token usage and gCO2e,
    and formats the final response including any data or error messages.
    Updates the assistant's placeholder message in session state with the complete response.
    Triggers a final Streamlit rerun to display the updated message and sidebar metrics.
    """
    prompt = st.session_state.pop("processing_prompt", None)
    asst_msg_id = st.session_state.pop("current_asst_msg_id", None)

    if not prompt or not asst_msg_id:
        logger.warning("process_agent_interaction called without prompt or asst_msg_id in session_state.")
        return 

    message_to_update = next((m for m in reversed(st.session_state.messages) if m["id"] == asst_msg_id), None)
    if not message_to_update:
        logger.error(f"Could not find assistant message placeholder with ID {asst_msg_id} to update.")
        return

    token_callback = TokenUsageCallbackHandler()
    final_df = None
    sql_query_found = None
    agent_steps_for_display = []
    assistant_response_content = "" 

    try:
        logger.info(f"Processing message: '{prompt}' with agent.")
        response = st.session_state.agent.invoke(
            {"input": prompt},
            config={"callbacks": [token_callback]}
        )
        logger.info("Agent invoke finished.")
        agent_output_text = response.get('output', 'Beklager, jeg fikk ikke noe svar fra agenten.')
        intermediate_steps = response.get('intermediate_steps', [])

        if intermediate_steps:
            for idx, (action, observation) in enumerate(intermediate_steps):
                tool_name = getattr(action, 'tool', 'Unknown Tool')
                raw_tool_input = getattr(action, 'tool_input', '')
                tool_input_str = str(raw_tool_input)
                step_detail = {
                    "type": "Verktøy brukt", "name": tool_name, "input": tool_input_str,
                    "output": str(observation), "log": getattr(action, 'log', '').strip().replace('\n', ' ')
                }
                agent_steps_for_display.append(step_detail)
                if 'sql' in tool_name.lower() and \
                   ('query' in tool_name.lower() or 'tool' in tool_name.lower() or 'db' in tool_name.lower()):
                    sql_query_found = tool_input_str
                    logger.info(f"Found SQL query (Tool: {tool_name}): {sql_query_found}")
        else:
            logger.info("Agent reported no intermediate steps.")

        if sql_query_found:
            assistant_response_content, final_df = process_sql_to_dataframe(sql_query_found, agent_output_text)
        else:
            logger.info("No SQL query was executed by the agent, or the SQL tool was not recognized.")
            assistant_response_content = agent_output_text

    except Exception as e:
        logger.exception("Error during agent execution or data processing")
        assistant_response_content = f"En feil oppstod under behandling av din forespørsel: {type(e).__name__} - {e}"
        final_df = None
    finally:
        usage_report = token_callback.get_report()
        report_summary_for_log = copy.deepcopy(usage_report)
        report_summary_for_log.pop('detailed_steps', None) 
        logger.info(f"Token Usage Report Summary for query '{prompt}': {report_summary_for_log}")
        
        current_message_tokens = usage_report.get('total_tokens_used', 0)
        current_message_gco2e = current_message_tokens * TOKEN_TO_GCO2E_FACTOR

        usage_report_summary_for_user = (
            f"\n\n---\n*Ressursbruk (denne meldingen):*\n"
            f"*Tokens brukt: {current_message_tokens:,} "
            f"(Input: {usage_report.get('prompt_tokens_used',0):,}, Output: {usage_report.get('completion_tokens_used',0):,})*\n"
            f"*Estimert utslipp: {current_message_gco2e:.4f} gCO₂e 🌳*\n" 
            f"*Antall LLM-kall: {usage_report.get('successful_llm_requests',0)}*"
        )
        if usage_report.get('llm_errors',0) > 0:
             usage_report_summary_for_user += f"\n*Antall LLM-feil: {usage_report['llm_errors']}*"

        assistant_response_content += usage_report_summary_for_user
        
        st.session_state.session_total_tokens += current_message_tokens
        st.session_state.session_total_gco2e += current_message_gco2e

        message_to_update["content"] = assistant_response_content
        if final_df is not None: 
            message_to_update["dataframe"] = final_df 
            if not final_df.empty: 
                output = BytesIO()
                final_df.to_csv(output, index=False)
                csv_bytes = output.getvalue()
                output.close()
                message_to_update["csv_data"] = csv_bytes
            else: 
                message_to_update.pop("csv_data", None) 
        else: 
            message_to_update.pop("dataframe", None)
            message_to_update.pop("csv_data", None)

        if agent_steps_for_display:
            message_to_update["agent_steps"] = agent_steps_for_display
        else: 
            message_to_update.pop("agent_steps", None)

        st.rerun()
