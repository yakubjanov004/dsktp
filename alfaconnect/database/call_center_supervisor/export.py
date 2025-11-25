# database/call_center_supervisor/export.py
import asyncpg
from config import settings
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def _get_time_condition(time_period: str, column: str) -> str:
    """
    Get SQL WHERE condition for time period filtering.
    time_period: 'today', 'week', 'month', 'total'
    column: column name to filter on (e.g., 'created_at')
    
    For 'week': calculates from Monday to today
    """
    if time_period == "today":
        return f"{column} >= CURRENT_DATE"
    elif time_period == "week":
        today = datetime.now()
        days_since_monday = today.weekday() 
        monday = today - timedelta(days=days_since_monday)
        monday_date = monday.strftime("%Y-%m-%d")
        return f"{column} >= '{monday_date}'"
    elif time_period == "month":
        return f"{column} >= CURRENT_DATE - INTERVAL '30 days'"
    else:  # total
        return "TRUE"

async def get_ccs_connection_orders_for_export() -> List[Dict[str, Any]]:
    """Fetch connection orders handled by call center supervisors for export"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        
        # Get orders that are handled by call center operators under this supervisor
        query = """
        SELECT 
            co.id,
            co.application_number,
            co.region,
            co.address,
            co.created_at as connection_date,
            co.status,
            co.jm_notes as call_center_comments,
            u.full_name as client_name,
            u.phone as client_phone,
            t.name as tariff_name
        FROM connection_orders co
        LEFT JOIN users u ON co.user_id = u.id
        LEFT JOIN tarif t ON co.tarif_id = t.id
        ORDER BY co.created_at DESC
        """
        
        rows = await conn.fetch(query)
        
        result = []
        for row in rows:
            result.append({
                'ID': row['id'],
                'Ariza raqami': row['application_number'] or '',
                'Mijoz ismi': row['client_name'] or '',
                'Telefon': row['client_phone'] or '',
                'Hudud': row['region'] or '',
                'Manzil': row['address'] or '',
                'Ulanish sanasi': row['connection_date'].strftime('%Y-%m-%d %H:%M:%S') if row['connection_date'] else '',
                'Status': row['status'] or '',
                'Call center izohlari': row['call_center_comments'] or '',
                'Tarif': row['tariff_name'] or ''
            })
        
        return result
    finally:
        await conn.close()

async def get_ccs_operator_orders_for_export(time_period: str = "total") -> List[Dict[str, Any]]:
    """Fetch operator orders handled by call center supervisors for export
    time_period: 'today', 'week', 'month', 'total'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        time_condition = _get_time_condition(time_period, "so.created_at")
        query = f"""
        SELECT 
            so.id,
            so.application_number,
            so.region,
            so.address,
            so.description,
            so.type_of_zayavka,
            so.status,
            so.created_at,
            u.full_name as client_name,
            u.phone as client_phone,
            t.name as tariff_name
        FROM staff_orders so
        LEFT JOIN users u ON so.user_id = u.id
        LEFT JOIN tarif t ON t.id = so.tarif_id
        WHERE {time_condition}
        ORDER BY so.created_at DESC
        """
        
        rows = await conn.fetch(query)
        
        result = []
        for row in rows:
            result.append({
                'ID': row['id'],
                'Ariza raqami': row['application_number'] or '',
                'Mijoz ismi': row['client_name'] or '',
                'Telefon': row['client_phone'] or '',
                'Hudud': str(row['region']) if row['region'] else '',
                'Manzil': row['address'] or '',
                'Tavsif': row['description'] or '',
                'Ariza turi': row['type_of_zayavka'] or '',
                'Status': row['status'] or '',
                'Yaratilgan sana': row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if row['created_at'] else '',
                'Tarif': row['tariff_name'] or ''
            })
        
        return result
    finally:
        await conn.close()

async def get_ccs_operators_for_export() -> List[Dict[str, Any]]:
    """Fetch operators under call center supervisors for export"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        query = """
        SELECT 
            u.id,
            u.telegram_id,
            u.full_name,
            u.username,
            u.phone,
            u.region,
            u.address,
            u.created_at,
            u.updated_at,
            u.is_blocked
        FROM users u
        WHERE u.role = 'callcenter_operator'
        ORDER BY u.created_at DESC
        """
        
        rows = await conn.fetch(query)
        
        result = []
        for row in rows:
            result.append({
                'ID': row['id'],
                'Telegram ID': str(row['telegram_id']) if row['telegram_id'] else '',
                'To\'liq ism': row['full_name'] or '',
                'Username': row['username'] or '',
                'Telefon': row['phone'] or '',
                'Hudud': str(row['region']) if row['region'] else '',
                'Manzil': row['address'] or '',
                'Yaratilgan sana': row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if row['created_at'] else '',
                'Yangilanish sanasi': row['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if row['updated_at'] else '',
                'Bloklangan': 'Ha' if row['is_blocked'] else 'Yo\'q'
            })
        
        return result
    finally:
        await conn.close()

async def get_ccs_statistics_for_export(time_period: str = "total") -> List[Dict[str, Any]]:
    """Fetch statistics for call center supervisors for export
    time_period: 'today', 'week', 'month', 'total'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Get various statistics
        stats = {}
        
        time_condition = _get_time_condition(time_period, "created_at")
        
        # Total orders count
        total_orders = await conn.fetchval(f"SELECT COUNT(*) FROM staff_orders WHERE {time_condition}")
        stats['Jami arizalar'] = total_orders or 0
        
        # Active orders count
        active_orders = await conn.fetchval(f"SELECT COUNT(*) FROM staff_orders WHERE is_active = TRUE AND {time_condition}")
        stats['Aktiv arizalar'] = active_orders or 0
        
        # Orders by status
        status_counts = await conn.fetch(f"""
            SELECT status, COUNT(*) as count 
            FROM staff_orders 
            WHERE is_active = TRUE AND {time_condition}
            GROUP BY status
        """)
        
        for row in status_counts:
            stats[f'Status: {row["status"]}'] = row['count']
        
        # Orders by type
        type_counts = await conn.fetch(f"""
            SELECT type_of_zayavka, COUNT(*) as count 
            FROM staff_orders 
            WHERE is_active = TRUE AND {time_condition}
            GROUP BY type_of_zayavka
        """)
        
        for row in type_counts:
            stats[f'Tur: {row["type_of_zayavka"]}'] = row['count']
        
        # Recent orders (last 30 days)
        recent_condition = f"{time_condition} AND created_at >= NOW() - INTERVAL '30 days'"
        recent_orders = await conn.fetchval(f"""
            SELECT COUNT(*) 
            FROM staff_orders 
            WHERE {recent_condition}
        """)
        stats['Oxirgi 30 kun'] = recent_orders or 0
        
        # Convert to list format for export
        result = []
        for key, value in stats.items():
            result.append({
                'Ko\'rsatkich': key,
                'Qiymat': str(value)
            })
        
        return result
    finally:
        await conn.close()
