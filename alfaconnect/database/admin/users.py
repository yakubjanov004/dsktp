# database/admin/users.py

import asyncpg
from typing import List, Dict, Any, Optional
from config import settings

async def get_all_users_paginated(limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """Barcha foydalanuvchilar sahifalangan"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                id,
                telegram_id,
                username,
                full_name,
                phone,
                role,
                language,
                is_blocked,
                created_at,
                updated_at
            FROM users
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_users_by_role_paginated(role: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """Rol bo'yicha foydalanuvchilar sahifalangan"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                id,
                telegram_id,
                username,
                full_name,
                phone,
                role,
                language,
                is_blocked,
                created_at,
                updated_at
            FROM users
            WHERE role = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            role, limit, offset
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def search_users_paginated(search_term: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """Foydalanuvchilarni qidirish sahifalangan"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                id,
                telegram_id,
                username,
                full_name,
                phone,
                role,
                language,
                is_blocked,
                created_at,
                updated_at
            FROM users
            WHERE 
                full_name ILIKE $1 OR 
                phone ILIKE $1 OR 
                username ILIKE $1 OR
                telegram_id::text ILIKE $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            f"%{search_term}%", limit, offset
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def toggle_user_block_status(user_id: int) -> bool:
    """Foydalanuvchini bloklash/blokdan chiqarish"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        await conn.execute(
            """
            UPDATE users 
            SET is_blocked = NOT is_blocked, updated_at = NOW()
            WHERE id = $1
            """,
            user_id
        )
        return True
    except Exception as e:
        print(f"Error toggling user block status: {e}")
        return False
    finally:
        await conn.close()
