# database/connections.py
# Database connection utilities

import asyncpg
from config import settings

def get_connection_url() -> str:
    """
    Get the database connection URL from settings.
    
    Returns:
        str: The database connection URL
    """
    return settings.DB_URL

async def get_asyncpg_connection():
    """
    Get asyncpg connection with SSL disabled for local network connections.
    This helps when pg_hba.conf doesn't allow connections from specific IPs.
    
    Returns:
        asyncpg.Connection: Database connection
    """
    # SSL ni disable qilish - local network uchun
    # Agar kerak bo'lsa, .env da DB_SSL_MODE ni qo'shish mumkin
    ssl_mode = getattr(settings, 'DB_SSL_MODE', None)
    
    if ssl_mode == 'require':
        ssl = 'require'
    elif ssl_mode == 'disable':
        ssl = False
    else:
        # Default: SSL ni disable qilish (local network uchun)
        ssl = False
    
    return await asyncpg.connect(settings.DB_URL, ssl=ssl)
