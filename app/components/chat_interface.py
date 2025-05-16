import streamlit as st
import pandas as pd
from io import BytesIO
import copy
import logging
import numpy as np

from backend.token_tracer import TokenUsageCallbackHandler
from services.processing import process_sql_to_dataframe, TOKEN_TO_GCO2E_FACTOR, get_visualization_suggestion

logger = logging.getLogger(__name__)

def display_messages():
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for i, message in enumerate(st.session_state.get("messages", [])):
        message_id = message.get("id", f"msg_{i}")

        avatar_icon = "🧑‍💻" if message["role"] == "user" else "🤖"
        with st.chat_message(message["role"], avatar=avatar_icon):
            st.markdown(message["content"])
            
            current_df = None
            if "dataframe" in message and message["dataframe"] is not None:
                df_to_display = message["dataframe"]
                if not isinstance(df_to_display, pd.DataFrame):
                    try:
                        df_to_display = pd.DataFrame(df_to_display)
                    except Exception as e:
                        logger.error(f"Kunne ikke konvertere message['dataframe'] til DataFrame: {e}")
                        st.error("Kunne ikke vise tabellen.")
                        df_to_display = None 
                
                if df_to_display is not None:
                    current_df = df_to_display 
                    if not df_to_display.empty:
                        st.dataframe(df_to_display)
                    elif "dataframe" in message: 
                        st.caption("Tomt resultatsett.")
            
            if current_df is not None and not current_df.empty:
                if st.button("📊 Generer visualisering med AI", key=f"ai_vis_btn_{message_id}"):
                    st.session_state.ai_visualize_request = {
                        "message_id": message_id,
                        "dataframe_for_ai_processing": current_df.copy() 
                    }
                    if "ai_visualization_suggestion" in st.session_state:
                        del st.session_state.ai_visualization_suggestion
                    if "last_message_id_for_ai_viz" in st.session_state: 
                         del st.session_state.last_message_id_for_ai_viz
                    st.rerun()

                if st.session_state.get("ai_visualize_request", {}).get("message_id") == message_id:
                    with st.expander("AI-generert visualisering", expanded=True):
                        with st.spinner("🤖 AI tenker ut en passende visualisering..."):
                            if "ai_visualization_suggestion" not in st.session_state or \
                               st.session_state.get("last_message_id_for_ai_viz") != message_id:
                                
                                df_for_ai = st.session_state.ai_visualize_request["dataframe_for_ai_processing"]
                                suggestion = get_visualization_suggestion(df_for_ai)
                                
                                if suggestion:
                                    st.session_state.ai_visualization_suggestion = suggestion
                                    st.session_state.last_message_id_for_ai_viz = message_id
                                else:
                                    st.error("Beklager, AI-en kunne ikke generere et visualiseringsforslag for disse dataene.")
                                if "ai_visualize_request" in st.session_state:
                                    del st.session_state.ai_visualize_request
                                st.rerun()

            if "ai_visualization_suggestion" in st.session_state and \
               message_id == st.session_state.get("last_message_id_for_ai_viz"):
                
                suggestion = st.session_state.ai_visualization_suggestion
                df_to_plot_original = message.get("dataframe") 
                
                if df_to_plot_original is not None and not df_to_plot_original.empty:
                    if not isinstance(df_to_plot_original, pd.DataFrame):
                        try:
                            df_to_plot_original = pd.DataFrame(df_to_plot_original)
                        except:
                            st.error("Data for plotting er ikke i gyldig format.")
                            df_to_plot_original = None

                if df_to_plot_original is not None and not df_to_plot_original.empty:
                    try:
                        chart_type = suggestion.get("chart_type")
                        params = suggestion.get("params", {})
                        title = suggestion.get("title", "AI-generert graf")
                        
                        st.subheader(title)

                        plot_data_source = df_to_plot_original.copy()

                        x_col_name = params.get("x")
                        y_col_names = params.get("y")
                        
                        if y_col_names and not isinstance(y_col_names, list):
                            y_col_names = [y_col_names]
                        
                        valid_plot = True
                        if x_col_name and x_col_name not in plot_data_source.columns:
                            st.warning(f"AI foreslo x-kolonnen '{x_col_name}', som ikke finnes. Tilgjengelige: {', '.join(plot_data_source.columns)}. Prøver å bruke indeksen.")
                            x_col_name = None
                        
                        if y_col_names:
                            valid_y_cols = []
                            for y_col_check in y_col_names:
                                if y_col_check in plot_data_source.columns:
                                    valid_y_cols.append(y_col_check)
                                else:
                                    st.error(f"AI foreslo y-kolonnen '{y_col_check}', som ikke finnes. Tilgjengelige: {', '.join(plot_data_source.columns)}.")
                                    valid_plot = False
                                    break
                            y_col_names = valid_y_cols
                            if not y_col_names:
                                valid_plot = False
                        elif chart_type not in ["map"]:
                            numeric_cols = plot_data_source.select_dtypes(include=np.number).columns.tolist()
                            if numeric_cols:
                                y_col_names = numeric_cols
                                st.info(f"AI spesifiserte ikke y-kolonne(r). Bruker alle numeriske kolonner: {', '.join(y_col_names)}")
                            else:
                                st.error("AI spesifiserte ikke y-kolonne(r), og ingen numeriske kolonner ble funnet for automatisk valg.")
                                valid_plot = False
                        
                        if not valid_plot:
                            if "ai_visualization_suggestion" in st.session_state:
                                del st.session_state.ai_visualization_suggestion
                            return

                        if chart_type == "bar_chart":
                            st.bar_chart(plot_data_source, x=x_col_name, y=y_col_names)
                        elif chart_type == "line_chart":
                            st.line_chart(plot_data_source, x=x_col_name, y=y_col_names)
                        elif chart_type == "scatter_chart":
                            size_col = params.get("size")
                            color_col = params.get("color")
                            
                            if size_col and size_col not in plot_data_source.columns:
                                st.warning(f"AI foreslo 'size'-kolonnen '{size_col}', som ikke finnes. Fortsetter uten 'size'.")
                                size_col = None
                            if color_col and color_col not in plot_data_source.columns:
                                st.warning(f"AI foreslo 'color'-kolonnen '{color_col}', som ikke finnes. Fortsetter uten 'color'.")
                                color_col = None
                            
                            single_y_for_scatter = y_col_names[0] if y_col_names else None
                            if not (x_col_name and single_y_for_scatter): 
                                st.error("For punktdiagram må både en gyldig x- og y-kolonne være tilgjengelig.")
                            else:
                                st.scatter_chart(plot_data_source, x=x_col_name, y=single_y_for_scatter, size=size_col, color=color_col)
                        elif chart_type == "area_chart":
                            st.area_chart(plot_data_source, x=x_col_name, y=y_col_names)
                        elif chart_type == "map":
                            lat_col = params.get('lat')
                            lon_col = params.get('lon')
                            if lat_col and lon_col and lat_col in plot_data_source.columns and lon_col in plot_data_source.columns:
                                st.map(plot_data_source, latitude=lat_col, longitude=lon_col)
                            else:
                                st.error("Kunne ikke lage kart. AI må spesifisere gyldige 'lat'- og 'lon'-kolonner som finnes i dataene.")
                        else:
                            st.warning(f"Ukjent eller ustøttet graf-type fra AI: {chart_type}")
                        
                    except Exception as e:
                        logger.error(f"Kunne ikke rendre AI-foreslått graf: {e}", exc_info=True)
                        st.error(f"En feil oppstod under generering av AI-grafen: {e}")
                        if "ai_visualization_suggestion" in st.session_state:
                            del st.session_state.ai_visualization_suggestion

            if "csv_data" in message and message["csv_data"] is not None:
                st.download_button(
                    label="Last ned CSV",
                    data=message["csv_data"],
                    file_name="query_result.csv",
                    mime="text/csv",
                    key=f"download_{message_id}"
                )
            
            if "agent_steps" in message and message["agent_steps"]:
                with st.expander("Vis agentens tankeprosess og SQL"):
                    for step in message["agent_steps"]:
                        step_name = str(step.get('name', 'N/A'))
                        step_input = str(step.get("input", ""))
                        step_output = str(step.get("output", ""))
                        step_log = str(step.get("log", ""))

                        st.markdown(f"**{step.get('type', 'Ukjent Steg')}**: {step_name}")
                        if "input" in step: st.code(step_input, language="sql" if "sql" in step_name.lower() else "text")
                        if "output" in step: st.text(step_output[:1000] + "..." if len(step_output) > 1000 else step_output)
                        if "log" in step and step_log: st.text(f"Log: {step_log}")

            if message["role"] == "assistant":
                if message_id:
                    is_welcome_message = message_id.startswith("welcome_")
                    is_processing_message = message.get("content") == "Behandler forespørselen din..."
                    
                    if not is_welcome_message and not is_processing_message:
                        feedback_key = f"feedback_{message_id}"
                        st.feedback(options="thumbs", key=feedback_key)
                else:
                    logger.warning(f"Assistant message at index {i} is missing an ID. Feedback widget not shown.")


def handle_user_input(prompt: str):
    if not st.session_state.get("agent"):
        st.error("Chatbot agent er ikke lastet. Prøv å laste siden på nytt.")
        error_msg_id_counter = st.session_state.get("msg_id_counter", 0) + 1
        st.session_state.msg_id_counter = error_msg_id_counter
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Feil: Chatbot agent er ikke lastet. Kan ikke behandle forespørselen.",
            "id": f"error_{error_msg_id_counter}"
        })
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
    
    if "ai_visualize_request" in st.session_state:
        del st.session_state.ai_visualize_request
    if "ai_visualization_suggestion" in st.session_state:
        del st.session_state.ai_visualization_suggestion
    if "last_message_id_for_ai_viz" in st.session_state:
        del st.session_state.last_message_id_for_ai_viz

    st.rerun()


def process_agent_interaction():
    prompt_to_process = st.session_state.pop("processing_prompt", None)
    asst_msg_id_to_update = st.session_state.pop("current_asst_msg_id", None)

    if not prompt_to_process or not asst_msg_id_to_update:
        logger.warning("process_agent_interaction called without prompt or asst_msg_id in session_state.")
        return 

    message_to_update_index = -1
    for i, msg in enumerate(st.session_state.messages):
        if msg.get("id") == asst_msg_id_to_update:
            message_to_update_index = i
            break
    
    if message_to_update_index == -1:
        logger.error(f"Could not find assistant message placeholder with ID {asst_msg_id_to_update} to update.")
        st.session_state.messages.append({
            "role": "assistant", 
            "content": f"Intern feil: Kunne ikke oppdatere svar (ID: {asst_msg_id_to_update}).",
            "id": f"error_update_{asst_msg_id_to_update}"
        })
        st.rerun()
        return

    token_callback = TokenUsageCallbackHandler()
    final_df = None
    sql_query_found = None
    agent_steps_for_display = []
    assistant_response_content = "" 

    try:
        logger.info(f"Processing message: '{prompt_to_process}' with agent.")
        if not st.session_state.get("agent"):
            raise Exception("Agent not available for processing.")

        response = st.session_state.agent.invoke(
            {"input": prompt_to_process},
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
            logger.info("No SQL query was executed by the agent, or the SQL tool was not recognized by the logger.")
            assistant_response_content = agent_output_text

    except Exception as e:
        logger.exception("Error during agent execution or data processing")
        assistant_response_content = f"En feil oppstod under behandling av din forespørsel: {type(e).__name__} - {e}"
        final_df = None
    finally:
        usage_report = token_callback.get_report()
        report_summary_for_log = copy.deepcopy(usage_report)
        report_summary_for_log.pop('detailed_steps', None) 
        logger.info(f"Token Usage Report Summary for query '{prompt_to_process}': {report_summary_for_log}")
        
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
        
        st.session_state.session_total_tokens = st.session_state.get("session_total_tokens", 0) + current_message_tokens
        st.session_state.session_total_gco2e = st.session_state.get("session_total_gco2e", 0.0) + current_message_gco2e

        st.session_state.messages[message_to_update_index]["content"] = assistant_response_content
        
        if final_df is not None: 
            st.session_state.messages[message_to_update_index]["dataframe"] = final_df 
            if not final_df.empty: 
                output = BytesIO()
                final_df.to_csv(output, index=False)
                csv_bytes = output.getvalue()
                output.close()
                st.session_state.messages[message_to_update_index]["csv_data"] = csv_bytes
            else: 
                st.session_state.messages[message_to_update_index].pop("csv_data", None) 
        else: 
            st.session_state.messages[message_to_update_index].pop("dataframe", None)
            st.session_state.messages[message_to_update_index].pop("csv_data", None)

        if agent_steps_for_display:
            st.session_state.messages[message_to_update_index]["agent_steps"] = agent_steps_for_display
        else: 
            st.session_state.messages[message_to_update_index].pop("agent_steps", None)
        
        if final_df is not None and not final_df.empty:
            st.session_state.last_message_id_for_ai_viz = asst_msg_id_to_update

        st.rerun()
