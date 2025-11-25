"""
Chat queries for WebApp
"""
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime
from config import settings


async def create_chat(client_id: int, operator_id: Optional[int] = None) -> Dict[str, Any]:
    """Create a new chat or reactivate inactive chat"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Check for existing inactive chat
        existing = await conn.fetchrow(
            """
            SELECT id, status FROM chats 
            WHERE client_id = $1 AND status = 'inactive'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            client_id
        )
        
        if existing:
            # Reactivate inactive chat
            row = await conn.fetchrow(
                """
                UPDATE chats
                SET status = 'active',
                    operator_id = $2,
                    last_activity_at = now(),
                    updated_at = now()
                WHERE id = $3
                RETURNING *
                """,
                operator_id, existing['id']
            )
        else:
            # Create new chat
            row = await conn.fetchrow(
                """
                INSERT INTO chats (client_id, operator_id, status, last_activity_at)
                VALUES ($1, $2, 'active', now())
                RETURNING *
                """,
                client_id, operator_id
            )
        
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_chat_by_id(chat_id: int) -> Optional[Dict[str, Any]]:
    """Get chat by ID with user names"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT 
                c.*,
                client.full_name as client_name,
                client.telegram_id as client_telegram_id,
                operator.full_name as operator_name
            FROM chats c
            LEFT JOIN users client ON c.client_id = client.id
            LEFT JOIN users operator ON c.operator_id = operator.id
            WHERE c.id = $1
            """,
            chat_id
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_user_chats(user_id: int, role: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get chats for user based on role"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if role == 'client':
            # Client sees their own chats
            query = """
                SELECT 
                    c.*,
                    client.full_name as client_name,
                    client.telegram_id as client_telegram_id,
                    operator.full_name as operator_name
                FROM chats c
                LEFT JOIN users client ON c.client_id = client.id
                LEFT JOIN users operator ON c.operator_id = operator.id
                WHERE c.client_id = $1
            """
            params = [user_id]
            if status:
                query += " AND c.status = $2"
                params.append(status)
            query += " ORDER BY c.last_activity_at DESC"
        elif role == 'callcenter_supervisor':
            # Supervisors see all chats
            query = """
                SELECT 
                    c.*,
                    client.full_name as client_name,
                    client.telegram_id as client_telegram_id,
                    operator.full_name as operator_name
                FROM chats c
                LEFT JOIN users client ON c.client_id = client.id
                LEFT JOIN users operator ON c.operator_id = operator.id
            """
            params = []
            if status:
                query += " WHERE c.status = $1"
                params.append(status)
            query += " ORDER BY c.last_activity_at DESC"
        else:
            # Operators see assigned chats
            query = """
                SELECT 
                    c.*,
                    client.full_name as client_name,
                    client.telegram_id as client_telegram_id,
                    operator.full_name as operator_name
                FROM chats c
                LEFT JOIN users client ON c.client_id = client.id
                LEFT JOIN users operator ON c.operator_id = operator.id
                WHERE c.operator_id = $1
            """
            params = [user_id]
            if status:
                query += " AND c.status = $2"
                params.append(status)
            query += " ORDER BY c.last_activity_at DESC"
        
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def assign_chat_to_operator(chat_id: int, operator_id: int) -> bool:
    """Assign chat to operator (race-safe)"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            """
            UPDATE chats
            SET operator_id = $1,
                updated_at = now()
            WHERE id = $2
              AND operator_id IS NULL
              AND status = 'active'
            """,
            operator_id, chat_id
        )
        return result == "UPDATE 1"
    finally:
        await conn.close()


async def close_chat(chat_id: int) -> bool:
    """Close chat (mark as inactive)"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            """
            UPDATE chats
            SET status = 'inactive',
                operator_id = NULL,
                updated_at = now()
            WHERE id = $1
            """,
            chat_id
        )
        return result == "UPDATE 1"
    finally:
        await conn.close()


async def update_chat_activity(chat_id: int) -> None:
    """Update chat last_activity_at"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        await conn.execute(
            """
            UPDATE chats
            SET last_activity_at = now(),
                updated_at = now()
            WHERE id = $1
            """,
            chat_id
        )
    finally:
        await conn.close()


async def mark_inactive_chats() -> int:
    """Mark inactive chats (1 hour threshold)"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            """
            UPDATE chats
            SET status = 'inactive',
                operator_id = NULL,
                updated_at = now()
            WHERE status = 'active'
              AND last_activity_at < now() - interval '1 hour'
            """
        )
        # Extract count from result string like "UPDATE 5"
        count = int(result.split()[-1]) if result.startswith("UPDATE") else 0
        return count
    finally:
        await conn.close()


async def get_supervisor_inbox(limit: int = 20, cursor_ts: Optional[datetime] = None, cursor_id: Optional[int] = None) -> Dict[str, Any]:
    """Get supervisor inbox (unassigned active chats)"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if cursor_ts is not None and cursor_id is not None:
            rows = await conn.fetch(
                """
                SELECT 
                    c.*,
                    client.full_name as client_name,
                    client.telegram_id as client_telegram_id
                FROM chats c
                LEFT JOIN users client ON c.client_id = client.id
                WHERE c.status = 'active'
                  AND c.operator_id IS NULL
                  AND (c.last_activity_at, c.id) < ($1::timestamp, $2)
                ORDER BY c.last_activity_at DESC, c.id DESC
                LIMIT $3
                """,
                cursor_ts, cursor_id, limit
            )
        else:
            rows = await conn.fetch(
                """
                SELECT 
                    c.*,
                    client.full_name as client_name,
                    client.telegram_id as client_telegram_id
                FROM chats c
                LEFT JOIN users client ON c.client_id = client.id
                WHERE c.status = 'active'
                  AND c.operator_id IS NULL
                ORDER BY c.last_activity_at DESC, c.id DESC
                LIMIT $1
                """,
                limit
            )
        
        count_row = await conn.fetchrow(
            """
            SELECT COUNT(*) as cnt
            FROM chats
            WHERE status = 'active' AND operator_id IS NULL
            """
        )
        
        return {
            "chats": [dict(r) for r in rows],
            "count": count_row['cnt'] if count_row else 0
        }
    finally:
        await conn.close()


async def get_operator_chats(operator_id: int, limit: int = 20, cursor_ts: Optional[datetime] = None, cursor_id: Optional[int] = None) -> Dict[str, Any]:
    """Get operator's assigned chats"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if cursor_ts is not None and cursor_id is not None:
            rows = await conn.fetch(
                """
                SELECT 
                    c.*,
                    client.full_name as client_name,
                    client.telegram_id as client_telegram_id
                FROM chats c
                LEFT JOIN users client ON c.client_id = client.id
                WHERE c.operator_id = $1
                  AND c.status = 'active'
                  AND (c.last_activity_at, c.id) < ($2::timestamp, $3)
                ORDER BY c.last_activity_at DESC, c.id DESC
                LIMIT $4
                """,
                operator_id, cursor_ts, cursor_id, limit
            )
        else:
            rows = await conn.fetch(
                """
                SELECT 
                    c.*,
                    client.full_name as client_name,
                    client.telegram_id as client_telegram_id
                FROM chats c
                LEFT JOIN users client ON c.client_id = client.id
                WHERE c.operator_id = $1
                  AND c.status = 'active'
                ORDER BY c.last_activity_at DESC, c.id DESC
                LIMIT $2
                """,
                operator_id, limit
            )
        
        count_row = await conn.fetchrow(
            """
            SELECT COUNT(*) as cnt
            FROM chats
            WHERE operator_id = $1 AND status = 'active'
            """,
            operator_id
        )
        
        return {
            "chats": [dict(r) for r in rows],
            "count": count_row['cnt'] if count_row else 0
        }
    finally:
        await conn.close()


async def get_supervisor_active_chats(limit: int = 20, cursor_ts: Optional[datetime] = None, cursor_id: Optional[int] = None) -> Dict[str, Any]:
    """Get supervisor active chats (assigned chats) with cursor-based pagination"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if cursor_ts is not None and cursor_id is not None:
            rows = await conn.fetch(
                """
                SELECT 
                    c.*,
                    client.full_name as client_name,
                    client.telegram_id as client_telegram_id,
                    operator.full_name as operator_name,
                    COALESCE(
                        (SELECT MAX(m.created_at) 
                         FROM messages m 
                         WHERE m.chat_id = c.id 
                           AND m.sender_type = 'client'),
                        c.created_at
                    ) as last_client_activity_at
                FROM chats c
                LEFT JOIN users client ON c.client_id = client.id
                LEFT JOIN users operator ON c.operator_id = operator.id
                WHERE c.status = 'active'
                  AND c.operator_id IS NOT NULL
                  AND (c.last_activity_at, c.id) < ($1::timestamp, $2)
                ORDER BY c.last_activity_at DESC, c.id DESC
                LIMIT $3
                """,
                cursor_ts, cursor_id, limit
            )
        else:
            rows = await conn.fetch(
                """
                SELECT 
                    c.*,
                    client.full_name as client_name,
                    client.telegram_id as client_telegram_id,
                    operator.full_name as operator_name,
                    COALESCE(
                        (SELECT MAX(m.created_at) 
                         FROM messages m 
                         WHERE m.chat_id = c.id 
                           AND m.sender_type = 'client'),
                        c.created_at
                    ) as last_client_activity_at
                FROM chats c
                LEFT JOIN users client ON c.client_id = client.id
                LEFT JOIN users operator ON c.operator_id = operator.id
                WHERE c.status = 'active'
                  AND c.operator_id IS NOT NULL
                ORDER BY c.last_activity_at DESC, c.id DESC
                LIMIT $1
                """,
                limit
            )
        
        count_row = await conn.fetchrow(
            """
            SELECT COUNT(*) as cnt
            FROM chats
            WHERE status = 'active' AND operator_id IS NOT NULL
            """
        )
        
        chats = [dict(r) for r in rows]
        
        # Convert last_client_activity_at to datetime if it's not already
        for chat in chats:
            if chat.get('last_client_activity_at') and isinstance(chat['last_client_activity_at'], datetime):
                # Already a datetime, keep it
                pass
            elif chat.get('last_client_activity_at'):
                # Convert if needed
                pass
        
        return {
            "chats": chats,
            "count": count_row['cnt'] if count_row else 0
        }
    finally:
        await conn.close()


async def get_active_chats_count() -> int:
    """Get count of active chats"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            "SELECT COUNT(*) as cnt FROM chats WHERE status = 'active'"
        )
        return row['cnt'] if row else 0
    finally:
        await conn.close()


async def get_active_chat_counts() -> Dict[str, Any]:
    """Get active chat statistics"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        inbox_count = await conn.fetchrow(
            "SELECT COUNT(*) as cnt FROM chats WHERE status = 'active' AND operator_id IS NULL"
        )
        
        operator_counts = await conn.fetch(
            """
            SELECT operator_id, COUNT(*) as cnt
            FROM chats
            WHERE status = 'active' AND operator_id IS NOT NULL
            GROUP BY operator_id
            """
        )
        
        return {
            "inbox_count": inbox_count['cnt'] if inbox_count else 0,
            "operator_counts": [{"operator_id": r['operator_id'], "cnt": r['cnt']} for r in operator_counts]
        }
    finally:
        await conn.close()

