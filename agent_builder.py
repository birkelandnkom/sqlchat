from langchain_community.agent_toolkits import create_sql_agent
from langchain.agents import AgentExecutor
from langchain.agents.agent_types import AgentType
from llm_client import llm
from db_client import db
import logging

logger = logging.getLogger(__name__)


def build_agent() -> AgentExecutor:
    """Bygger og returnerer en LangChain-agent for SQL-spørringer."""
    logger.info('Bygger agent...')
    raw_agent = create_sql_agent(
        llm=llm,
        db=db,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
        top_k=20,
    )
    agent_executor = AgentExecutor.from_agent_and_tools(
        agent=raw_agent.agent,
        tools=raw_agent.tools,
        verbose=False,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
    )
    logger.info('Agent klar')
    return agent_executor