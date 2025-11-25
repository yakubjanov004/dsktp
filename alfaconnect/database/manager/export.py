# database/manager/export.py
# Manager roli uchun export queries

import asyncpg
from config import settings
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# =========================================================
#  Helper Functions
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

# =========================================================
#  Connection Orders Export
# =========================================================

async def get_manager_connection_orders_for_export(time_period: str = "total") -> List[Dict[str, Any]]:
    """Fetch all connection orders for manager export
    time_period: 'today', 'week', 'month', 'total'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        time_condition = _get_time_condition(time_period, "co.created_at")
        query = f"""
        SELECT 
            co.id, 
            co.application_number,
            u.full_name as client_name,
            u.phone as phone_number,
            co.region,
            co.address,
            t.name as plan_name,
            co.created_at as connection_date,
            co.status,
            co.jm_notes
        FROM connection_orders co
        LEFT JOIN users u ON co.user_id = u.id
        LEFT JOIN tarif t ON co.tarif_id = t.id
        WHERE {time_condition}
        ORDER BY co.created_at DESC
        """
        rows = await conn.fetch(query)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching connection orders for export: {e}")
        return []
    finally:
        await conn.close()

# =========================================================
#  Statistics Export
# =========================================================

async def get_manager_statistics_for_export(time_period: str = "total") -> Dict[str, Any]:
    """Fetch detailed statistics for manager export
    time_period: 'today', 'week', 'month', 'total'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # 1. Asosiy statistika
        stats = {}
        
        # Time filter WHERE condition
        time_condition = _get_time_condition(time_period, "created_at")
        
        # 2. Umumiy arizalar statistikasi
        general_stats = await conn.fetchrow(f"""
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN status = 'in_manager' THEN 1 ELSE 0 END) as new_orders,
                SUM(CASE WHEN status IN ('in_manager', 'in_junior_manager', 'in_controller', 'in_technician', 'in_technician_work') THEN 1 ELSE 0 END) as in_progress_orders,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
                COUNT(DISTINCT user_id) as unique_clients,
                COUNT(DISTINCT tarif_id) as unique_tariffs_used
            FROM connection_orders
            WHERE {time_condition}
        """)
        
        # Calculate completion rate
        completion_rate = 0
        if general_stats['total_orders'] > 0:
            completion_rate = round((general_stats['completed_orders'] / general_stats['total_orders']) * 100, 1)
        
        # Create summary structure expected by the handler
        stats['summary'] = {
            'total_orders': general_stats['total_orders'] or 0,
            'new_orders': general_stats['new_orders'] or 0,
            'in_progress_orders': general_stats['in_progress_orders'] or 0,
            'completed_orders': general_stats['completed_orders'] or 0,
            'completion_rate': completion_rate,
            'unique_clients': general_stats['unique_clients'] or 0,
            'unique_tariffs_used': general_stats['unique_tariffs_used'] or 0
        }
        
        # 3. Oylik ariza statistikasi (oxirgi 6 oy)
        if time_period in ["total", "month"]:
            stats['monthly_trends'] = await conn.fetch(f"""
                SELECT 
                    TO_CHAR(created_at, 'YYYY-MM') as month,
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
                    SUM(CASE WHEN status = 'in_manager' THEN 1 ELSE 0 END) as new_orders
                FROM connection_orders
                WHERE {time_condition}
                  AND created_at >= NOW() - INTERVAL '6 months'
                GROUP BY TO_CHAR(created_at, 'YYYY-MM')
                ORDER BY month DESC
            """)
        else:
            stats['monthly_trends'] = []
        
        # 4. Menejerlar bo'yicha statistika
        # Managerlar connections jadvali orqali buyurtmalarga biriktiriladi
        # Manager recipient_id yoki sender_id sifatida bo'lishi mumkin
        time_condition_manager = _get_time_condition(time_period, "co.created_at")
        stats['by_manager'] = await conn.fetch(f"""
            WITH last_assignments AS (
                -- Har bir application_number uchun eng oxirgi assignment'ni topamiz
                SELECT DISTINCT ON (c.application_number)
                       c.application_number,
                       CASE 
                           WHEN c.recipient_id IN (SELECT id FROM users WHERE role IN ('manager', 'junior_manager')) 
                           THEN c.recipient_id
                           WHEN c.sender_id IN (SELECT id FROM users WHERE role IN ('manager', 'junior_manager'))
                           THEN c.sender_id
                           ELSE NULL
                       END as manager_id
                FROM connections c
                WHERE c.application_number IS NOT NULL
                  AND (c.recipient_id IN (SELECT id FROM users WHERE role IN ('manager', 'junior_manager'))
                       OR c.sender_id IN (SELECT id FROM users WHERE role IN ('manager', 'junior_manager')))
                ORDER BY c.application_number, c.created_at DESC
            )
            SELECT 
                u.full_name as manager_name,
                u.phone as manager_phone,
                COUNT(DISTINCT la.application_number) as total_orders,
                COUNT(DISTINCT CASE WHEN co.status = 'completed' THEN la.application_number END) as completed_orders,
                COUNT(DISTINCT CASE WHEN co.status IN ('in_manager', 'in_junior_manager', 'in_controller', 'in_technician', 'in_technician_work') THEN la.application_number END) as in_progress_orders,
                COUNT(DISTINCT co.user_id) as unique_clients
            FROM users u
            LEFT JOIN last_assignments la ON la.manager_id = u.id AND la.manager_id IS NOT NULL
            LEFT JOIN connection_orders co ON co.application_number = la.application_number 
                AND {time_condition_manager}
                AND COALESCE(co.is_active, TRUE) = TRUE
            WHERE u.role IN ('manager', 'junior_manager')
            GROUP BY u.id, u.full_name, u.phone
            ORDER BY total_orders DESC
        """)
        
        # 5. Tarif rejalari bo'yicha statistika
        time_condition_tariff = _get_time_condition(time_period, "co.created_at")
        stats['by_tariff'] = await conn.fetch(f"""
            SELECT 
                t.name as tariff_name,
                COUNT(co.id) as total_orders,
                COUNT(DISTINCT co.user_id) as unique_clients,
                TO_CHAR(AVG(EXTRACT(EPOCH FROM co.created_at)) * INTERVAL '1 second', 'YYYY-MM-DD') as avg_order_date
            FROM tarif t
            LEFT JOIN connection_orders co ON t.id = co.tarif_id AND {time_condition_tariff}
            GROUP BY t.id, t.name
            HAVING COUNT(co.id) > 0
            ORDER BY total_orders DESC
        """)
        
        # 6. So'ngi 30 kun ichidagi faol menejerlar
        time_condition_recent = _get_time_condition(time_period, "co.created_at")
        stats['recent_activity'] = await conn.fetch(f"""
            SELECT 
                u.full_name as manager_name,
                COUNT(co.id) as recent_orders,
                MAX(co.updated_at) as last_activity
            FROM users u
            LEFT JOIN connection_orders co ON u.id = co.user_id 
                AND {time_condition_recent}
                AND co.updated_at >= NOW() - INTERVAL '30 days'
            WHERE u.role IN ('manager', 'junior_manager')
            GROUP BY u.id, u.full_name
            ORDER BY recent_orders DESC
            LIMIT 10
        """)
        
        # 7. Handle empty results
        if not general_stats:
            return {
                'summary': {
                    'total_orders': 0,
                    'new_orders': 0,
                    'in_progress_orders': 0,
                    'completed_orders': 0,
                    'unique_clients': 0,
                    'unique_tariffs_used': 0,
                    'completion_rate': 0,
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                'monthly_trends': [],
                'by_manager': [],
                'by_tariff': [],
                'recent_activity': []
            }
            
        # 8. Umumiy statistika
        result = {
            'summary': {
                'total_orders': general_stats['total_orders'] or 0,
                'new_orders': general_stats['new_orders'] or 0,
                'in_progress_orders': general_stats['in_progress_orders'] or 0,
                'completed_orders': general_stats['completed_orders'] or 0,
                'unique_clients': general_stats['unique_clients'] or 0,
                'unique_tariffs_used': general_stats['unique_tariffs_used'] or 0,
                'completion_rate': round((general_stats['completed_orders'] or 0) / 
                                      (general_stats['total_orders'] or 1) * 100, 2),
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            'monthly_trends': [dict(row) for row in stats['monthly_trends']],
            'by_manager': [dict(row) for row in stats['by_manager']],
            'by_tariff': [dict(row) for row in stats['by_tariff']],
            'recent_activity': [dict(row) for row in stats['recent_activity']]
        }
        
        return result
    except Exception as e:
        logger.error(f"Error fetching manager statistics for export: {e}")
        return {
            'summary': {
                'total_orders': 0,
                'new_orders': 0,
                'in_progress_orders': 0,
                'completed_orders': 0,
                'unique_clients': 0,
                'unique_tariffs_used': 0,
                'completion_rate': 0,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            'monthly_trends': [],
            'by_manager': [],
            'by_tariff': [],
            'recent_activity': []
        }
    finally:
        await conn.close()

# =========================================================
#  Employees Export
# =========================================================

async def get_manager_employees_for_export() -> List[Dict[str, Any]]:
    """Fetch employees list for manager export"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        query = """
        SELECT 
            telegram_id,
            full_name,
            username,
            phone,
            role,
            is_blocked,
            created_at
        FROM users
        WHERE role IN ('manager', 'junior_manager')
        ORDER BY created_at DESC
        """
        rows = await conn.fetch(query)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching employees for export: {e}")
        return []
    finally:
        await conn.close()

# =========================================================
#  Staff Orders Export
# =========================================================

async def get_manager_staff_orders_for_export() -> List[Dict[str, Any]]:
    """Fetch staff orders for manager export"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        query = """
        SELECT 
            so.id,
            so.user_id,
            so.phone,
            so.abonent_id,
            so.region,
            so.address,
            so.description,
            so.status,
            so.type_of_zayavka,
            so.is_active,
            so.created_at,
            so.updated_at,
            u.full_name as creator_name,
            u.phone as creator_phone,
            client.full_name as client_name,
            client.phone as client_phone
        FROM staff_orders so
        LEFT JOIN users u ON so.user_id = u.id
        LEFT JOIN users client ON client.id::text = so.abonent_id
        ORDER BY so.created_at DESC
        """
        rows = await conn.fetch(query)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching staff orders for export: {e}")
        return []
    finally:
        await conn.close()

# =========================================================
#  Smart Service Orders Export
# =========================================================

async def get_manager_smart_service_orders_for_export() -> List[Dict[str, Any]]:
    """Fetch smart service orders for manager export"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        query = """
        SELECT 
            sso.id,
            sso.user_id,
            sso.category,
            sso.service_type,
            sso.address,
            sso.latitude,
            sso.longitude,
            sso.description,
            sso.is_active,
            sso.created_at,
            sso.updated_at,
            u.full_name as client_name,
            u.phone as client_phone,
            u.username
        FROM smart_service_orders sso
        LEFT JOIN users u ON sso.user_id = u.id
        ORDER BY sso.created_at DESC
        """
        rows = await conn.fetch(query)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching smart service orders for export: {e}")
        return []
    finally:
        await conn.close()

# =========================================================
#  Technician Orders Export
# =========================================================

async def get_manager_technician_orders_for_export() -> List[Dict[str, Any]]:
    """Fetch technician orders for manager export"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        query = """
        SELECT 
            tech_orders.id,
            tech_orders.user_id,
            tech_orders.phone,
            tech_orders.abonent_id,
            tech_orders.region,
            tech_orders.address,
            tech_orders.description,
            tech_orders.status,
            tech_orders.is_active,
            tech_orders.created_at,
            tech_orders.updated_at,
            tech_orders.media,
            u.full_name as creator_name,
            u.phone as creator_phone,
            client.full_name as client_name,
            client.phone as client_phone
        FROM technician_orders tech_orders
        LEFT JOIN users u ON tech_orders.user_id = u.id
        LEFT JOIN users client ON client.id::text = tech_orders.abonent_id
        ORDER BY tech_orders.created_at DESC
        """
        rows = await conn.fetch(query)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching technician orders for export: {e}")
        return []
    finally:
        await conn.close()
