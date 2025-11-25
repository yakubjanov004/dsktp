# database/warehouse/users.py
import asyncpg
from typing import List, Dict, Any
from config import settings

# ---------- FOYDALANUVCHILAR ----------
async def get_users_by_role(role: str) -> List[Dict[str, Any]]:
    """Warehouse uchun alohida get_users_by_role funksiyasi"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT id, full_name, username, phone, telegram_id
            FROM users
            WHERE role = $1 AND COALESCE(is_blocked, FALSE) = FALSE
            ORDER BY full_name NULLS LAST, id
            """,
            role,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()
