# database/call_center/inbox.py
import asyncpg
from typing import List, Dict, Any, Optional
from config import settings

# === Ulash funksiyasi ===
async def get_connection():
    return await asyncpg.connect(settings.DB_URL)

# =========================================================
# USER HELPER FUNCTIONS
# =========================================================

async def get_user_id_by_telegram_id(telegram_id: int) -> Optional[int]:
    """Telegram ID orqali user ID ni olish"""
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT id
            FROM users
            WHERE telegram_id = $1
            LIMIT 1
            """,
            telegram_id,
        )
        return row["id"] if row else None
    finally:
        await conn.close()

async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Telegram ID orqali to'liq user ma'lumotlarini olish"""
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT 
                id, telegram_id, full_name, username, phone, role,
                language, region, address, is_blocked, created_at, updated_at
            FROM users
            WHERE telegram_id = $1
            """,
            telegram_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()

async def get_any_controller_id() -> Optional[int]:
    """Har qanday controller ID ni olish"""
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT id
            FROM users
            WHERE role = 'controller'
            ORDER BY id ASC
            LIMIT 1
            """
        )
        return row["id"] if row else None
    finally:
        await conn.close()

# =========================================================
# OPERATOR ORDERS FUNCTIONS
# =========================================================

async def get_operator_orders(operator_id: int) -> List[Dict[str, Any]]:
    """Operator uchun texnik arizalarni olish"""
    conn = await get_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT
                t.id,
                t.application_number,
                t.user_id,
                t.region,
                t.address,
                t.abonent_id,
                t.description,
                t.description_operator AS comments,
                t.media,
                t.status,
                t.created_at,
                t.updated_at,
                
                -- Client ma'lumotlari
                u.full_name AS client_name,
                u.phone AS client_phone,
                u.telegram_id AS client_telegram_id,
                
                -- Media type
                CASE 
                    WHEN t.media IS NOT NULL THEN 'photo'
                    ELSE NULL
                END as media_type
                
            FROM technician_orders t
            JOIN users u ON u.id = t.user_id
            WHERE t.is_active = TRUE
              AND t.status = 'in_call_center_operator'
            ORDER BY t.created_at ASC
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def get_operator_orders_count(operator_id: int) -> int:
    """Operator uchun arizalar soni"""
    conn = await get_connection()
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM technician_orders
            WHERE is_active = TRUE
              AND status = 'in_call_center_operator'
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def get_order_by_id(order_id: int) -> Optional[Dict[str, Any]]:
    """ID bo'yicha arizani olish"""
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT
                t.id,
                t.application_number,
                t.user_id,
                t.region,
                t.address,
                t.abonent_id,
                t.description,
                t.description_operator AS comments,
                t.media,
                t.status,
                t.created_at,
                t.updated_at,
                
                -- Client ma'lumotlari
                u.full_name AS client_name,
                u.phone AS client_phone,
                u.telegram_id AS client_telegram_id,
                
                -- Media type
                CASE 
                    WHEN t.media IS NOT NULL THEN 'photo'
                    ELSE NULL
                END as media_type
                
            FROM technician_orders t
            JOIN users u ON u.id = t.user_id
            WHERE t.id = $1
            """,
            order_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()

# =========================================================
# ORDER STATUS FUNCTIONS
# =========================================================

async def update_order_status(order_id: int, status: str, is_active: bool = True) -> bool:
    """Ariza statusini yangilash"""
    conn = await get_connection()
    try:
        result = await conn.execute(
            """
            UPDATE technician_orders
            SET status = $1, is_active = $2, updated_at = NOW()
            WHERE id = $3
            """,
            status, is_active, order_id,
        )
        return result == "UPDATE 1"
    finally:
        await conn.close()

async def add_operator_comment(order_id: int, comment: str) -> bool:
    """Operator izoh qo'shish"""
    conn = await get_connection()
    try:
        result = await conn.execute(
            """
            UPDATE technician_orders
            SET description_operator = $1, updated_at = NOW()
            WHERE id = $2
            """,
            comment, order_id,
        )
        return result == "UPDATE 1"
    finally:
        await conn.close()

# =========================================================
# CONNECTIONS LOGGING FUNCTIONS
# =========================================================

async def log_connection_from_operator(
    sender_id: int,
    recipient_id: int,
    technician_order_id: int,
) -> Optional[int]:
    """Operator tomonidan controllerga yuborilgan ariza uchun connection yaratish"""
    conn = await get_connection()
    try:
        # Get application_number
        app_info = await conn.fetchrow("SELECT application_number FROM technician_orders WHERE id = $1", technician_order_id)
        
        row = await conn.fetchrow(
            """
            INSERT INTO connections(
                application_number,
                sender_id, recipient_id,
                sender_status, recipient_status,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, 'in_call_center_operator', 'in_controller', NOW(), NOW())
            RETURNING id
            """,
            app_info['application_number'] if app_info else None, sender_id, recipient_id,
        )
        return row["id"] if row else None
    finally:
        await conn.close()

async def log_connection_completed_from_operator(
    sender_id: int,
    recipient_id: int,
    technician_order_id: int,
) -> Optional[int]:
    """Operator tomonidan yopilgan ariza uchun connection yaratish"""
    conn = await get_connection()
    try:
        # Get application_number
        app_info = await conn.fetchrow("SELECT application_number FROM technician_orders WHERE id = $1", technician_order_id)
        
        row = await conn.fetchrow(
            """
            INSERT INTO connections(
                application_number,
                sender_id, recipient_id,
                sender_status, recipient_status,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, 'in_call_center_operator', 'completed', NOW(), NOW())
            RETURNING id
            """,
            app_info['application_number'] if app_info else None, sender_id, recipient_id,
        )
        return row["id"] if row else None
    finally:
        await conn.close()

# =========================================================
# LEGACY FUNCTIONS (compatibility)
# =========================================================

async def send_to_supervisor(order_id: int) -> bool:
    """Arizani supervisor ga yuborish (legacy)"""
    return await update_order_status(order_id, 'in_call_center_supervisor')

async def cancel_order(order_id: int) -> bool:
    """Arizani bekor qilish (legacy)"""
    return await update_order_status(order_id, 'cancelled', False)

async def count_operator_orders(operator_id: int, status: str = 'in_call_center_operator') -> int:
    """Operator arizalari soni (legacy)"""
    return await get_operator_orders_count(operator_id)

async def get_all_active_orders() -> List[Dict[str, Any]]:
    """Barcha aktiv arizalar (legacy)"""
    return await get_operator_orders(0)  # operator_id ignored in new implementation
