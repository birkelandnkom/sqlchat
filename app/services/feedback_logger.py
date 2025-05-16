import streamlit as st
import json
import os
import logging
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FEEDBACK_LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
FEEDBACK_LOG_FILE = os.path.join(FEEDBACK_LOG_DIR, "feedback_log.jsonl")

logger = logging.getLogger(__name__)

def log_feedback_to_file(feedback_data: dict):
    """
    Writes a given feedback entry to the JSONL log file.

    Args:
        feedback_data (dict): The dictionary containing feedback information.
    """
    try:
        if not os.path.exists(FEEDBACK_LOG_DIR):
            os.makedirs(FEEDBACK_LOG_DIR)
            logger.info(f"Created feedback log directory: {FEEDBACK_LOG_DIR}")

        with open(FEEDBACK_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_data, ensure_ascii=False) + "\n")
        logger.info(f"Feedback logged for message_id: {feedback_data.get('message_id')}")
    except Exception as e:
        st.error(f"Kunne ikke skrive tilbakemeldingslogg: {e}")
        logger.error(f"Klarte ikke skrive tilbakemelding til {FEEDBACK_LOG_FILE}: {e}", exc_info=True)

def process_all_feedback():
    """
    Processes all feedback submitted in the current session.
    Logs both positive (thumbs up) and negative (thumbs down) feedback.
    """
    if "messages" not in st.session_state or not st.session_state.messages:
        return

    if "processed_feedback_ids" not in st.session_state:
        st.session_state.processed_feedback_ids = set()

    messages_snapshot = list(st.session_state.messages)

    for i, message in enumerate(messages_snapshot):
        if message["role"] == "assistant":
            message_id = message.get("id")
            if not message_id:
                logger.warning("Assistant message found without an ID. Skipping feedback processing for this message.")
                continue

            feedback_key = f"feedback_{message_id}"
            feedback_score = st.session_state.get(feedback_key) # 0 for thumbs down, 1 for thumbs up

            if feedback_score is not None and message_id not in st.session_state.processed_feedback_ids:
                user_query = "N/A"
                preceding_user_message_id = "N/A"
                
                if i > 0:
                    for j in range(i - 1, -1, -1):
                        prev_message = messages_snapshot[j]
                        if prev_message["role"] == "user":
                            user_query = prev_message["content"]
                            preceding_user_message_id = prev_message.get("id", "N/A")
                            break
                
                log_entry_base = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "user_query": user_query,
                    "assistant_response": message.get("content", ""),
                    "feedback_score_value": feedback_score,
                    "message_id": message_id,
                    "preceding_user_message_id": preceding_user_message_id,
                    "agent_steps": message.get("agent_steps", [])
                }

                if feedback_score == 0:
                    log_entry = {**log_entry_base, "feedback_type": "thumbs_down"}
                    log_feedback_to_file(log_entry)
                    st.toast("Takk for din tilbakemelding. Dette hjelper oss å forbedre tjenesten.", icon="📝")
                
                elif feedback_score == 1:
                    log_entry = {**log_entry_base, "feedback_type": "thumbs_up"}
                    log_feedback_to_file(log_entry)
                    st.toast("Takk for din tilbakemelding!", icon="😊")

                st.session_state.processed_feedback_ids.add(message_id)
