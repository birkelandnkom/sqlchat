import chainlit as cl
import pandas as pd
import ast
import logging
from logging import getLogger
from io import BytesIO
import copy 
import uuid 
from backend.agent_builder import build_agent
from backend.token_tracer import TokenUsageCallbackHandler  
from backend.db_client import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logging.getLogger('backend.token_tracer').setLevel(logging.WARNING) 
logger = getLogger(__name__)

TOKEN_COUNTER_ELEMENT_ID = "session_token_counter_id" # Made ID more unique

@cl.password_auth_callback
def auth_callback(username: str, password: str) -> cl.User | None:
    """
    Simple password authentication for Proof of Concept.
    """
    if username == "admin" and password == "admin":
        logger.info(f"User '{username}' logged in.")
        return cl.User(identifier="admin", metadata={"role": "admin", "provider": "credentials"})
    else:
        logger.warning(f"Failed login attempt for user '{username}'.")
        return None

@cl.on_chat_start
async def start_chat():
    """
    Initializes and configures the chatbot agent at the start of a new chat.
    Also initializes and displays the session token counter by including it in the welcome message.
    """
    logger.info("Starting a new chat...")
    user = cl.user_session.get("user")
    
    if user:
        logger.info(f"Chat started by user: {user.identifier}")
    else:
        logger.info("Chat started (no user info found in session - auth disabled?).")

    try:
        agent_executor = build_agent() 
        cl.user_session.set("agent", agent_executor)
        logger.info("Agent built and stored in session.")

        cl.user_session.set("session_total_tokens", 0)
        
        token_counter_element = cl.Text(
            content="Øktens totale tokens: 0", 
            name="session_token_counter_name",
            id=TOKEN_COUNTER_ELEMENT_ID, 
            display="side" 
        )
        cl.user_session.set("token_counter_element_instance", token_counter_element)
        logger.info(f"Session token counter element instance created with ID: {TOKEN_COUNTER_ELEMENT_ID}")

        await cl.Message(
            content="Velkommen! Still meg spørsmål om dataene i databasen.",
            author="chatbot",
            elements=[token_counter_element]
        ).send()
        logger.info("Welcome message with token counter sent.")

    except Exception as e:
        logger.exception("Failed to build agent or initialize token counter at chat start")
        await cl.ErrorMessage(content=f"Could not initialize chatbot: {e}").send()


async def process_sql_to_dataframe(sql_query: str, original_agent_text: str) -> tuple[str, pd.DataFrame | None]:
    """
    Executes a given SQL query against the database and attempts to convert the result to a Pandas DataFrame.
    """
    df = None
    final_output_text = original_agent_text
    try:
        logger.info(f"Executing SQL via db.run: {sql_query}")
        sql_result_structured = await cl.make_async(db.run)(sql_query, fetch="all", include_columns=True)
        logger.info(f"db.run finished, result type: {type(sql_result_structured)}")

        parsed_data_for_df = None

        if isinstance(sql_result_structured, list) and sql_result_structured:
            if all(isinstance(row, dict) for row in sql_result_structured):
                parsed_data_for_df = sql_result_structured
            else: 
                parsed_data_for_df = sql_result_structured 
        elif isinstance(sql_result_structured, str):
            potential_data_str = sql_result_structured.strip()
            if potential_data_str.startswith('[') and potential_data_str.endswith(']'):
                try: 
                    parsed_data_for_df = ast.literal_eval(potential_data_str)
                except Exception as parse_err:
                    logger.warning(f"Could not parse SQL result string as list: {parse_err}. Raw data: {potential_data_str}")
                    final_output_text = f"Query executed, but result format was unexpected (unparseable string): {sql_result_structured}"
            elif potential_data_str: 
                final_output_text = potential_data_str 
            else: 
                final_output_text = "Query executed but returned no results (empty string)."
        elif sql_result_structured is not None: 
            parsed_data_for_df = sql_result_structured


        if parsed_data_for_df is not None:
            try:
                df = pd.DataFrame(parsed_data_for_df) if parsed_data_for_df else pd.DataFrame()
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
                logger.error(f"Could not create DataFrame from results: {df_err}. Raw data: {parsed_data_for_df}", exc_info=True)
                final_output_text = f"Could not create DataFrame from SQL results: {df_err}\nRaw data received: {str(parsed_data_for_df)[:200]}..." 
                df = None
        elif sql_result_structured is None or (isinstance(sql_result_structured, str) and not sql_result_structured.strip()):
             final_output_text = "Spørringen ble utført, men returnerte ingen data."
    except Exception as db_err: 
        logger.error(f"Error during SQL execution or result processing: {db_err}", exc_info=True)
        final_output_text = f"Beklager, en feil oppstod under kjøring av SQL eller behandling av resultat: {db_err}"
        df = None 
    return final_output_text, df


@cl.on_message
async def main(message: cl.Message):
    """
    Processes user messages, invokes the agent with token tracking,
    updates the session token counter by modifying the existing element instance
    and including it in the response message.
    """
    agent = cl.user_session.get("agent")
    if not agent:
        await cl.ErrorMessage(content="Chatbot agent not started. Please try starting a new chat.").send()
        return

    prompt = message.content
    logger.info(f"Processing message: '{prompt}'")

    token_callback = TokenUsageCallbackHandler() 
    final_response_text = "Behandler forespørselen din..."
    final_df = None
    sql_query_found = None
    usage_report_summary_for_user = "" 

    token_counter_element_instance = cl.user_session.get("token_counter_element_instance")

    async with cl.Step(name="Agent Execution", show_input=True, language="text") as agent_step:
        agent_step.input = prompt
        try:
            response = await agent.ainvoke(
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
                    if isinstance(raw_tool_input, dict):
                        tool_input_str = str(raw_tool_input) 
                    elif not isinstance(raw_tool_input, str):
                        tool_input_str = str(raw_tool_input)
                    else:
                        tool_input_str = raw_tool_input

                    step_name = f"Step {idx+1}: {tool_name}"
                    async with cl.Step(name=step_name, parent_id=agent_step.id, type="tool") as tool_step:
                        tool_step.input = tool_input_str
                        tool_step.output = str(observation) 
                        
                        if 'sql' in tool_name.lower() and \
                           ('query' in tool_name.lower() or 'tool' in tool_name.lower() or 'db' in tool_name.lower()):
                            sql_query_found = tool_input_str 
                            logger.info(f"Found SQL query in step {idx+1} (Tool: {tool_name}): {sql_query_found}")
            else:
                logger.info("Agent reported no intermediate steps.")

            if sql_query_found:
                final_response_text, final_df = await process_sql_to_dataframe(sql_query_found, agent_output_text)
                agent_step.output = final_response_text
            else:
                logger.info("No SQL query was executed by the agent, or the SQL tool was not recognized.")
                final_response_text = agent_output_text
                agent_step.output = final_response_text
        
        except Exception as e:
            logger.exception("Error during agent execution or data processing") 
            final_response_text = f"En feil oppstod under behandling av din forespørsel: {type(e).__name__}" 
            agent_step.is_error = True 
            agent_step.output = final_response_text
            final_df = None
        finally:
            usage_report = token_callback.get_report()
            
            report_summary_for_log = copy.deepcopy(usage_report)
            report_summary_for_log.pop('detailed_steps', None) 
            logger.info(f"Token Usage Report Summary for query '{prompt}': {report_summary_for_log}")
            if usage_report.get('detailed_steps') and logging.getLogger('backend.token_tracer').isEnabledFor(logging.DEBUG):
                 logger.debug(f"Full detailed_steps for query '{prompt}': {usage_report['detailed_steps']}")

            current_message_tokens = usage_report.get('total_tokens_used', 0)
            usage_report_summary_for_user = (
                f"\n\n--- Ressursbruk (denne meldingen) ---\n"
                f"Tokens brukt: {current_message_tokens}\n"
                f"(Input: {usage_report['prompt_tokens_used']}, Output: {usage_report['completion_tokens_used']})\n"
                f"Antall LLM-kall: {usage_report['successful_llm_requests']}"
            )
            if usage_report['llm_errors'] > 0:
                 usage_report_summary_for_user += f"\nAntall LLM-feil: {usage_report['llm_errors']}"
            
            if agent_step.output: 
                agent_step.output += usage_report_summary_for_user
            else: 
                final_response_text += usage_report_summary_for_user

            session_total_tokens = cl.user_session.get("session_total_tokens", 0)
            new_session_total_tokens = session_total_tokens + current_message_tokens
            cl.user_session.set("session_total_tokens", new_session_total_tokens)

            if token_counter_element_instance:
                token_counter_element_instance.content = f"Øktens totale tokens: {new_session_total_tokens}"
                logger.info(f"Session token counter element content updated to: {new_session_total_tokens}. It will be re-sent with the main message.")
            else:
                logger.warning("Could not find token_counter_element_instance in session to update.")


    final_elements_for_message = []
    if final_df is not None and not final_df.empty:
        try:
            df_element = cl.Dataframe(data=final_df, name="Resultater", display="inline") 
            final_elements_for_message.append(df_element)
            logger.info("Dataframe element created successfully using cl.Dataframe.")

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
            final_elements_for_message.append(csv_file_element)
            logger.info("CSV file element for download created successfully.")

        except Exception as el_err:
            logger.error(f"Error creating Dataframe element or CSV file: {el_err}", exc_info=True)
            final_response_text += "\n\n*(Beklager, kunne ikke formatere tabellen og/eller nedlastingslink for resultatene.)*"
    
    if token_counter_element_instance:
        if token_counter_element_instance not in final_elements_for_message:
            final_elements_for_message.append(token_counter_element_instance)
    
    if usage_report_summary_for_user and usage_report_summary_for_user not in final_response_text:
         if agent_step.output and usage_report_summary_for_user not in agent_step.output :
            pass 
         else: 
            final_response_text += usage_report_summary_for_user

    await cl.Message(
        content=final_response_text,
        elements=final_elements_for_message, 
        author="chatbot"
    ).send()
