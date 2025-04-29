from langchain_community.utilities import SQLDatabase
from config import DATABASE_URI
import logging

logger = logging.getLogger(__name__)

db = SQLDatabase.from_uri(
    DATABASE_URI,
    include_tables=[
        'customers', 'geolocation', 'order_items',
        'order_payments', 'order_reviews', 'orders',
        'product_category_name_translation', 'products', 'sellers'
    ]
)
logger.info('Database koblet til: %s', DATABASE_URI)