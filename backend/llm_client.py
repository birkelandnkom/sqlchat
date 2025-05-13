from langchain_openai import AzureChatOpenAI
from backend.config import AZURE_OPENAI_ENDPOINT
import logging

logger = logging.getLogger(__name__)


llm = AzureChatOpenAI(
    model='o3-mini',
    api_version="2025-01-01-preview",
    timeout=None,
)

logger.info('LLM client initialisert using base: %s', AZURE_OPENAI_ENDPOINT)