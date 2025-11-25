# database/call_center/statistics.py
import asyncpg
from typing import Dict
from config import settings

async def get_connection():
    return await asyncpg.connect(settings.DB_URL)

async def get_user_id_by_telegram_id(tg_id: int) -> int | None:
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1 LIMIT 1",
            tg_id
        )
        return row["id"] if row else None
    finally:
        await conn.close()

async def get_operator_stats_by_range(operator_id: int, range_key: str) -> Dict[str, int]:
    """
    range_key: 'day' | 'week' | 'month' | 'year'
    """
    interval_map = {
        "day":   "1 day",
        "week":  "7 days",
        "month": "1 month",
        "year":  "1 year",
    }
    interval = interval_map.get(range_key, "1 day")

    # ⚠️ interval parametr bo'lib bormaydi — whitelistdan olinib literal bo'lib qo'yilyapti
    co_sql = f"""
        SELECT COUNT(*)::int
        FROM staff_orders
        WHERE user_id = $1
          AND type_of_zayavka = 'connection'
          AND is_active = TRUE
          AND created_at >= NOW() - INTERVAL '{interval}'
    """
    to_sql = f"""
        SELECT COUNT(*)::int
        FROM staff_orders
        WHERE user_id = $1
          AND type_of_zayavka = 'technician'
          AND created_at >= NOW() - INTERVAL '{interval}'
    """
    sent_sql = f"""
        SELECT COUNT(*)::int
        FROM connections c
        JOIN users u ON u.id = c.recipient_id
        WHERE c.sender_id = $1
          AND u.role = 'controller'
          AND c.created_at >= NOW() - INTERVAL '{interval}'
    """

    conn = await get_connection()
    try:
        connection_orders = await conn.fetchval(co_sql, operator_id)
        technician_orders = await conn.fetchval(to_sql, operator_id)
        sent_orders = await conn.fetchval(sent_sql, operator_id)

        return {
            "connection_orders_total": int(connection_orders or 0),
            "technician_orders_total": int(technician_orders or 0),
            "sent_to_controller_total": int(sent_orders or 0),
            "closed_by_operator_total": 0,  # Hozircha 0 qilib qoldiramiz
        }
    finally:
        await conn.close()

async def get_operator_total_stats(operator_id: int) -> Dict[str, int]:
    """
    Operatorning umumiy statistikasi (barcha vaqt uchun)
    """
    conn = await get_connection()
    try:
        connection_orders = await conn.fetchval(
            """
            SELECT COUNT(*)::int
            FROM staff_orders
            WHERE user_id = $1
              AND type_of_zayavka = 'connection'
              AND is_active = TRUE
            """,
            operator_id
        )
        
        technician_orders = await conn.fetchval(
            """
            SELECT COUNT(*)::int
            FROM staff_orders
            WHERE user_id = $1
              AND type_of_zayavka = 'technician'
            """,
            operator_id
        )
        
        sent_orders = await conn.fetchval(
            """
            SELECT COUNT(*)::int
            FROM connections c
            JOIN users u ON u.id = c.recipient_id
            WHERE c.sender_id = $1
              AND u.role = 'controller'
            """,
            operator_id
        )

        return {
            "connection_orders": int(connection_orders or 0),
            "technician_orders": int(technician_orders or 0),
            "sent_orders": int(sent_orders or 0),
        }
    finally:
        await conn.close()
