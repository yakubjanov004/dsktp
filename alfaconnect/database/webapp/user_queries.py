"""
WebApp uchun user queries
"""
from typing import Optional, Dict, Any, List
from database.basic.user import (
    get_user_by_telegram_id as _get_user_by_telegram_id,
    get_user_by_id as _get_user_by_id,
    ensure_user as _ensure_user,
    get_users_by_role
)
import asyncpg
from config import settings


async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Telegram ID orqali user ma'lumotlarini olish"""
    return await _get_user_by_telegram_id(telegram_id)


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """User ID orqali user ma'lumotlarini olish"""
    return await _get_user_by_id(user_id)


async def create_or_get_user(telegram_id: int, first_name: Optional[str] = None, 
                             last_name: Optional[str] = None, username: Optional[str] = None) -> Dict[str, Any]:
    """User yaratish yoki olish"""
    full_name = None
    if first_name or last_name:
        full_name = f"{first_name or ''} {last_name or ''}".strip()
    
    return await _ensure_user(telegram_id, full_name or "User", username or "", role='client')


async def get_client_info(user_id: int) -> Optional[Dict[str, Any]]:
    """Client ma'lumotlarini olish (chat stats bilan)"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT 
                u.id,
                u.telegram_id,
                u.full_name,
                u.username,
                u.phone,
                u.role,
                u.language,
                u.region,
                u.address,
                u.abonent_id,
                u.is_online,
                u.last_seen_at,
                u.created_at,
                u.updated_at,
                COUNT(DISTINCT c.id) as total_chats,
                COUNT(DISTINCT CASE WHEN c.status = 'active' THEN c.id END) as active_chats
            FROM users u
            LEFT JOIN chats c ON c.client_id = u.id
            WHERE u.id = $1
            GROUP BY u.id
            """,
            user_id
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_available_clients(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Mavjud clientlarni olish"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                u.id,
                u.telegram_id,
                u.full_name,
                u.username,
                u.phone,
                u.role,
                u.language,
                u.region,
                u.address,
                u.abonent_id,
                u.is_online,
                u.last_seen_at,
                u.created_at,
                u.updated_at,
                COUNT(DISTINCT c.id) as total_chats,
                COUNT(DISTINCT CASE WHEN c.status = 'active' THEN c.id END) as active_chats
            FROM users u
            LEFT JOIN chats c ON c.client_id = u.id
            WHERE u.role = 'client'
            GROUP BY u.id
            ORDER BY u.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def search_clients(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Clientlarni qidirish"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        search_term = f"%{query}%"
        rows = await conn.fetch(
            """
            SELECT 
                u.id,
                u.telegram_id,
                u.full_name,
                u.username,
                u.phone,
                u.role,
                u.language,
                u.region,
                u.address,
                u.abonent_id,
                u.is_online,
                u.last_seen_at,
                u.created_at,
                u.updated_at,
                COUNT(DISTINCT c.id) as total_chats,
                COUNT(DISTINCT CASE WHEN c.status = 'active' THEN c.id END) as active_chats
            FROM users u
            LEFT JOIN chats c ON c.client_id = u.id
            WHERE u.role = 'client'
              AND (
                u.full_name ILIKE $1
                OR u.username ILIKE $1
                OR u.phone ILIKE $1
                OR CAST(u.telegram_id AS TEXT) ILIKE $1
              )
            GROUP BY u.id
            ORDER BY u.full_name
            LIMIT $2
            """,
            search_term, limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_operators(limit: int = 100) -> List[Dict[str, Any]]:
    """Operatorlarni olish"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT id, full_name, username, phone, telegram_id, role, is_online, last_seen_at
              FROM users
             WHERE role IN ('callcenter_operator', 'callcenter_supervisor')
               AND COALESCE(is_blocked, FALSE) = FALSE
             ORDER BY full_name NULLS LAST, id
             LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

