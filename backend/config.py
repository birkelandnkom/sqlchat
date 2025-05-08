import os
from dotenv import load_dotenv
from pathlib import Path
import logging 

logger = logging.getLogger(__name__) 
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=False)


LLM_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
LLM_API_BASE = os.getenv('AZURE_OPENAI_API_URI')
# GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')


if not LLM_API_KEY:
    logger.critical("Missing required environment variable: LLM_API_KEY. LLM features will fail.")


DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///test_chatbot.db')
if DATABASE_URI == 'sqlite:///test_chatbot.db':
    logger.warning("Using default SQLite database URI: %s", DATABASE_URI)
elif not DATABASE_URI:
    logger.critical("Missing required environment variable: DATABASE_URI and no default set.")
