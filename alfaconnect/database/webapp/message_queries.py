"""
Message queries for WebApp
"""
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime
from config import settings


async def create_message(
    chat_id: int,
    sender_id: Optional[int],
    sender_type: str,
    message_text: str,
    operator_id: Optional[int] = None,
    attachments: Optional[Dict[str, Any]] = None
) -> int:
    """
    Create a new message and update chat's last_activity_at.
    
    This is an atomic operation - both message creation and activity update
    happen in the same transaction.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Transaction ichida xabar yaratish va chat activity yangilash
        async with conn.transaction():
            # 1. Xabar yaratish
            row = await conn.fetchrow(
                """
                INSERT INTO messages (
                    chat_id, sender_id, sender_type, operator_id, message_text, attachments
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                chat_id, sender_id, sender_type, operator_id, message_text,
                asyncpg.types.pgjsonb.encode(attachments) if attachments else None
            )
            
            message_id = row['id'] if row else None
            
            if message_id:
                # 2. Chat last_activity_at ni yangilash (har bir xabar yuborilganda!)
                await conn.execute(
                    """
                    UPDATE chats
                    SET last_activity_at = now(),
                        updated_at = now()
                    WHERE id = $1
                    """,
                    chat_id
                )
            
            return message_id
    finally:
        await conn.close()


async def get_chat_messages(
    chat_id: int,
    limit: int = 100,
    offset: int = 0,
    cursor_ts: Optional[datetime] = None,
    cursor_id: Optional[int] = None,
    since_ts: Optional[datetime] = None,
    since_id: Optional[int] = None,
    all_messages: bool = False
) -> List[Dict[str, Any]]:
    """Get messages for a chat"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if all_messages:
            # Load ALL messages in chronological order (oldest first) - for supervisors viewing full chat history
            rows = await conn.fetch(
                """
                SELECT 
                    m.*,
                    u.full_name as sender_name,
                    u.telegram_id as sender_telegram_id,
                    u.role as sender_role
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                WHERE m.chat_id = $1
                ORDER BY m.created_at ASC, m.id ASC
                """,
                chat_id
            )
            return [dict(r) for r in rows]
        elif since_ts or since_id:
            # Sync mode: get messages after timestamp/id
            query = """
                SELECT 
                    m.*,
                    u.full_name as sender_name,
                    u.telegram_id as sender_telegram_id,
                    u.role as sender_role
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                WHERE m.chat_id = $1
            """
            params = [chat_id]
            param_index = 2
            if since_ts:
                query += f" AND m.created_at > ${param_index}"
                params.append(since_ts)
                param_index += 1
            if since_id:
                query += f" AND m.id > ${param_index}"
                params.append(since_id)
                param_index += 1
            query += f" ORDER BY m.created_at ASC, m.id ASC LIMIT ${param_index}"
            params.append(limit)
            # Execute the query and return results
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]
        elif cursor_ts and cursor_id:
            # Cursor pagination
            rows = await conn.fetch(
                """
                SELECT 
                    m.*,
                    u.full_name as sender_name,
                    u.telegram_id as sender_telegram_id,
                    u.role as sender_role
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                WHERE m.chat_id = $1
                  AND (m.created_at, m.id) < ($2::timestamp, $3)
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT $4
                """,
                chat_id, cursor_ts, cursor_id, limit
            )
            return [dict(r) for r in reversed(rows)]  # Reverse to get chronological order
        else:
            # Offset pagination
            rows = await conn.fetch(
                """
                SELECT 
                    m.*,
                    u.full_name as sender_name,
                    u.telegram_id as sender_telegram_id,
                    u.role as sender_role
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                WHERE m.chat_id = $1
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT $2 OFFSET $3
                """,
                chat_id, limit, offset
            )
            return [dict(r) for r in reversed(rows)]  # Reverse to get chronological order
    finally:
        await conn.close()


async def get_message_by_id(message_id: int) -> Optional[Dict[str, Any]]:
    """Get message by ID"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT 
                m.*,
                u.full_name as sender_name,
                u.telegram_id as sender_telegram_id,
                u.role as sender_role
            FROM messages m
            LEFT JOIN users u ON m.sender_id = u.id
            WHERE m.id = $1
            """,
            message_id
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_unread_messages_count(chat_id: int, user_id: int) -> int:
    """Get unread messages count (placeholder - implement read tracking if needed)"""
    # For now, return 0 as read tracking is not implemented
    return 0

