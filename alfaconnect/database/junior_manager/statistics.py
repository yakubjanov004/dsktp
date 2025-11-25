# database/junior_manager/statistics.py
# Junior Manager roli uchun statistika queries

import asyncpg
from typing import Dict, Any
from config import settings

async def get_jm_stats_for_telegram(telegram_id: int) -> Dict[str, Any]:
    """
    Junior Manager uchun statistika ma'lumotlari.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Junior Manager ID va ismini olish
        user_row = await conn.fetchrow(
            "SELECT id, full_name FROM users WHERE telegram_id = $1 AND role = 'junior_manager'",
            telegram_id
        )
        
        if not user_row:
            return {
                "total_orders": 0,
                "new_orders": 0,
                "in_progress_orders": 0,
                "completed_orders": 0,
                "today_completed": 0,
                "manager_name": "Noma'lum"
            }
        
        jm_id = user_row["id"]
        manager_name = user_row["full_name"] or "Noma'lum"
        
        # Umumiy statistika - connection_orders va staff_orders biriktirilgan arizalar
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE order_type = 'connection' AND status = 'in_junior_manager') AS new_orders,
                COUNT(*) FILTER (WHERE order_type = 'connection' AND status IN ('in_controller', 'in_technician', 'in_technician_work', 'in_manager', 'between_controller_technician')) AS in_progress_orders,
                COUNT(*) FILTER (WHERE order_type = 'connection' AND status = 'completed') AS completed_orders,
                COUNT(*) FILTER (WHERE order_type = 'connection' AND status = 'completed' AND DATE(updated_at) = CURRENT_DATE) AS today_completed,
                COUNT(*) AS total_orders
            FROM (
                -- Connection Orders (mijozlar arizalari)
                SELECT
                    'connection' as order_type,
                    co.status::text as status,
                    co.updated_at
                FROM connections c
                JOIN connection_orders co ON co.application_number = c.application_number
                WHERE c.recipient_id = $1
                  AND c.application_number IS NOT NULL
                  AND co.is_active = TRUE
                  AND c.recipient_status = 'in_junior_manager'
                
                UNION ALL
                
                -- Staff Orders (xodimlar arizalari)
                SELECT
                    'staff' as order_type,
                    so.status::text as status,
                    so.updated_at
                FROM connections c
                JOIN staff_orders so ON so.application_number = c.application_number
                WHERE c.recipient_id = $1
                  AND c.application_number IS NOT NULL
                  AND so.is_active = TRUE
                  AND c.recipient_status = 'in_junior_manager'
            ) combined_orders
            """,
            jm_id
        )
        
        return {
            "total_orders": int(stats["total_orders"] or 0),
            "new_orders": int(stats["new_orders"] or 0),
            "in_progress_orders": int(stats["in_progress_orders"] or 0),
            "completed_orders": int(stats["completed_orders"] or 0),
            "today_completed": int(stats["today_completed"] or 0),
            "manager_name": manager_name
        }
    finally:
        await conn.close()

async def get_jm_performance_stats(telegram_id: int, days: int = 30) -> Dict[str, Any]:
    """
    Junior Manager ishlash ko'rsatkichlari.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Junior Manager ID ni olish
        user_row = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1 AND role = 'junior_manager'",
            telegram_id
        )
        
        if not user_row:
            return {
                "orders_processed": 0,
                "avg_processing_time": 0,
                "completion_rate": 0
            }
        
        jm_id = user_row["id"]
        
        # Oxirgi N kunlik statistika - faqat o'ziga biriktirilgan arizalar
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS orders_processed,
                AVG(EXTRACT(EPOCH FROM (so.updated_at - so.created_at))/3600) AS avg_processing_hours,
                COUNT(*) FILTER (WHERE so.status = 'completed') * 100.0 / COUNT(*) AS completion_rate
            FROM connections c
            JOIN staff_orders so ON so.application_number = c.application_number
            WHERE c.recipient_id = $1
              AND so.is_active = TRUE
              AND so.created_at >= NOW() - INTERVAL '%s days'
            """,
            jm_id, days
        )
        
        return {
            "orders_processed": int(stats["orders_processed"] or 0),
            "avg_processing_time": float(stats["avg_processing_hours"] or 0),
            "completion_rate": float(stats["completion_rate"] or 0)
        }
    finally:
        await conn.close()
