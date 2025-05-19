from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from backend.config import DATABASE_URI
from backend.llm_client import llm

import logging

logger = logging.getLogger(__name__)

TABLES = [
    'employees', 'customers', 'invoices', 'invoice_items',
    'artists', 'albums', 'media_types', 'genres',
    'tracks', 'playlists', 'playlist_track'
]

try:
    db = SQLDatabase.from_uri(
    DATABASE_URI,
    include_tables=TABLES
    )
    logger.info('Database koblet til: %s', DATABASE_URI)

    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    logger.info("Toolkit bygget")
except Exception as e:
    logger.exception("Database tilkobling feilet: %s", e)
    raise e 


if 'db' not in locals():
     logger.critical("Database object 'db' kunne ikke starte. Applikasjonen avsluttes.")
     import sys
     sys.exit(1)
