# database/controller/export.py

from typing import List, Dict, Any
import asyncpg
import logging
from config import settings

logger = logging.getLogger(__name__)

# =========================================================
#  Controller Export Functions
# =========================================================

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
        from datetime import datetime, timedelta
        today = datetime.now()
        days_since_monday = today.weekday() 
        monday = today - timedelta(days=days_since_monday)
        monday_date = monday.strftime("%Y-%m-%d")
        return f"{column} >= '{monday_date}'"
    elif time_period == "month":
        return f"{column} >= CURRENT_DATE - INTERVAL '30 days'"
    else:  # total
        return "TRUE"

async def get_controller_orders_for_export(time_period: str = "total") -> List[Dict[str, Any]]:
    """
    Controller orders ro'yxatini export uchun olish.
    Faqat texnik arizalar: technician_orders va staff_orders (type_of_zayavka = 'technician').
    time_period: 'today', 'week', 'month', 'total'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Time filter WHERE condition
        time_condition = _get_time_condition(time_period, "t.created_at")
        
        # Technician orders (mijozlar yaratgan texnik arizalar)
        tech_rows = await conn.fetch(
            f"""
            SELECT 
                t.id,
                t.application_number,
                t.region,
                t.address,
                t.description,
                'technician' as type_of_zayavka,
                t.status,
                t.created_at,
                u.full_name as client_name,
                u.phone as client_phone,
                NULL as tariff,
                t.region as region_name,
                'mijoz' as creator_type,
                a.akt_number,
                tech_user.full_name as technician_name,
                controller_user.full_name as controller_name
            FROM technician_orders t
            LEFT JOIN users u ON u.id = t.user_id
            LEFT JOIN akt_documents a ON a.application_number = t.application_number
            LEFT JOIN connections c ON c.application_number = t.application_number 
                AND c.sender_id IN (SELECT id FROM users WHERE role = 'controller')
                AND c.recipient_id IN (SELECT id FROM users WHERE role = 'technician')
            LEFT JOIN users tech_user ON tech_user.id = c.recipient_id AND tech_user.role = 'technician'
            LEFT JOIN users controller_user ON controller_user.id = c.sender_id AND controller_user.role = 'controller'
            WHERE COALESCE(t.is_active, TRUE) = TRUE
                AND {time_condition}
            ORDER BY t.created_at DESC
            """
        )
        
        # Staff orders (xodimlar yaratgan texnik xizmat arizalari)
        # Eski database bilan mos kelishi uchun cancellation_note maydonini ixtiyoriy qildik
        time_condition_staff = _get_time_condition(time_period, "s.created_at")
        staff_rows = await conn.fetch(
            f"""
            SELECT 
                s.id,
                s.application_number,
                s.region,
                s.address,
                s.description,
                s.type_of_zayavka,
                s.status,
                s.created_at,
                u.full_name as client_name,
                u.phone as client_phone,
                NULL as tariff,
                s.region as region_name,
                'xodim' as creator_type,
                a.akt_number,
                tech_user.full_name as technician_name,
                controller_user.full_name as controller_name
            FROM staff_orders s
            LEFT JOIN users u ON u.id = s.user_id
            LEFT JOIN akt_documents a ON a.application_number = s.application_number
            LEFT JOIN connections c ON c.application_number = s.application_number 
                AND c.sender_id IN (SELECT id FROM users WHERE role = 'controller')
                AND c.recipient_id IN (SELECT id FROM users WHERE role = 'technician')
            LEFT JOIN users tech_user ON tech_user.id = c.recipient_id AND tech_user.role = 'technician'
            LEFT JOIN users controller_user ON controller_user.id = c.sender_id AND controller_user.role = 'controller'
            WHERE COALESCE(s.is_active, TRUE) = TRUE
              AND s.type_of_zayavka = 'technician'
              AND {time_condition_staff}
            ORDER BY s.created_at DESC
            """
        )
        
        # Birlashtirish
        all_orders = []
        for row in tech_rows:
            all_orders.append(dict(row))
        for row in staff_rows:
            all_orders.append(dict(row))
            
        # Created_at bo'yicha tartiblash
        all_orders.sort(key=lambda x: x['created_at'], reverse=True)
        
        return all_orders
    finally:
        await conn.close()

async def get_controller_statistics_for_export(time_period: str = "total") -> Dict[str, Any]:
    """
    Controller uchun statistika export.
    time_period: 'today', 'week', 'month', 'total'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # 1. Asosiy statistika
        stats = {}
        
        # Time filter WHERE condition
        time_condition = _get_time_condition(time_period, "created_at")
        
        # 2. Umumiy texnik arizalar statistikasi
        general_stats = await conn.fetchrow(
            f"""
            SELECT 
                COUNT(*) as total_orders,
                COUNT(CASE WHEN status = 'in_controller' THEN 1 END) as in_controller,
                COUNT(CASE WHEN status = 'between_controller_technician' THEN 1 END) as between_controller_technician,
                COUNT(CASE WHEN status = 'in_technician' THEN 1 END) as in_technician,
                COUNT(CASE WHEN status = 'in_diagnostics' THEN 1 END) as in_diagnostics,
                COUNT(CASE WHEN status = 'in_repairs' THEN 1 END) as in_repairs,
                COUNT(CASE WHEN status = 'in_warehouse' THEN 1 END) as in_warehouse,
                COUNT(CASE WHEN status = 'in_technician_work' THEN 1 END) as in_technician_work,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled,
                COUNT(DISTINCT user_id) as unique_clients,
                COUNT(DISTINCT region) as unique_problem_types
            FROM technician_orders
            WHERE COALESCE(is_active, TRUE) = TRUE
                AND {time_condition}
            """
        )
        
        # Calculate completion rate and create summary structure
        completion_rate = 0
        if general_stats['total_orders'] > 0:
            completion_rate = round((general_stats['completed'] / general_stats['total_orders']) * 100, 1)
        
        stats['summary'] = {
            'total_requests': general_stats['total_orders'] or 0,
            'new_requests': general_stats['in_controller'] or 0,
            'in_progress_requests': (general_stats['between_controller_technician'] or 0) + (general_stats['in_technician'] or 0),
            'completed_requests': general_stats['completed'] or 0,
            'completion_rate': completion_rate,
            'unique_clients': general_stats['unique_clients'] or 0,
            'unique_problem_types': general_stats['unique_problem_types'] or 0
        }
        
        if time_period in ["total", "month"]:
            stats['monthly_trends'] = await conn.fetch(
                f"""
                SELECT 
                    TO_CHAR(created_at, 'YYYY-MM') as month,
                    COUNT(*) as total_requests,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_requests,
                    COUNT(CASE WHEN status = 'in_controller' THEN 1 END) as new_requests
                FROM technician_orders
                WHERE COALESCE(is_active, TRUE) = TRUE
                  AND {time_condition}
                GROUP BY TO_CHAR(created_at, 'YYYY-MM')
                ORDER BY month DESC
                """
            )
        else:
            stats['monthly_trends'] = []
        
        # 4. Technicianlar bo'yicha statistika
        # Use connections table to find orders assigned to technicians
        time_condition_for_tech = _get_time_condition(time_period, "tech_orders.created_at")
        stats['by_technician'] = await conn.fetch(
            f"""
            WITH last_assign AS (
                SELECT DISTINCT ON (c.application_number)
                       c.application_number,
                       c.recipient_id as technician_id
                FROM connections c
                WHERE c.application_number IS NOT NULL
                  AND c.recipient_id IN (SELECT id FROM users WHERE role = 'technician')
                ORDER BY c.application_number, c.created_at DESC
            )
            SELECT 
                u.full_name as technician_name,
                u.phone as technician_phone,
                COUNT(DISTINCT tech_orders.id) as total_orders,
                COUNT(DISTINCT CASE WHEN tech_orders.status = 'completed' THEN tech_orders.id END) as completed_orders,
                COUNT(DISTINCT CASE WHEN tech_orders.status IN ('between_controller_technician', 'in_technician', 'in_technician_work') THEN tech_orders.id END) as in_progress_orders,
                COUNT(DISTINCT tech_orders.user_id) as unique_clients
            FROM users u
            LEFT JOIN last_assign la ON la.technician_id = u.id
            LEFT JOIN technician_orders tech_orders ON tech_orders.application_number = la.application_number
                AND COALESCE(tech_orders.is_active, TRUE) = TRUE
                AND {time_condition_for_tech}
            WHERE u.role = 'technician'
            GROUP BY u.id, u.full_name, u.phone
            ORDER BY total_orders DESC
            """
        )
        
        stats['by_tariff'] = await conn.fetch(
            """
            SELECT 
                region as tariff_name,
                COUNT(tech_orders.id) as total_orders,
                COUNT(DISTINCT tech_orders.user_id) as unique_clients,
                TO_CHAR(AVG(EXTRACT(EPOCH FROM tech_orders.created_at)) * INTERVAL '1 second', 'YYYY-MM-DD') as avg_order_date
            FROM technician_orders tech_orders
            WHERE COALESCE(tech_orders.is_active, TRUE) = TRUE
            GROUP BY tech_orders.region
            ORDER BY total_orders DESC
            """
        )
        
        stats['recent_activity'] = await conn.fetch(
            """
            SELECT 
                u.full_name as technician_name,
                u.phone as technician_phone,
                COUNT(tech_orders.id) as recent_orders,
                MAX(tech_orders.created_at) as last_order_date
            FROM users u
            LEFT JOIN technician_orders tech_orders ON tech_orders.user_id = u.id 
                AND COALESCE(tech_orders.is_active, TRUE) = TRUE
                AND tech_orders.created_at >= NOW() - INTERVAL '30 days'
            WHERE u.role = 'technician'
            GROUP BY u.id, u.full_name, u.phone
            ORDER BY recent_orders DESC
            LIMIT 10
            """
        )
        
        
        return stats
    finally:
        await conn.close()

async def get_controller_employees_for_export() -> List[Dict[str, Any]]:
    """
    Controller uchun xodimlar ro'yxatini export uchun olish.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        users = await conn.fetch(
            """
            SELECT DISTINCT ON (u.id)
                u.id,
                u.full_name,
                u.phone,
                u.username,
                u.telegram_id,
                u.role,
                u.is_blocked,
                u.created_at
            FROM users u
            WHERE u.role IN ('controller', 'technician')
            ORDER BY u.id, u.role, u.full_name
            """
        )
        
        # Then get order counts for each user
        result = []
        seen_ids = set()  # Additional safety check
        
        for user in users:
            user_id = user['id']
            
            # Skip if we've already processed this user
            if user_id in seen_ids:
                logger.warning(f"Duplicate user detected: {user_id} - {user['full_name']}")
                continue
            
            seen_ids.add(user_id)
            user_dict = dict(user)
            
            # Get order counts for this user
            order_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_orders,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_orders
                FROM staff_orders 
                WHERE user_id = $1 AND COALESCE(is_active, TRUE) = TRUE
                """,
                user_id
            )
            
            user_dict['total_orders'] = order_stats['total_orders'] if order_stats else 0
            user_dict['completed_orders'] = order_stats['completed_orders'] if order_stats else 0
            
            result.append(user_dict)
        
        return result
    finally:
        await conn.close()
