"""
Staff chat queries for WebApp
"""
import asyncpg
from typing import Optional, List, Dict, Any
from config import settings


async def create_staff_chat(sender_id: int, receiver_id: int) -> Dict[str, Any]:
    """Create a new staff chat or reactivate inactive chat"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Check for existing inactive chat
        existing = await conn.fetchrow(
            """
            SELECT id FROM staff_chats 
            WHERE sender_id = $1 AND receiver_id = $2 AND status = 'inactive'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            sender_id, receiver_id
        )
        
        if existing:
            # Reactivate
            row = await conn.fetchrow(
                """
                UPDATE staff_chats
                SET status = 'active',
                    last_activity_at = now(),
                    updated_at = now()
                WHERE id = $1
                RETURNING *
                """,
                existing['id']
            )
        else:
            # Create new
            row = await conn.fetchrow(
                """
                INSERT INTO staff_chats (sender_id, receiver_id, status, last_activity_at)
                VALUES ($1, $2, 'active', now())
                RETURNING *
                """,
                sender_id, receiver_id
            )
        
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_staff_chat_by_id(chat_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Get staff chat by ID (with optional authorization check)"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if user_id:
            # Check if user is participant (sender or receiver)
            row = await conn.fetchrow(
                """
                SELECT 
                    sc.*,
                    sender.full_name as sender_name,
                    receiver.full_name as receiver_name
                FROM staff_chats sc
                LEFT JOIN users sender ON sc.sender_id = sender.id
                LEFT JOIN users receiver ON sc.receiver_id = receiver.id
                WHERE sc.id = $1 AND (sc.sender_id = $2 OR sc.receiver_id = $2)
                """,
                chat_id, user_id
            )
        else:
            # No authorization check - just get chat
            row = await conn.fetchrow(
                """
                SELECT 
                    sc.*,
                    sender.full_name as sender_name,
                    receiver.full_name as receiver_name
                FROM staff_chats sc
                LEFT JOIN users sender ON sc.sender_id = sender.id
                LEFT JOIN users receiver ON sc.receiver_id = receiver.id
                WHERE sc.id = $1
                """,
                chat_id
            )
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_staff_chats(user_id: int, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """Get staff chats for user"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                sc.*,
                sender.full_name as sender_name,
                receiver.full_name as receiver_name
            FROM staff_chats sc
            LEFT JOIN users sender ON sc.sender_id = sender.id
            LEFT JOIN users receiver ON sc.receiver_id = receiver.id
            WHERE (sc.sender_id = $1 OR sc.receiver_id = $1)
            ORDER BY sc.last_activity_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id, limit, offset
        )
        
        count_row = await conn.fetchrow(
            """
            SELECT COUNT(*) as cnt
            FROM staff_chats
            WHERE sender_id = $1 OR receiver_id = $1
            """,
            user_id
        )
        
        return {
            "chats": [dict(r) for r in rows],
            "count": count_row['cnt'] if count_row else 0
        }
    finally:
        await conn.close()


async def create_staff_message(
    chat_id: int,
    sender_id: int,
    message_text: str,
    attachments: Optional[Dict[str, Any]] = None
) -> int:
    """Create a staff message"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO staff_messages (chat_id, sender_id, message_text, attachments)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            chat_id, sender_id, message_text,
            asyncpg.types.pgjsonb.encode(attachments) if attachments else None
        )
        return row['id'] if row else None
    finally:
        await conn.close()


async def get_staff_messages(
    chat_id: int,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get staff messages"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                sm.*,
                u.full_name as sender_name,
                u.telegram_id as sender_telegram_id,
                u.role as sender_role
            FROM staff_messages sm
            LEFT JOIN users u ON sm.sender_id = u.id
            WHERE sm.chat_id = $1
            ORDER BY sm.created_at DESC, sm.id DESC
            LIMIT $2 OFFSET $3
            """,
            chat_id, limit, offset
        )
        return [dict(r) for r in reversed(rows)]  # Reverse for chronological order
    finally:
        await conn.close()


async def get_staff_message_by_id(message_id: int) -> Optional[Dict[str, Any]]:
    """Get staff message by ID"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT 
                sm.*,
                u.full_name as sender_name,
                u.telegram_id as sender_telegram_id,
                u.role as sender_role
            FROM staff_messages sm
            LEFT JOIN users u ON sm.sender_id = u.id
            WHERE sm.id = $1
            """,
            message_id
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_available_staff(user_id: int) -> List[Dict[str, Any]]:
    """Get available staff members for chat"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                u.id,
                u.telegram_id,
                u.full_name,
                u.username,
                u.role
            FROM users u
            WHERE u.id != $1
              AND u.role IN ('call_center', 'call_center_supervisor', 'manager', 'controller')
              AND COALESCE(u.is_blocked, FALSE) = FALSE
            ORDER BY u.full_name
            """,
            user_id
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def close_staff_chat(chat_id: int) -> bool:
    """Close staff chat"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            """
            UPDATE staff_chats
            SET status = 'inactive',
                updated_at = now()
            WHERE id = $1
            """,
            chat_id
        )
        return result == "UPDATE 1"
    finally:
        await conn.close()

