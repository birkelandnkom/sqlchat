import openai
from langchain_community.chat_models import ChatOpenAI
from config import OPENAI_API_KEY, OPENAI_API_BASE
import logging

logger = logging.getLogger(__name__)

openai.api_key = OPENAI_API_KEY
openai.api_base = OPENAI_API_BASE

llm = ChatOpenAI(
    model='openai/gpt-3.5-turbo',
    temperature=0.2,
    max_tokens=2048,
    openai_api_base=OPENAI_API_BASE,
    openai_api_key=OPENAI_API_KEY,
)
logger.info('LLM client initialisert')