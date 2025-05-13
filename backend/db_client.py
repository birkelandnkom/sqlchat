from langchain_community.utilities import SQLDatabase
from backend.config import DATABASE_URI
import logging

logger = logging.getLogger(__name__)

try:
    db = SQLDatabase.from_uri(
    DATABASE_URI,
    include_tables=[
        'employees',
        'customers',
        'invoices',
        'invoice_items',
        'artists',
        'albums',
        'media_types',
        'genres',
        'tracks',
        'playlists',
        'playlist_track'
        ]
    )
    logger.info('Database koblet til: %s', DATABASE_URI)
except Exception as e:
    logger.exception("Database tilkobling feilet: %s", e)
    raise e 


if 'db' not in locals():
     logger.critical("Database object 'db' kunne ikke starte. Applikasjonen avsluttes.")
     import sys
     sys.exit(1)
