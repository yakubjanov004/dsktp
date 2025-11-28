"""
Message queries for WebApp
"""
import asyncpg
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from config import settings

logger = logging.getLogger(__name__)


async def create_message(
    chat_id: int,
    sender_id: Optional[int],
    sender_type: str,
    message_text: str,
    operator_id: Optional[int] = None,
    attachments: Optional[Dict[str, Any]] = None,
    reply_to_message_id: Optional[int] = None
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
                    chat_id, sender_id, sender_type, operator_id, message_text, attachments, reply_to_message_id
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                chat_id, sender_id, sender_type, operator_id, message_text,
                asyncpg.types.pgjsonb.encode(attachments) if attachments else None,
                reply_to_message_id
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


async def _get_message_reactions(conn, message_id: int) -> List[Dict[str, Any]]:
    """Helper function to get reactions for a message"""
    reaction_rows = await conn.fetch(
        """
        SELECT 
            emoji,
            COUNT(*) as count,
            array_agg(user_id ORDER BY created_at) as user_ids
        FROM message_reactions
        WHERE message_id = $1
        GROUP BY emoji
        ORDER BY count DESC, emoji
        """,
        message_id
    )
    return [
        {
            "emoji": row["emoji"],
            "count": row["count"],
            "users": row["user_ids"]
        }
        for row in reaction_rows
    ]


async def _get_bulk_reactions(conn, message_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    """Get reactions for multiple messages in one query"""
    if not message_ids:
        return {}
    
    rows = await conn.fetch(
        """
        SELECT 
            message_id,
            emoji,
            COUNT(*) as count,
            array_agg(user_id ORDER BY created_at) as user_ids
        FROM message_reactions
        WHERE message_id = ANY($1::bigint[])
        GROUP BY message_id, emoji
        ORDER BY message_id, count DESC, emoji
        """,
        message_ids
    )
    
    # Group by message_id
    reactions_by_message: Dict[int, List[Dict[str, Any]]] = {}
    for row in rows:
        message_id = row["message_id"]
        if message_id not in reactions_by_message:
            reactions_by_message[message_id] = []
        reactions_by_message[message_id].append({
            "emoji": row["emoji"],
            "count": row["count"],
            "users": row["user_ids"]
        })
    
    # Ensure all message_ids have empty list if no reactions
    for msg_id in message_ids:
        if msg_id not in reactions_by_message:
            reactions_by_message[msg_id] = []
    
    return reactions_by_message


async def _get_bulk_read_counts(conn, message_ids: List[int]) -> Dict[int, int]:
    """Get read counts for multiple messages in one query"""
    if not message_ids:
        return {}
    
    rows = await conn.fetch(
        """
        SELECT 
            message_id,
            COUNT(*) as read_count
        FROM message_reads
        WHERE message_id = ANY($1::bigint[])
        GROUP BY message_id
        """,
        message_ids
    )
    
    # Create dict with all message_ids (default 0)
    read_counts = {msg_id: 0 for msg_id in message_ids}
    for row in rows:
        read_counts[row["message_id"]] = row["read_count"]
    
    return read_counts


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
                    u.role as sender_role,
                    reply_msg.id as reply_to_id,
                    reply_msg.message_text as reply_to_text,
                    reply_msg.sender_id as reply_to_sender_id,
                    reply_msg.sender_type as reply_to_sender_type,
                    reply_user.full_name as reply_to_sender_name
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                LEFT JOIN messages reply_msg ON m.reply_to_message_id = reply_msg.id
                LEFT JOIN users reply_user ON reply_msg.sender_id = reply_user.id
                WHERE m.chat_id = $1
                ORDER BY m.created_at ASC, m.id ASC
                """,
                chat_id
            )
            messages = [dict(r) for r in rows]
            # Bulk load reactions and read counts
            if messages:
                message_ids = [msg["id"] for msg in messages]
                reactions_by_message = await _get_bulk_reactions(conn, message_ids)
                read_counts = await _get_bulk_read_counts(conn, message_ids)
                # Add to each message
                for msg in messages:
                    msg["reactions"] = reactions_by_message.get(msg["id"], [])
                    msg["read_count"] = read_counts.get(msg["id"], 0)
            return messages
        elif since_ts or since_id:
            # Sync mode: get messages after timestamp/id
            query = """
                SELECT 
                    m.*,
                    u.full_name as sender_name,
                    u.telegram_id as sender_telegram_id,
                    u.role as sender_role,
                    reply_msg.id as reply_to_id,
                    reply_msg.message_text as reply_to_text,
                    reply_msg.sender_id as reply_to_sender_id,
                    reply_msg.sender_type as reply_to_sender_type,
                    reply_user.full_name as reply_to_sender_name
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                LEFT JOIN messages reply_msg ON m.reply_to_message_id = reply_msg.id
                LEFT JOIN users reply_user ON reply_msg.sender_id = reply_user.id
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
            messages = [dict(r) for r in rows]
            # Bulk load reactions and read counts
            if messages:
                message_ids = [msg["id"] for msg in messages]
                reactions_by_message = await _get_bulk_reactions(conn, message_ids)
                read_counts = await _get_bulk_read_counts(conn, message_ids)
                # Add to each message
                for msg in messages:
                    msg["reactions"] = reactions_by_message.get(msg["id"], [])
                    msg["read_count"] = read_counts.get(msg["id"], 0)
            return messages
        elif cursor_ts and cursor_id:
            # Cursor pagination
            rows = await conn.fetch(
                """
                SELECT 
                    m.*,
                    u.full_name as sender_name,
                    u.telegram_id as sender_telegram_id,
                    u.role as sender_role,
                    reply_msg.id as reply_to_id,
                    reply_msg.message_text as reply_to_text,
                    reply_msg.sender_id as reply_to_sender_id,
                    reply_msg.sender_type as reply_to_sender_type,
                    reply_user.full_name as reply_to_sender_name
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                LEFT JOIN messages reply_msg ON m.reply_to_message_id = reply_msg.id
                LEFT JOIN users reply_user ON reply_msg.sender_id = reply_user.id
                WHERE m.chat_id = $1
                  AND (m.created_at, m.id) < ($2::timestamp, $3)
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT $4
                """,
                chat_id, cursor_ts, cursor_id, limit
            )
            messages = [dict(r) for r in reversed(rows)]  # Reverse to get chronological order
            # Bulk load reactions and read counts
            if messages:
                message_ids = [msg["id"] for msg in messages]
                reactions_by_message = await _get_bulk_reactions(conn, message_ids)
                read_counts = await _get_bulk_read_counts(conn, message_ids)
                # Add to each message
                for msg in messages:
                    msg["reactions"] = reactions_by_message.get(msg["id"], [])
                    msg["read_count"] = read_counts.get(msg["id"], 0)
            return messages
        else:
            # Offset pagination
            rows = await conn.fetch(
                """
                SELECT 
                    m.*,
                    u.full_name as sender_name,
                    u.telegram_id as sender_telegram_id,
                    u.role as sender_role,
                    reply_msg.id as reply_to_id,
                    reply_msg.message_text as reply_to_text,
                    reply_msg.sender_id as reply_to_sender_id,
                    reply_msg.sender_type as reply_to_sender_type,
                    reply_user.full_name as reply_to_sender_name
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                LEFT JOIN messages reply_msg ON m.reply_to_message_id = reply_msg.id
                LEFT JOIN users reply_user ON reply_msg.sender_id = reply_user.id
                WHERE m.chat_id = $1
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT $2 OFFSET $3
                """,
                chat_id, limit, offset
            )
            messages = [dict(r) for r in reversed(rows)]  # Reverse to get chronological order
            # Bulk load reactions and read counts
            if messages:
                message_ids = [msg["id"] for msg in messages]
                reactions_by_message = await _get_bulk_reactions(conn, message_ids)
                read_counts = await _get_bulk_read_counts(conn, message_ids)
                # Add to each message
                for msg in messages:
                    msg["reactions"] = reactions_by_message.get(msg["id"], [])
                    msg["read_count"] = read_counts.get(msg["id"], 0)
            return messages
    finally:
        await conn.close()


async def get_message_by_id(message_id: int) -> Optional[Dict[str, Any]]:
    """Get message by ID with reactions and reply data"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT 
                m.*,
                u.full_name as sender_name,
                u.telegram_id as sender_telegram_id,
                u.role as sender_role,
                reply_msg.id as reply_to_id,
                reply_msg.message_text as reply_to_text,
                reply_msg.sender_id as reply_to_sender_id,
                reply_msg.sender_type as reply_to_sender_type,
                reply_user.full_name as reply_to_sender_name
            FROM messages m
            LEFT JOIN users u ON m.sender_id = u.id
            LEFT JOIN messages reply_msg ON m.reply_to_message_id = reply_msg.id
            LEFT JOIN users reply_user ON reply_msg.sender_id = reply_user.id
            WHERE m.id = $1
            """,
            message_id
        )
        if not row:
            return None
        
        message = dict(row)
        # Add reactions
        reaction_rows = await conn.fetch(
            """
            SELECT 
                emoji,
                COUNT(*) as count,
                array_agg(user_id ORDER BY created_at) as user_ids
            FROM message_reactions
            WHERE message_id = $1
            GROUP BY emoji
            ORDER BY count DESC, emoji
            """,
            message_id
        )
        message["reactions"] = [
            {
                "emoji": r["emoji"],
                "count": r["count"],
                "users": r["user_ids"]
            }
            for r in reaction_rows
        ]
        # Add read count
        read_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM message_reads WHERE message_id = $1
            """,
            message_id
        )
        message["read_count"] = read_count or 0
        return message
    finally:
        await conn.close()


async def get_message_thread(message_id: int) -> List[Dict[str, Any]]:
    """Get all messages that reply to a specific message (thread)"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Get all messages that reply to this message
        rows = await conn.fetch(
            """
            SELECT 
                m.*,
                u.full_name as sender_name,
                u.telegram_id as sender_telegram_id,
                u.role as sender_role,
                reply_msg.id as reply_to_id,
                reply_msg.message_text as reply_to_text,
                reply_msg.sender_id as reply_to_sender_id,
                reply_msg.sender_type as reply_to_sender_type,
                reply_user.full_name as reply_to_sender_name
            FROM messages m
            LEFT JOIN users u ON m.sender_id = u.id
            LEFT JOIN messages reply_msg ON m.reply_to_message_id = reply_msg.id
            LEFT JOIN users reply_user ON reply_msg.sender_id = reply_user.id
            WHERE m.reply_to_message_id = $1
            ORDER BY m.created_at ASC, m.id ASC
            """,
            message_id
        )
        
        messages = [dict(r) for r in rows]
        
        # Bulk load reactions and read counts
        if messages:
            message_ids = [msg["id"] for msg in messages]
            reactions_by_message = await _get_bulk_reactions(conn, message_ids)
            read_counts = await _get_bulk_read_counts(conn, message_ids)
            
            # Add to each message
            for msg in messages:
                msg["reactions"] = reactions_by_message.get(msg["id"], [])
                msg["read_count"] = read_counts.get(msg["id"], 0)
        
        return messages
    finally:
        await conn.close()


async def get_unread_messages_count(chat_id: int, user_id: int) -> int:
    """
    Get unread messages count for a user in a chat.
    Unread = messages not read by this user (excluding own messages).
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM messages m
            WHERE m.chat_id = $1
              AND m.sender_id != $2
              AND m.sender_type != 'system'
              AND NOT EXISTS (
                  SELECT 1 FROM message_reads mr
                  WHERE mr.message_id = m.id AND mr.user_id = $2
              )
            """,
            chat_id, user_id
        )
        return count or 0
    finally:
        await conn.close()


async def mark_message_read(message_id: int, user_id: int) -> bool:
    """
    Mark a message as read by a user.
    Returns True if successful, False otherwise.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        await conn.execute(
            """
            INSERT INTO message_reads (message_id, user_id, read_at)
            VALUES ($1, $2, now())
            ON CONFLICT (message_id, user_id) 
            DO UPDATE SET read_at = now()
            """,
            message_id, user_id
        )
        return True
    except Exception as e:
        logger.error(f"Error marking message as read: {e}")
        return False
    finally:
        await conn.close()


async def get_message_reads(message_id: int) -> List[Dict[str, Any]]:
    """
    Get list of users who read a message.
    Returns list of user dictionaries with read_at timestamp.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                mr.user_id,
                mr.read_at,
                u.full_name as user_name,
                u.telegram_id as user_telegram_id
            FROM message_reads mr
            INNER JOIN users u ON mr.user_id = u.id
            WHERE mr.message_id = $1
            ORDER BY mr.read_at ASC
            """,
            message_id
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def mark_chat_messages_read(chat_id: int, user_id: int) -> int:
    """
    Mark all unread messages in a chat as read for a user.
    Returns number of messages marked as read.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            """
            INSERT INTO message_reads (message_id, user_id, read_at)
            SELECT m.id, $2, now()
            FROM messages m
            WHERE m.chat_id = $1
              AND m.sender_id != $2
              AND m.sender_type != 'system'
              AND NOT EXISTS (
                  SELECT 1 FROM message_reads mr
                  WHERE mr.message_id = m.id AND mr.user_id = $2
              )
            ON CONFLICT (message_id, user_id) DO NOTHING
            """,
            chat_id, user_id
        )
        # Extract count from result string like "INSERT 0 5"
        if result.startswith("INSERT"):
            parts = result.split()
            if len(parts) >= 3:
                return int(parts[2])
        return 0
    except Exception as e:
        logger.error(f"Error marking chat messages as read: {e}")
        return 0
    finally:
        await conn.close()


async def get_chat_media(
    chat_id: int,
    media_type: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get media files (images/videos) from chat messages.
    
    Args:
        chat_id: Chat ID
        media_type: 'image', 'video', or None for all
        limit: Maximum number of media items to return
    
    Returns:
        List of messages with media attachments
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Build query with parameterized conditions
        if media_type == "image":
            rows = await conn.fetch(
                """
                SELECT 
                    m.id, m.chat_id, m.sender_id, m.sender_type, m.operator_id,
                    m.message_text, m.attachments, m.created_at,
                    u.full_name as sender_name, u.telegram_id as sender_telegram_id, u.role as sender_role
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                WHERE m.chat_id = $1
                  AND m.attachments IS NOT NULL
                  AND attachments->>'type' != 'voice'
                  AND (attachments->>'type' = 'image' OR attachments->>'image' IS NOT NULL)
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT $2
                """,
                chat_id, limit
            )
        elif media_type == "video":
            rows = await conn.fetch(
                """
                SELECT 
                    m.id, m.chat_id, m.sender_id, m.sender_type, m.operator_id,
                    m.message_text, m.attachments, m.created_at,
                    u.full_name as sender_name, u.telegram_id as sender_telegram_id, u.role as sender_role
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                WHERE m.chat_id = $1
                  AND m.attachments IS NOT NULL
                  AND attachments->>'type' != 'voice'
                  AND (attachments->>'type' = 'video' OR attachments->>'video' IS NOT NULL)
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT $2
                """,
                chat_id, limit
            )
        else:
            rows = await conn.fetch(
                """
                SELECT 
                    m.id, m.chat_id, m.sender_id, m.sender_type, m.operator_id,
                    m.message_text, m.attachments, m.created_at,
                    u.full_name as sender_name, u.telegram_id as sender_telegram_id, u.role as sender_role
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                WHERE m.chat_id = $1
                  AND m.attachments IS NOT NULL
                  AND attachments->>'type' != 'voice'
                  AND (attachments->>'type' IN ('image', 'video') OR attachments->>'image' IS NOT NULL OR attachments->>'video' IS NOT NULL)
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT $2
                """,
                chat_id, limit
            )
        
        messages = []
        for row in rows:
            message = dict(row)
            # Attachments already decoded by asyncpg
            messages.append(message)
        
        return messages
    finally:
        await conn.close()


async def get_message_reactions(message_id: int) -> List[Dict[str, Any]]:
    """
    Get all reactions for a message, grouped by emoji with user counts.
    
    Returns:
        List of dicts: [{"emoji": "👍", "count": 3, "users": [user_id1, user_id2, ...]}, ...]
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                emoji,
                COUNT(*) as count,
                array_agg(user_id ORDER BY created_at) as user_ids
            FROM message_reactions
            WHERE message_id = $1
            GROUP BY emoji
            ORDER BY count DESC, emoji
            """,
            message_id
        )
        return [
            {
                "emoji": row["emoji"],
                "count": row["count"],
                "users": row["user_ids"]
            }
            for row in rows
        ]
    finally:
        await conn.close()


async def toggle_message_reaction(message_id: int, user_id: int, emoji: str) -> Dict[str, Any]:
    """
    Toggle a reaction on a message.
    If emoji is empty, remove user's reaction.
    If user already has this emoji reaction, remove it.
    Otherwise, add or update reaction.
    
    Returns:
        Dict with "action" ("added" or "removed") and "reactions" (updated reactions list)
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        async with conn.transaction():
            # If emoji is empty, remove reaction
            if not emoji:
                await conn.execute(
                    """
                    DELETE FROM message_reactions
                    WHERE message_id = $1 AND user_id = $2
                    """,
                    message_id, user_id
                )
                action = "removed"
            else:
                # Check if user already has this emoji reaction
                existing = await conn.fetchrow(
                    """
                    SELECT emoji FROM message_reactions
                    WHERE message_id = $1 AND user_id = $2
                    """,
                    message_id, user_id
                )
                
                if existing and existing["emoji"] == emoji:
                    # Remove reaction (user clicked same emoji)
                    await conn.execute(
                        """
                        DELETE FROM message_reactions
                        WHERE message_id = $1 AND user_id = $2
                        """,
                        message_id, user_id
                    )
                    action = "removed"
                else:
                    # Add or update reaction
                    await conn.execute(
                        """
                        INSERT INTO message_reactions (message_id, user_id, emoji)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (message_id, user_id)
                        DO UPDATE SET emoji = $3, created_at = now()
                        """,
                        message_id, user_id, emoji
                    )
                    action = "added"
            
            # Get updated reactions using helper function
            reactions = await _get_message_reactions(conn, message_id)
            
            return {
                "action": action,
                "reactions": reactions
            }
    finally:
        await conn.close()


async def search_messages(chat_id: int, query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Search messages in a chat using PostgreSQL full-text search.
    
    Args:
        chat_id: Chat ID to search in
        query: Search query string
        limit: Maximum number of results (default: 50)
    
    Returns:
        List of message dicts with sender info, ordered by relevance and created_at
    """
    if not query or not query.strip():
        return []
    
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                m.*,
                u.full_name as sender_name,
                u.telegram_id as sender_telegram_id,
                u.role as sender_role,
                ts_rank(to_tsvector('simple', m.message_text), plainto_tsquery('simple', $2)) as rank
            FROM messages m
            LEFT JOIN users u ON m.sender_id = u.id
            WHERE m.chat_id = $1
              AND to_tsvector('simple', m.message_text) @@ plainto_tsquery('simple', $2)
            ORDER BY rank DESC, m.created_at DESC
            LIMIT $3
            """,
            chat_id, query.strip(), limit
        )
        
        messages = [dict(r) for r in rows]
        # Remove rank from message dict (internal use only)
        for msg in messages:
            msg.pop('rank', None)
        
        # Bulk load reactions and read counts
        if messages:
            message_ids = [msg["id"] for msg in messages]
            reactions_by_message = await _get_bulk_reactions(conn, message_ids)
            read_counts = await _get_bulk_read_counts(conn, message_ids)
            # Add to each message
            for msg in messages:
                msg["reactions"] = reactions_by_message.get(msg["id"], [])
                msg["read_count"] = read_counts.get(msg["id"], 0)
        
        return messages
    finally:
        await conn.close()


async def forward_message(
    message_id: int,
    target_chat_id: int,
    sender_id: int,
    sender_type: str,
    operator_id: Optional[int] = None
) -> Optional[int]:
    """
    Forward a message to another chat.
    
    Args:
        message_id: ID of the message to forward
        target_chat_id: ID of the target chat
        sender_id: ID of the user forwarding the message
        sender_type: Type of sender ('client' or 'operator')
        operator_id: Operator ID if sender_type is 'operator'
    
    Returns:
        ID of the new forwarded message, or None if failed
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        async with conn.transaction():
            # 1. Get original message
            original_message = await conn.fetchrow(
                """
                SELECT 
                    chat_id,
                    sender_id as original_sender_id,
                    message_text,
                    attachments,
                    forwarded_from_message_id,
                    forwarded_from_chat_id,
                    forwarded_from_user_id
                FROM messages
                WHERE id = $1
                """,
                message_id
            )
            
            if not original_message:
                return None
            
            # 2. Determine forwarded_from fields
            # If original message is already forwarded, keep original forward info
            if original_message['forwarded_from_message_id']:
                forwarded_from_message_id = original_message['forwarded_from_message_id']
                forwarded_from_chat_id = original_message['forwarded_from_chat_id']
                forwarded_from_user_id = original_message['forwarded_from_user_id']
            else:
                # Original message - use its info
                forwarded_from_message_id = message_id
                forwarded_from_chat_id = original_message['chat_id']
                forwarded_from_user_id = original_message['original_sender_id']
            
            # 3. Create forwarded message
            row = await conn.fetchrow(
                """
                INSERT INTO messages (
                    chat_id, sender_id, sender_type, operator_id, 
                    message_text, attachments,
                    forwarded_from_message_id, forwarded_from_chat_id, forwarded_from_user_id
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                target_chat_id,
                sender_id,
                sender_type,
                operator_id,
                original_message['message_text'],
                original_message['attachments'],
                forwarded_from_message_id,
                forwarded_from_chat_id,
                forwarded_from_user_id
            )
            
            new_message_id = row['id'] if row else None
            
            if new_message_id:
                # 4. Update target chat's last_activity_at
                await conn.execute(
                    """
                    UPDATE chats
                    SET last_activity_at = now(),
                        updated_at = now()
                    WHERE id = $1
                    """,
                    target_chat_id
                )
            
            return new_message_id
    finally:
        await conn.close()


async def edit_message(
    message_id: int,
    new_text: str,
    user_id: int
) -> Optional[Dict[str, Any]]:
    """
    Edit a message. Only the message owner can edit it within 15 minutes.
    Returns updated message or None if not found/unauthorized.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Check if message exists and user is the owner
        message = await conn.fetchrow(
            """
            SELECT id, sender_id, sender_type, operator_id, created_at
            FROM messages
            WHERE id = $1
            """,
            message_id
        )
        
        if not message:
            return None
        
        # Check ownership
        sender_id = message['sender_id']
        sender_type = message['sender_type']
        operator_id = message['operator_id']
        
        # User must be the sender
        if sender_type == 'operator' and operator_id != user_id:
            return None
        if sender_type == 'client' and sender_id != user_id:
            return None
        if sender_type == 'system':
            return None  # System messages cannot be edited
        
        # Check time limit (15 minutes)
        created_at = message['created_at']
        if created_at.tzinfo:
            time_diff = datetime.now(created_at.tzinfo) - created_at
        else:
            time_diff = datetime.now(timezone.utc) - created_at.replace(tzinfo=timezone.utc)
        if time_diff.total_seconds() > 15 * 60:  # 15 minutes
            return None
        
        # Update message
        await conn.execute(
            """
            UPDATE messages
            SET message_text = $1,
                edited_at = now()
            WHERE id = $2
            """,
            new_text,
            message_id
        )
        
        # Get updated message
        updated_message = await get_message_by_id(message_id)
        return updated_message
    finally:
        await conn.close()

