import os
from dotenv import load_dotenv
from pathlib import Path
import logging 

logger = logging.getLogger(__name__) 
load_dotenv(override=True)


AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')

if not AZURE_OPENAI_API_KEY:
    logger.critical("Missing required environment variable: AZURE_OPENAI_API_KEY. LLM features will fail.")


DATABASE_URI = os.getenv('DATABASE_URI', r"sqlite:///data-ekom.db").strip()
if DATABASE_URI == 'sqlite:///data-ekom.db':
    logger.warning("Environment variable DATABASE_URI not set. Using default: %s", DATABASE_URI)
elif not DATABASE_URI:
    logger.critical("Missing required environment variable: DATABASE_URI and no default set.")
