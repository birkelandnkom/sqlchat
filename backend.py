# backend.py

import os
from dotenv import load_dotenv
import openai
from langchain_community.chat_models import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain.agents import AgentExecutor
from langchain.agents.agent_types import AgentType

load_dotenv(".env", override=False)

openai.api_key = os.getenv("OPENROUTER_API_KEY")
openai.api_base = "https://openrouter.ai/api/v1"

llm = ChatOpenAI(
    model="openai/gpt-3.5-turbo",
    temperature=0.2,
    max_tokens=2048,
    openai_api_base=openai.api_base,
    openai_api_key=openai.api_key,
)

db = SQLDatabase.from_uri(
    "sqlite:///test_chatbot.db",
    include_tables=[
        "customers", "geolocation", "order_items", 
        "order_payments", "order_reviews", "orders", 
        "product_category_name_translation", "products", "sellers"
    ]
)

def build_agent():
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
    )
    return agent_executor

__all__ = ["build_agent", "db"]
