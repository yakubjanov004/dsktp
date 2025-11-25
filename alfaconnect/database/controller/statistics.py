# database/controller/statistics.py

from typing import Dict, Any, List
import asyncpg
import logging
from config import settings

logger = logging.getLogger(__name__)

# =========================================================
#  Controller Statistics
# =========================================================

async def get_controller_statistics() -> Dict[str, Any]:
    """
    Controller uchun umumiy statistika olish.
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
                COUNT(*) as total_orders,
                COUNT(CASE WHEN so.status = 'in_controller' THEN 1 END) as in_controller,
                COUNT(CASE WHEN so.status = 'between_controller_technician' THEN 1 END) as between_controller_technician,
                COUNT(CASE WHEN so.status = 'in_technician' THEN 1 END) as in_technician,
                COUNT(CASE WHEN so.status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN so.status = 'cancelled' THEN 1 END) as cancelled,
                COUNT(CASE WHEN so.type_of_zayavka = 'connection' THEN 1 END) as connection_orders,
                COUNT(CASE WHEN so.type_of_zayavka = 'technician' THEN 1 END) as technician_orders
            FROM staff_orders so
            JOIN last_assign la ON la.application_number = so.application_number
            WHERE la.recipient_status IN ('in_controller', 'between_controller_technician', 'in_technician')
              AND COALESCE(so.is_active, TRUE) = TRUE
            """
        )
        return dict(stats) if stats else {}
    finally:
        await conn.close()

async def get_controller_daily_statistics(days: int = 7) -> List[Dict[str, Any]]:
    """
    Controller uchun kunlik statistika olish.
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
                       c.created_at
                FROM connections c
                WHERE c.application_number IS NOT NULL
                ORDER BY c.application_number, c.created_at DESC
            )
            SELECT 
                DATE(so.created_at) as date,
                COUNT(*) as total_orders,
                COUNT(CASE WHEN so.status = 'completed' THEN 1 END) as completed_orders,
                COUNT(CASE WHEN so.status = 'cancelled' THEN 1 END) as cancelled_orders,
                COUNT(CASE WHEN so.type_of_zayavka = 'connection' THEN 1 END) as connection_orders,
                COUNT(CASE WHEN so.type_of_zayavka = 'technician' THEN 1 END) as technician_orders
            FROM staff_orders so
            JOIN last_assign la ON la.application_number = so.application_number
            WHERE la.recipient_status IN ('in_controller', 'between_controller_technician', 'in_technician')
              AND COALESCE(so.is_active, TRUE) = TRUE
              AND so.created_at >= NOW() - INTERVAL '%s days'
            GROUP BY DATE(so.created_at)
            ORDER BY date DESC
            """,
            days
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def get_controller_technician_performance() -> List[Dict[str, Any]]:
    """
    Controller uchun technician performance statistika.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
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
                u.id as technician_id,
                u.full_name as technician_name,
                u.phone as technician_phone,
                COUNT(so.id) as total_orders,
                COUNT(CASE WHEN so.status = 'completed' THEN 1 END) as completed_orders,
                COUNT(CASE WHEN so.status = 'cancelled' THEN 1 END) as cancelled_orders,
                COUNT(CASE WHEN so.status IN ('between_controller_technician', 'in_technician') THEN 1 END) as active_orders,
                AVG(CASE WHEN so.status = 'completed' THEN 
                    EXTRACT(EPOCH FROM (so.updated_at - so.created_at))/3600 
                END) as avg_completion_hours
            FROM users u
            LEFT JOIN last_assign la ON la.recipient_id = u.id
            LEFT JOIN staff_orders so ON so.application_number = la.application_number
            WHERE u.role = 'technician'
              AND COALESCE(u.is_blocked, FALSE) = FALSE
            GROUP BY u.id, u.full_name, u.phone
            ORDER BY total_orders DESC, u.full_name
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def get_controller_order_types_statistics() -> Dict[str, Any]:
    """
    Controller uchun order types bo'yicha statistika.
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
                COUNT(CASE WHEN so.type_of_zayavka = 'connection' THEN 1 END) as connection_orders,
                COUNT(CASE WHEN so.type_of_zayavka = 'technician' THEN 1 END) as technician_orders,
                COUNT(CASE WHEN so.business_type = 'B2C' THEN 1 END) as b2c_orders,
                COUNT(CASE WHEN so.business_type = 'B2B' THEN 1 END) as b2b_orders,
                COUNT(CASE WHEN so.status = 'completed' AND so.type_of_zayavka = 'connection' THEN 1 END) as completed_connections,
                COUNT(CASE WHEN so.status = 'completed' AND so.type_of_zayavka = 'technician' THEN 1 END) as completed_technician
            FROM staff_orders so
            JOIN last_assign la ON la.application_number = so.application_number
            WHERE la.recipient_status IN ('in_controller', 'between_controller_technician', 'in_technician')
              AND COALESCE(so.is_active, TRUE) = TRUE
            """
        )
        return dict(stats) if stats else {}
    finally:
        await conn.close()

# =========================================================
#  Individual Count Functions for Controller Orders Handler
# =========================================================

async def ctrl_total_tech_orders_count() -> int:
    """
    Controller uchun jami aktiv buyurtmalar soni.
    Barcha 3 xil order type: connection_orders, technician_orders, va staff_orders.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval(
            """
            SELECT 
                (SELECT COUNT(*) FROM technician_orders WHERE COALESCE(is_active, TRUE) = TRUE AND status IN ('in_controller','between_controller_technician','in_technician','in_technician_work','in_repairs','in_warehouse','completed')) +
                (SELECT COUNT(*) FROM staff_orders WHERE type_of_zayavka = 'technician' AND COALESCE(is_active, TRUE) = TRUE AND status IN ('in_controller','between_controller_technician','in_technician','in_technician_work','in_repairs','in_warehouse','completed')) +
                (SELECT COUNT(*) FROM connection_orders WHERE COALESCE(is_active, TRUE) = TRUE AND status IN ('in_controller','between_controller_technician','in_technician','completed'))
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def ctrl_new_in_controller_count() -> int:
    """
    Controller uchun yangi kelgan buyurtmalar soni.
    Barcha 3 xil order type: connection_orders, technician_orders, va staff_orders.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval(
            """
            SELECT 
                (SELECT COUNT(*) FROM technician_orders WHERE status = 'in_controller' AND COALESCE(is_active, TRUE) = TRUE) +
                (SELECT COUNT(*) FROM staff_orders WHERE status = 'in_controller' AND type_of_zayavka = 'technician' AND COALESCE(is_active, TRUE) = TRUE) +
                (SELECT COUNT(*) FROM connection_orders WHERE status = 'in_controller' AND COALESCE(is_active, TRUE) = TRUE)
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def ctrl_in_progress_count() -> int:
    """
    Controller uchun jarayondagi buyurtmalar soni.
    Barcha 3 xil order type: connection_orders, technician_orders, va staff_orders.
    Excludes completed and cancelled orders.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval(
            """
            SELECT 
                (SELECT COUNT(*) FROM technician_orders WHERE status IN ('between_controller_technician', 'in_technician', 'in_technician_work', 'in_repairs', 'in_warehouse') AND COALESCE(is_active, TRUE) = TRUE) +
                (SELECT COUNT(*) FROM staff_orders WHERE status IN ('between_controller_technician', 'in_technician', 'in_technician_work', 'in_repairs', 'in_warehouse') AND type_of_zayavka = 'technician' AND COALESCE(is_active, TRUE) = TRUE) +
                (SELECT COUNT(*) FROM connection_orders WHERE status IN ('between_controller_technician','in_technician') AND COALESCE(is_active, TRUE) = TRUE)
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def ctrl_completed_today_count() -> int:
    """
    Controller uchun bugun bajarilgan buyurtmalar soni.
    Barcha 3 xil order type: connection_orders, technician_orders, va staff_orders.
    Only orders completed today, excludes cancelled orders.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval(
            """
            SELECT 
                (SELECT COUNT(*) FROM technician_orders WHERE status = 'completed' AND DATE(updated_at) = CURRENT_DATE AND COALESCE(is_active, TRUE) = TRUE) +
                (SELECT COUNT(*) FROM staff_orders WHERE status = 'completed' AND DATE(updated_at) = CURRENT_DATE AND type_of_zayavka = 'technician' AND COALESCE(is_active, TRUE) = TRUE) +
                (SELECT COUNT(*) FROM connection_orders WHERE status = 'completed' AND DATE(updated_at) = CURRENT_DATE AND COALESCE(is_active, TRUE) = TRUE)
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def ctrl_cancelled_count() -> int:
    """
    Controller uchun bekor qilingan buyurtmalar soni.
    """
    # Neither technician_orders nor connection_orders support cancelled status
    # Only staff_orders has cancelled status, but controller doesn't handle staff_orders
    return 0

# =========================================================
#  Controller Orders List Functions
# =========================================================

async def ctrl_get_new_orders(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Controller uchun yangi kelgan buyurtmalar ro'yxati.
    Barcha 3 xil order type: connection_orders, technician_orders, va staff_orders.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            -- Client yaratgan technician orders
            SELECT 
                to_orders.id,
                to_orders.application_number,
                to_orders.user_id,
                to_orders.abonent_id,
                to_orders.region,
                to_orders.address,
                NULL as tarif_id,
                to_orders.description,
                to_orders.business_type,
                'technician' as type_of_zayavka,
                to_orders.status::text,
                to_orders.created_at,
                to_orders.updated_at,
                u.full_name as client_name,
                u.phone as client_phone,
                NULL as tariff,
                NULL as media_file_id,
                NULL as media_type
            FROM technician_orders to_orders
            LEFT JOIN users u ON u.id = to_orders.user_id
            WHERE to_orders.status::text = 'in_controller'
              AND COALESCE(to_orders.is_active, TRUE) = TRUE
            
            UNION ALL
            
            -- Staff yaratgan technician orders (staff_orders with type_of_zayavka='technician')
            SELECT 
                so.id,
                so.application_number,
                so.user_id,
                so.abonent_id,
                so.region,
                so.address,
                so.tarif_id,
                so.description,
                so.business_type,
                so.type_of_zayavka,
                so.status::text,
                so.created_at,
                so.updated_at,
                COALESCE(client_user.full_name, 'Mijoz') as client_name,
                COALESCE(client_user.phone, so.phone) as client_phone,
                t.name as tariff,
                NULL as media_file_id,
                NULL as media_type
            FROM staff_orders so
            LEFT JOIN users client_user ON client_user.id::text = so.abonent_id
            LEFT JOIN tarif t ON t.id = so.tarif_id
            WHERE so.status::text = 'in_controller'
              AND so.type_of_zayavka = 'technician'
              AND COALESCE(so.is_active, TRUE) = TRUE
            
            UNION ALL
            
            -- Connection orders (ulanish arizalari) JM dan kelganlar
            SELECT
                co.id,
                co.application_number,
                co.user_id,
                NULL as abonent_id,
                co.region,
                co.address,
                co.tarif_id,
                NULL as description,
                'B2C' as business_type,
                'connection' as type_of_zayavka,
                co.status::text,
                co.created_at,
                co.updated_at,
                u_co.full_name as client_name,
                u_co.phone as client_phone,
                t.name as tariff,
                NULL as media_file_id,
                NULL as media_type
            FROM connection_orders co
            LEFT JOIN users u_co ON u_co.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            WHERE co.status::text = 'in_controller'
              AND COALESCE(co.is_active, TRUE) = TRUE
            
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def ctrl_get_in_progress_orders(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Controller uchun jarayondagi buyurtmalar ro'yxati.
    Both technician_orders (client-created) and staff_orders with type_of_zayavka='technician' (staff-created).
    Excludes completed and cancelled orders.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            -- Client yaratgan technician orders
            SELECT 
                to_orders.id,
                to_orders.application_number,
                to_orders.user_id,
                to_orders.abonent_id,
                to_orders.region,
                to_orders.address,
                NULL as tarif_id,
                to_orders.description,
                to_orders.business_type,
                'technician' as type_of_zayavka,
                to_orders.status::text,
                to_orders.created_at,
                to_orders.updated_at,
                u.full_name as client_name,
                u.phone as client_phone,
                NULL as tariff,
                NULL as technician_name,
                NULL as technician_phone,
                NULL as media_file_id,
                NULL as media_type
            FROM technician_orders to_orders
            LEFT JOIN users u ON u.id = to_orders.user_id
            WHERE to_orders.status::text IN ('between_controller_technician', 'in_technician', 'in_technician_work', 'in_repairs', 'in_warehouse')
              AND COALESCE(to_orders.is_active, TRUE) = TRUE
            
            UNION ALL
            
            -- Staff yaratgan technician orders (staff_orders with type_of_zayavka='technician')
            SELECT 
                so.id,
                so.application_number,
                so.user_id,
                so.abonent_id,
                so.region,
                so.address,
                so.tarif_id,
                so.description,
                so.business_type,
                so.type_of_zayavka,
                so.status::text,
                so.created_at,
                so.updated_at,
                COALESCE(client_user.full_name, 'Mijoz') as client_name,
                COALESCE(client_user.phone, so.phone) as client_phone,
                t.name as tariff,
                NULL as technician_name,
                NULL as technician_phone,
                NULL as media_file_id,
                NULL as media_type
            FROM staff_orders so
            LEFT JOIN users client_user ON client_user.id::text = so.abonent_id
            LEFT JOIN tarif t ON t.id = so.tarif_id
            WHERE so.status::text IN ('between_controller_technician', 'in_technician', 'in_technician_work', 'in_repairs', 'in_warehouse')
              AND so.type_of_zayavka = 'technician'
              AND COALESCE(so.is_active, TRUE) = TRUE
            
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def ctrl_get_completed_today_orders(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Controller uchun bugun bajarilgan buyurtmalar ro'yxati.
    Both technician_orders (client-created) and staff_orders with type_of_zayavka='technician' (staff-created).
    Only orders completed today, excludes cancelled orders.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            -- Client yaratgan technician orders
            SELECT 
                to_orders.id,
                to_orders.application_number,
                to_orders.user_id,
                to_orders.abonent_id,
                to_orders.region,
                to_orders.address,
                NULL as tarif_id,
                to_orders.description,
                to_orders.business_type,
                'technician' as type_of_zayavka,
                to_orders.status::text,
                to_orders.created_at,
                to_orders.updated_at,
                u.full_name as client_name,
                u.phone as client_phone,
                NULL as tariff,
                NULL as technician_name,
                NULL as technician_phone,
                NULL as media_file_id,
                NULL as media_type
            FROM technician_orders to_orders
            LEFT JOIN users u ON u.id = to_orders.user_id
            WHERE to_orders.status::text = 'completed'
              AND DATE(to_orders.updated_at) = CURRENT_DATE
              AND COALESCE(to_orders.is_active, TRUE) = TRUE
            
            UNION ALL
            
            -- Staff yaratgan technician orders (staff_orders with type_of_zayavka='technician')
            SELECT 
                so.id,
                so.application_number,
                so.user_id,
                so.abonent_id,
                so.region,
                so.address,
                so.tarif_id,
                so.description,
                so.business_type,
                so.type_of_zayavka,
                so.status::text,
                so.created_at,
                so.updated_at,
                COALESCE(client_user.full_name, 'Mijoz') as client_name,
                COALESCE(client_user.phone, so.phone) as client_phone,
                t.name as tariff,
                NULL as technician_name,
                NULL as technician_phone,
                NULL as media_file_id,
                NULL as media_type
            FROM staff_orders so
            LEFT JOIN users client_user ON client_user.id::text = so.abonent_id
            LEFT JOIN tarif t ON t.id = so.tarif_id
            WHERE so.status::text = 'completed'
              AND DATE(so.updated_at) = CURRENT_DATE
              AND so.type_of_zayavka = 'technician'
              AND COALESCE(so.is_active, TRUE) = TRUE
            
            ORDER BY updated_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def ctrl_get_cancelled_orders(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Controller uchun bekor qilingan buyurtmalar ro'yxati.
    """
    # Neither technician_orders nor connection_orders support cancelled status
    # Only staff_orders has cancelled status, but controller doesn't handle staff_orders
    return []

async def ctrl_get_order_media(order_id: int, order_type: str) -> List[Dict[str, Any]]:
    """
    Ariza uchun media fayllarni olish.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if order_type == 'technician':
            # Technician orders uchun media ustunidan olamiz
            row = await conn.fetchrow(
                """
                SELECT 
                    media,
                    created_at
                FROM technician_orders
                WHERE id = $1
                """,
                order_id
            )
            
            if row and row['media']:
                # Media file_id ni file_path sifatida qaytaramiz
                return [{
                    'id': order_id,
                    'file_path': row['media'],  # Bu Telegram file_id
                    'file_type': 'photo',
                    'original_name': f'technician_order_{order_id}.jpg',
                    'mime_type': 'image/jpeg',
                    'file_size': 0,
                    'created_at': row['created_at']
                }]
            else:
                return []
                
        elif order_type == 'connection':
            # Connection orders uchun media_files jadvalidan olamiz
            rows = await conn.fetch(
                """
                SELECT 
                    mf.id,
                    mf.file_path,
                    mf.file_type,
                    mf.original_name,
                    mf.mime_type,
                    mf.file_size,
                    mf.created_at
                FROM media_files mf
                WHERE mf.related_table = 'connection_orders'
                  AND mf.related_id = $1
                  AND mf.is_active = TRUE
                ORDER BY mf.created_at DESC
                """,
                order_id
            )
            return [dict(r) for r in rows]
        else:
            return []
    finally:
        await conn.close()