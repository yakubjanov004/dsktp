"""
User online/offline status queries
"""
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import asyncpg
from config import settings

# Online status TTL: user is considered online if last_seen_at is within this duration
ONLINE_TTL = timedelta(seconds=60)


def is_user_online(last_seen_at: Optional[datetime]) -> bool:
    """
    Calculate if user is online based on last_seen_at timestamp.
    
    Rule: User is online if last_seen_at is within ONLINE_TTL (60 seconds).
    
    Args:
        last_seen_at: Timestamp when user was last seen
        
    Returns:
        True if user is online, False otherwise
    """
    if last_seen_at is None:
        return False
    
    now = datetime.now(timezone.utc)
    time_diff = now - last_seen_at
    
    # Handle future timestamps (clock skew)
    if time_diff.total_seconds() < 0:
        return True
    
    return time_diff <= ONLINE_TTL


async def update_user_last_seen(user_id: int, last_seen_at: Optional[datetime] = None, is_online: Optional[bool] = None) -> bool:
    """
    Update user last_seen_at timestamp and is_online status (heartbeat).
    
    Args:
        user_id: User ID
        last_seen_at: Timestamp (defaults to now if None)
        is_online: Online status (True/False). If None, calculated from TTL.
        
    Returns:
        True if update successful, False otherwise
    """
    if last_seen_at is None:
        last_seen_at = datetime.now(timezone.utc)
    
    # Calculate is_online if not provided
    if is_online is None:
        is_online = True  # If sending heartbeat, user is online
    
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        await conn.execute(
            """
            UPDATE users
            SET last_seen_at = $1,
                is_online = $2,
                updated_at = $1
            WHERE id = $3
            """,
            last_seen_at,
            is_online,
            user_id
        )
        return True
    except Exception as e:
        import logging
        logging.error(f"Error updating user last_seen_at: {e}")
        return False
    finally:
        await conn.close()


async def get_user_status(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get user online status (calculated from last_seen_at) and last_seen_at.
    
    Args:
        user_id: User ID
        
    Returns:
        Dict with is_online (calculated) and last_seen_at, or None if user not found
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT id, last_seen_at
            FROM users
            WHERE id = $1
            """,
            user_id
        )
        if not row:
            return None
        
        last_seen_at = row['last_seen_at']
        is_online = is_user_online(last_seen_at)
        
        return {
            'id': row['id'],
            'is_online': is_online,
            'last_seen_at': last_seen_at
        }
    finally:
        await conn.close()


async def get_online_users(role: Optional[str] = None) -> list[Dict[str, Any]]:
    """
    Get list of online users (calculated from last_seen_at), optionally filtered by role.
    
    Args:
        role: Optional role filter (e.g., 'callcenter_operator', 'client')
        
    Returns:
        List of user dicts with id, full_name, role, is_online (calculated), last_seen_at
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if role:
            rows = await conn.fetch(
                """
                SELECT id, full_name, role, last_seen_at
                FROM users
                WHERE role = $1
                ORDER BY last_seen_at DESC NULLS LAST
                """,
                role
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, full_name, role, last_seen_at
                FROM users
                ORDER BY last_seen_at DESC NULLS LAST
                """
            )
        
        # Filter and calculate is_online for each user
        now = datetime.now(timezone.utc)
        online_users = []
        for row in rows:
            last_seen_at = row['last_seen_at']
            if last_seen_at and (now - last_seen_at) <= ONLINE_TTL:
                user_dict = dict(row)
                user_dict['is_online'] = True
                online_users.append(user_dict)
        
        return online_users
    finally:
        await conn.close()

