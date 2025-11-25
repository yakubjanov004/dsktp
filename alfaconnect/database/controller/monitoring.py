# database/controller/monitoring.py

from typing import Dict, Any, List
import asyncpg
import logging
from config import settings

logger = logging.getLogger(__name__)

# =========================================================
#  Controller Real-time Monitoring
# =========================================================

async def get_realtime_counts() -> Dict[str, int]:
    """
    Controller uchun real-time counts olish.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        stats = await conn.fetchrow(
            """
            WITH last_assign AS (
                SELECT DISTINCT ON (c.application_number)
                       c.application_number,
                       c.recipient_id,
                       c.recipient_status
                FROM connections c
                WHERE c.application_number IS NOT NULL
                ORDER BY c.application_number, c.created_at DESC
            )
            SELECT 
                COUNT(CASE WHEN so.status = 'in_controller' THEN 1 END) as in_controller,
                COUNT(CASE WHEN so.status = 'between_controller_technician' THEN 1 END) as between_controller_technician,
                COUNT(CASE WHEN so.status = 'in_technician' THEN 1 END) as in_technician,
                COUNT(CASE WHEN so.status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN so.status = 'cancelled' THEN 1 END) as cancelled,
                COUNT(*) as total_active
            FROM staff_orders so
            JOIN last_assign la ON la.application_number = so.application_number
            WHERE la.recipient_status IN ('in_controller', 'between_controller_technician', 'in_technician')
              AND COALESCE(so.is_active, TRUE) = TRUE
            """
        )
        return dict(stats) if stats else {}
    finally:
        await conn.close()

async def list_active_orders_detailed(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Controller uchun aktiv orders ro'yxatini batafsil olish.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            WITH last_assign AS (
                SELECT DISTINCT ON (c.application_number)
                       c.application_number,
                       c.recipient_id,
                       c.recipient_status,
                       c.created_at as assigned_at
                FROM connections c
                WHERE c.application_number IS NOT NULL
                ORDER BY c.application_number, c.created_at DESC
            )
            SELECT 
                so.id,
                so.application_number,
                so.user_id,
                so.phone,
                so.abonent_id,
                so.region,
                so.address,
                so.tarif_id,
                so.description,
                so.business_type,
                so.type_of_zayavka,
                so.status,
                so.is_active,
                so.created_at,
                so.updated_at,
                la.assigned_at,
                u.full_name as client_name,
                u.phone as client_phone,
                t.name as tariff,
                INITCAP(REPLACE(so.region, '_', ' ')) AS region_name,
                creator.full_name as staff_name,
                creator.phone as staff_phone,
                creator.role as staff_role,
                CASE 
                    WHEN so.status = 'in_controller' THEN 'Controller da'
                    WHEN so.status = 'between_controller_technician' THEN 'Technician ga yuborilgan'
                    WHEN so.status = 'in_technician' THEN 'Technician da'
                    WHEN so.status = 'completed' THEN 'Bajarilgan'
                    WHEN so.status = 'cancelled' THEN 'Bekor qilingan'
                    ELSE so.status
                END as status_text
            FROM staff_orders so
            JOIN last_assign la ON la.application_number = so.application_number
            LEFT JOIN users u ON u.id = so.user_id
            LEFT JOIN tarif t ON t.id = so.tarif_id
            LEFT JOIN users creator ON creator.id = so.user_id
            WHERE la.recipient_status IN ('in_controller', 'between_controller_technician', 'in_technician')
              AND so.status IN ('in_controller', 'between_controller_technician', 'in_technician')
              AND COALESCE(so.is_active, TRUE) = TRUE
            ORDER BY so.created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def get_controller_workflow_history(order_id: int) -> Dict[str, Any]:
    """
    Controller uchun workflow history olish.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Order ma'lumotlarini olamiz
        order_info = await conn.fetchrow(
            """
            SELECT 
                so.id,
                so.application_number,
                so.user_id,
                so.phone,
                so.abonent_id,
                so.region,
                so.address,
                so.tarif_id,
                so.description,
                so.business_type,
                so.type_of_zayavka,
                so.status,
                so.is_active,
                so.created_at,
                so.updated_at,
                u.full_name as client_name,
                u.phone as client_phone,
                t.name as tariff,
                INITCAP(REPLACE(so.region, '_', ' ')) AS region_name
            FROM staff_orders so
            LEFT JOIN users u ON u.id = so.user_id
            LEFT JOIN tarif t ON t.id = so.tarif_id
            WHERE so.id = $1
            """,
            order_id
        )
        
        if not order_info:
            return {}
        
        # Workflow history olamiz - barcha order turlarini qo'llab-quvvatlaydi
        workflow = await conn.fetch(
            """
            SELECT 
                c.id,
                c.sender_id,
                c.recipient_id,
                c.sender_status,
                c.recipient_status,
                c.created_at,
                sender.full_name as sender_name,
                sender.role as sender_role,
                recipient.full_name as recipient_name,
                recipient.role as recipient_role,
                CASE 
                    'connection'
                END AS order_type
            FROM connections c
            LEFT JOIN users sender ON sender.id = c.sender_id
            LEFT JOIN users recipient ON recipient.id = c.recipient_id
                WHERE EXISTS (
                    SELECT 1 FROM connection_orders co WHERE co.application_number = c.application_number AND co.id = $1
                    UNION ALL
                    SELECT 1 FROM technician_orders to WHERE to.application_number = c.application_number AND to.id = $1
                    UNION ALL
                    SELECT 1 FROM staff_orders so WHERE so.application_number = c.application_number AND so.id = $1
                )
            ORDER BY c.created_at ASC
            """,
            order_id
        )
        
        return {
            "order": dict(order_info),
            "workflow": [dict(w) for w in workflow]
        }
    finally:
        await conn.close()

async def get_controller_technician_load() -> List[Dict[str, Any]]:
    """
    Controller uchun technician load monitoring.
    Counts ALL order types: connection_orders, technician_orders, and staff_orders.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            WITH connection_loads AS (
                -- Connection orders assigned to technician
                SELECT 
                    c.recipient_id AS technician_id,
                    COUNT(*) AS active_orders,
                    COUNT(CASE WHEN co.status = 'between_controller_technician' THEN 1 END) as pending_orders,
                    COUNT(CASE WHEN co.status = 'in_technician' THEN 1 END) as in_progress_orders,
                    COUNT(CASE WHEN co.status = 'in_technician_work' THEN 1 END) as in_work_orders
                FROM connections c
                JOIN connection_orders co ON co.application_number = c.application_number
                WHERE c.recipient_id IS NOT NULL
                  AND co.status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  AND co.is_active = TRUE
                  AND c.recipient_status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                GROUP BY c.recipient_id
            ),
            technician_loads AS (
                -- Technician orders assigned to technician
                SELECT 
                    c.recipient_id AS technician_id,
                    COUNT(*) AS active_orders,
                    COUNT(CASE WHEN to_orders.status = 'between_controller_technician' THEN 1 END) as pending_orders,
                    COUNT(CASE WHEN to_orders.status = 'in_technician' THEN 1 END) as in_progress_orders,
                    COUNT(CASE WHEN to_orders.status = 'in_technician_work' THEN 1 END) as in_work_orders
                FROM connections c
                JOIN technician_orders to_orders ON to_orders.application_number = c.application_number
                WHERE c.recipient_id IS NOT NULL
                  AND to_orders.status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  AND COALESCE(to_orders.is_active, TRUE) = TRUE
                  AND c.recipient_status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                GROUP BY c.recipient_id
            ),
            staff_loads AS (
                -- Staff orders assigned to technician
                SELECT 
                    c.recipient_id AS technician_id,
                    COUNT(*) AS active_orders,
                    COUNT(CASE WHEN so.status = 'between_controller_technician' THEN 1 END) as pending_orders,
                    COUNT(CASE WHEN so.status = 'in_technician' THEN 1 END) as in_progress_orders,
                    COUNT(CASE WHEN so.status = 'in_technician_work' THEN 1 END) as in_work_orders
                FROM connections c
                JOIN staff_orders so ON so.application_number = c.application_number
                WHERE c.recipient_id IS NOT NULL
                  AND so.status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  AND COALESCE(so.is_active, TRUE) = TRUE
                  AND c.recipient_status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                GROUP BY c.recipient_id
            ),
            total_loads AS (
                -- Combine all loads
                SELECT 
                    technician_id,
                    SUM(active_orders) AS total_active_orders,
                    SUM(pending_orders) AS total_pending_orders,
                    SUM(in_progress_orders) AS total_in_progress_orders,
                    SUM(in_work_orders) AS total_in_work_orders
                FROM (
                    SELECT technician_id, active_orders, pending_orders, in_progress_orders, in_work_orders FROM connection_loads
                    UNION ALL
                    SELECT technician_id, active_orders, pending_orders, in_progress_orders, in_work_orders FROM technician_loads
                    UNION ALL
                    SELECT technician_id, active_orders, pending_orders, in_progress_orders, in_work_orders FROM staff_loads
                ) combined
                GROUP BY technician_id
            )
            SELECT 
                u.id,
                u.full_name,
                u.phone,
                u.telegram_id,
                COALESCE(tl.total_active_orders, 0) as active_orders,
                COALESCE(tl.total_pending_orders, 0) as pending_orders,
                COALESCE(tl.total_in_progress_orders, 0) as in_progress_orders
            FROM users u
            LEFT JOIN total_loads tl ON tl.technician_id = u.id
            WHERE u.role = 'technician'
              AND COALESCE(u.is_blocked, FALSE) = FALSE
            ORDER BY active_orders DESC, u.full_name
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()
