# database/call_center_supervisor/statistics.py
import asyncpg
from config import settings
from typing import Dict, Any, List
from datetime import datetime, timedelta

async def get_active_connection_tasks_count() -> int:
    """
    Aktiv vazifalar soni:
      staff_orders jadvalidan is_active = TRUE
      va status 'completed' EMAS
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
              FROM staff_orders
             WHERE is_active = TRUE
               AND status <> 'completed'
            """
        )
    finally:
        await conn.close()

async def get_callcenter_operator_count() -> int:
    """
    Umumiy xodimlar soni:
      users jadvalidan role = 'callcenter_operator'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
              FROM users
             WHERE role IN ('callcenter_operator', 'callcenter_supervisor')
            """
        )
    finally:
        await conn.close()

async def get_canceled_connection_tasks_count() -> int:
    """
    Bekor qilingan vazifalar soni:
      staff_orders jadvalidan is_active = False
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
              FROM staff_orders
             WHERE is_active = FALSE
            """
        )
    finally:
        await conn.close()

async def get_completed_connection_tasks_count() -> int:
    """
    Yakunlangan vazifalar soni:
      staff_orders jadvalidan status = 'completed'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
              FROM staff_orders
             WHERE status = 'completed'
            """
        )
    finally:
        await conn.close()

async def get_callcenter_comprehensive_stats() -> Dict[str, Any]:
    """
    Call center uchun to'liq statistika - admin kabi
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Umumiy statistika
        total_operators = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE role = 'callcenter_operator'"
        )
        total_supervisors = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE role = 'callcenter_supervisor'"
        )
        
        # Bugungi arizalar
        today_orders = await conn.fetchval(
            """
            SELECT COUNT(*) FROM staff_orders 
            WHERE DATE(created_at) = CURRENT_DATE
            """
        )
        
        # Haftalik arizalar
        week_orders = await conn.fetchval(
            """
            SELECT COUNT(*) FROM staff_orders 
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            """
        )
        
        # Oylik arizalar
        month_orders = await conn.fetchval(
            """
            SELECT COUNT(*) FROM staff_orders 
            WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
            """
        )
        
        # Status bo'yicha statistika
        status_stats = await conn.fetch(
            """
            SELECT status, COUNT(*) as count
            FROM staff_orders
            WHERE is_active = TRUE
            GROUP BY status
            ORDER BY count DESC
            """
        )
        
        # Tur bo'yicha statistika
        type_stats = await conn.fetch(
            """
            SELECT type_of_zayavka, COUNT(*) as count
            FROM staff_orders
            WHERE is_active = TRUE
            GROUP BY type_of_zayavka
            ORDER BY count DESC
            """
        )
        
        # Operatorlar statistikasi
        operator_stats = await conn.fetch(
            """
            SELECT 
                u.full_name,
                u.username,
                COUNT(so.id) as total_orders,
                COUNT(CASE WHEN so.is_active = TRUE THEN 1 END) as active_orders,
                COUNT(CASE WHEN so.status = 'completed' THEN 1 END) as completed_orders,
                COUNT(CASE WHEN DATE(so.created_at) = CURRENT_DATE THEN 1 END) as today_orders
            FROM users u
            LEFT JOIN staff_orders so ON so.user_id = u.id
            WHERE u.role IN ('callcenter_operator', 'callcenter_supervisor')
            GROUP BY u.id, u.full_name, u.username
            ORDER BY total_orders DESC
            """
        )
        
        # Kunlik tendensiya (oxirgi 7 kun)
        daily_trends = await conn.fetch(
            """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as total_orders,
                COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_orders,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_orders
            FROM staff_orders
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            """
        )
        
        return {
            'overview': {
                'total_operators': total_operators,
                'total_supervisors': total_supervisors,
                'total_staff': total_operators + total_supervisors,
                'today_orders': today_orders,
                'week_orders': week_orders,
                'month_orders': month_orders
            },
            'status_statistics': {row['status']: row['count'] for row in status_stats},
            'type_statistics': {row['type_of_zayavka']: row['count'] for row in type_stats},
            'operator_statistics': [dict(row) for row in operator_stats],
            'daily_trends': [dict(row) for row in daily_trends]
        }
    finally:
        await conn.close()

async def get_operator_orders_stat() -> Dict[str, Any]:
    """
    Operatorlar statistikasi:
      Har bir operator uchun arizalar soni
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                u.full_name,
                u.username,
                COUNT(so.id) as orders_count,
                COUNT(CASE WHEN so.is_active = TRUE THEN 1 END) as active_orders,
                COUNT(CASE WHEN so.status = 'completed' THEN 1 END) as completed_orders
            FROM users u
            LEFT JOIN staff_orders so ON so.user_id = u.id
            WHERE u.role IN ('callcenter_operator', 'callcenter_supervisor')
            GROUP BY u.id, u.full_name, u.username
            ORDER BY orders_count DESC
            """
        )
        
        result = {
            'operators': [dict(row) for row in rows],
            'total_operators': len(rows),
            'total_orders': sum(row['orders_count'] for row in rows),
            'total_active_orders': sum(row['active_orders'] for row in rows),
            'total_completed_orders': sum(row['completed_orders'] for row in rows)
        }
        
        return result
    finally:
        await conn.close()

async def get_daily_statistics(days: int = 7) -> List[Dict[str, Any]]:
    """
    Kunlik statistikalar:
      Oxirgi N kun uchun kunlik arizalar soni
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as total_orders,
                COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_orders,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_orders
            FROM staff_orders
            WHERE created_at >= NOW() - make_interval(days => $1)
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            """,
            days
        )
        
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_monthly_statistics(months: int = 12) -> List[Dict[str, Any]]:
    """
    Oylik statistikalar:
      Oxirgi N oy uchun oylik arizalar soni
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                DATE_TRUNC('month', created_at) as month,
                COUNT(*) as total_orders,
                COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_orders,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_orders
            FROM staff_orders
            WHERE created_at >= NOW() - make_interval(months => $1)
            GROUP BY DATE_TRUNC('month', created_at)
            ORDER BY month DESC
            """,
            months
        )
        
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_status_statistics() -> Dict[str, int]:
    """
    Status bo'yicha statistikalar:
      Har bir status uchun arizalar soni
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                status,
                COUNT(*) as count
            FROM staff_orders
            WHERE is_active = TRUE
            GROUP BY status
            ORDER BY count DESC
            """
        )
        
        return {row['status']: row['count'] for row in rows}
    finally:
        await conn.close()

async def get_type_statistics() -> Dict[str, int]:
    """
    Tur bo'yicha statistikalar:
      Har bir ariza turi uchun arizalar soni
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                type_of_zayavka,
                COUNT(*) as count
            FROM staff_orders
            WHERE is_active = TRUE
            GROUP BY type_of_zayavka
            ORDER BY count DESC
            """
        )
        
        return {row['type_of_zayavka']: row['count'] for row in rows}
    finally:
        await conn.close()

async def get_performance_metrics() -> Dict[str, Any]:
    """
    Ishlash ko'rsatkichlari:
      Call center uchun performance metrikalari
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Bugungi ishlash ko'rsatkichlari
        today_metrics = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_orders,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_orders,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_orders,
                AVG(CASE WHEN status = 'completed' 
                    THEN EXTRACT(EPOCH FROM (updated_at - created_at))/3600 
                    ELSE NULL END) as avg_completion_hours
            FROM staff_orders
            WHERE DATE(created_at) = CURRENT_DATE
            """
        )
        
        # Haftalik ishlash ko'rsatkichlari
        week_metrics = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_orders,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_orders,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_orders,
                AVG(CASE WHEN status = 'completed' 
                    THEN EXTRACT(EPOCH FROM (updated_at - created_at))/3600 
                    ELSE NULL END) as avg_completion_hours
            FROM staff_orders
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            """
        )
        
        return {
            'today': dict(today_metrics) if today_metrics else {},
            'week': dict(week_metrics) if week_metrics else {}
        }
    finally:
        await conn.close()
