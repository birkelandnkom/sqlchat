import openai
from langchain_openai import AzureChatOpenAI
# from langchain_google_genai import ChatGoogleGenerativeAI
from backend.config import LLM_API_BASE
import logging

logger = logging.getLogger(__name__)


llm = AzureChatOpenAI(
    model='o3-mini',
    max_completion_tokens=4096,    
    api_version="2025-01-01-preview",
    timeout=None,
)

# llm = ChatGoogleGenerativeAI(
#     model="gemini-2.0-flash",
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2,
# )

logger.info('LLM client initialisert using base: %s', LLM_API_BASE)