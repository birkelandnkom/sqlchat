import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=False)

OPENAI_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENAI_API_BASE = 'https://openrouter.ai/api/v1'

DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///test_chatbot.db')