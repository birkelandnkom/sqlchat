from langchain_openai import AzureChatOpenAI
from backend.config import AZURE_OPENAI_ENDPOINT
import logging

logger = logging.getLogger(__name__)


llm = AzureChatOpenAI(
    model='gpt-4.1',
    api_version="2024-12-01-preview",
    timeout=60,
    stream_usage=True,
)

logger.info('LLM client initialisert using base: %s', AZURE_OPENAI_ENDPOINT)