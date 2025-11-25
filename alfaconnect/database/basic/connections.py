# database/basic/connections.py

import asyncpg
from typing import Optional, Dict, Any
from config import settings

async def get_connection(connection_id: int) -> Optional[Dict[str, Any]]:
    """Connection ma'lumotlarini olish"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT 
                id,
                sender_id,
                recipient_id,
                application_number,
                sender_status,
                recipient_status,
                created_at,
                updated_at
            FROM connections
            WHERE id = $1
            """,
            connection_id
        )
        return dict(row) if row else None
    finally:
        await conn.close()
