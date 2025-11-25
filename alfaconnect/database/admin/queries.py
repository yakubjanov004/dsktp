# database/admin/queries.py

import asyncpg
from typing import List, Dict, Any, Optional
from config import settings

async def get_user_statistics() -> Dict[str, Any]:
    """Foydalanuvchilar statistikasi"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Get basic stats
        stats = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN is_blocked = FALSE THEN 1 END) as active_users,
                COUNT(CASE WHEN is_blocked = TRUE THEN 1 END) as blocked_users
            FROM users
            """
        )
        
        # Get role statistics
        role_stats = await conn.fetch(
            """
            SELECT 
                role,
                COUNT(*) as count
            FROM users
            GROUP BY role
            ORDER BY count DESC
            """
        )
        
        result = dict(stats) if stats else {}
        result['role_statistics'] = [dict(row) for row in role_stats]
        
        return result
    except Exception as e:
        print(f"Error in get_user_statistics: {e}")
        return {'total_users': 0, 'active_users': 0, 'blocked_users': 0, 'role_statistics': []}
    finally:
        await conn.close()

async def get_system_overview() -> Dict[str, Any]:
    """Tizim umumiy ko'rinishi"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        overview = await conn.fetchrow(
            """
            SELECT 
                (SELECT COUNT(*) FROM users) as total_users,
                (SELECT COUNT(*) FROM users WHERE is_blocked = FALSE) as active_users,
                (SELECT COUNT(*) FROM users WHERE is_blocked = TRUE) as blocked_users,
                (SELECT COUNT(*) FROM connection_orders WHERE is_active = TRUE) as total_connection_orders,
                (SELECT COUNT(*) FROM technician_orders WHERE is_active = TRUE) as total_technician_orders,
                (SELECT COUNT(*) FROM staff_orders WHERE is_active = TRUE) as total_staff_orders,
                (SELECT COUNT(*) FROM connection_orders WHERE is_active = TRUE AND DATE(created_at) = CURRENT_DATE) as today_connection_orders,
                (SELECT COUNT(*) FROM technician_orders WHERE is_active = TRUE AND DATE(created_at) = CURRENT_DATE) as today_technician_orders,
                (SELECT COUNT(*) FROM materials) as total_materials,
                (SELECT COUNT(*) FROM connections) as total_connections,
                (SELECT COUNT(*) FROM akt_ratings) as total_ratings
            """
        )
        
        # Rollar bo'yicha statistika
        role_stats = await conn.fetch(
            """
            SELECT 
                role,
                COUNT(*) as count
            FROM users
            GROUP BY role
            ORDER BY count DESC
            """
        )
        result = dict(overview) if overview else {}
        
        # Rollar bo'yicha statistikani qo'shish
        users_by_role = {}
        for row in role_stats:
            users_by_role[row['role']] = row['count']
        result['users_by_role'] = users_by_role
        
        return result
    except Exception as e:
        print(f"Error in get_system_overview: {e}")
        return {}
    finally:
        await conn.close()

async def get_recent_activity(limit: int = 10) -> List[Dict[str, Any]]:
    """So'nggi faoliyat"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                'connection' as type,
                application_number,
                created_at,
                status
            FROM connection_orders
            WHERE is_active = TRUE
            UNION ALL
            SELECT 
                'technician' as type,
                application_number,
                created_at,
                status
            FROM technician_orders
            WHERE is_active = TRUE
            UNION ALL
            SELECT 
                'staff' as type,
                application_number,
                created_at,
                status
            FROM staff_orders
            WHERE is_active = TRUE
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_performance_metrics() -> Dict[str, Any]:
    """Ishlash ko'rsatkichlari"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        metrics = await conn.fetchrow(
            """
            SELECT 
                (SELECT AVG(rating) FROM akt_ratings WHERE rating > 0) as avg_rating,
                (SELECT COUNT(*) FROM connection_orders WHERE status = 'completed' AND created_at >= NOW() - INTERVAL '30 days') as completed_connections_30d,
                (SELECT COUNT(*) FROM technician_orders WHERE status = 'completed' AND created_at >= NOW() - INTERVAL '30 days') as completed_technician_30d,
                (SELECT COUNT(*) FROM staff_orders WHERE status = 'completed' AND created_at >= NOW() - INTERVAL '30 days') as completed_staff_30d
            """
        )
        return dict(metrics) if metrics else {}
    finally:
        await conn.close()

async def get_database_info() -> Dict[str, Any]:
    """Database ma'lumotlari"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        info = await conn.fetchrow(
            """
            SELECT 
                pg_database_size(current_database()) as database_size,
                (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public') as table_count
            """
        )
        return dict(info) if info else {}
    finally:
        await conn.close()
