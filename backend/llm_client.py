import openai
from langchain_community.chat_models import ChatOpenAI
from backend.config import LLM_API_KEY, LLM_API_BASE
import logging

logger = logging.getLogger(__name__)


llm = ChatOpenAI(
    model='openai/gpt-3.5-turbo',
    temperature=0.2,
    max_tokens=2048,
    openai_api_base=LLM_API_BASE,
    openai_api_key=LLM_API_KEY,
)
logger.info('LLM client initialisert using base: %s', LLM_API_BASE)