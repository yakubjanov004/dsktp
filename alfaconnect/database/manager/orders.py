import asyncpg
import re
from typing import List, Dict, Any, Optional, Union
from config import settings

from database.basic.user import ensure_user
from database.basic.tariff import get_or_create_tarif_by_code
from database.basic.phone import normalize_phone
from database.basic.region import normalize_region_code

async def ensure_user_manager(telegram_id: int, full_name: str, username: str) -> Dict[str, Any]:
    """
    Manager uchun user yaratish/yangilash.
    """
    return await ensure_user(telegram_id, full_name, username, 'manager')

async def staff_orders_create(
    user_id: int,
    phone: Optional[str],
    abonent_id: Optional[str],
    region: Optional[Union[int, str]],
    address: str,
    tarif_id: Optional[int],
    business_type: str = "B2C",
    created_by_role: str = "manager",
) -> int:
    """
    Manager TOMONIDAN ulanish arizasini yaratish.
    Default status: 'in_controller'.
    Connections jadvaliga ham yozuv qo'shadi.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        async with conn.transaction():
            next_number = await conn.fetchval(
                "SELECT COALESCE(MAX(CAST(SUBSTRING(application_number FROM '\\d+$') AS INTEGER)), 0) + 1 FROM staff_orders WHERE application_number LIKE $1",
                f"STAFF-CONN-{business_type}-%"
            )
            application_number = f"STAFF-CONN-{business_type}-{next_number:04d}"

            normalized_region = normalize_region_code(region) or (str(region).strip() if region is not None else None)
            normalized_phone = normalize_phone(phone) if phone else None

            row = await conn.fetchrow(
                """
                INSERT INTO staff_orders (
                    application_number, user_id, phone, abonent_id, region, address, tarif_id,
                    description, business_type, type_of_zayavka, status, is_active, created_by_role, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7,
                        '', $8, 'connection', 'in_controller'::staff_order_status, TRUE, $9, NOW(), NOW())
                RETURNING id, application_number
                """,
                application_number,
                user_id,
                normalized_phone,
                abonent_id,
                normalized_region,
                address,
                tarif_id,
                business_type,
                created_by_role,
            )

            staff_order_id = row["id"]
            app_number = row["application_number"]
            await conn.execute(
                """
                INSERT INTO connections (
                    application_number,
                    sender_id,
                    recipient_id,
                    sender_status,
                    recipient_status,
                    created_at,
                    updated_at
                )
                VALUES ($1, $2, $2, 'new', 'in_controller', NOW(), NOW())
                """,
                app_number, user_id
            )
            return {"id": staff_order_id, "application_number": row["application_number"]}
    finally:
        await conn.close()

async def staff_orders_technician_create(
    user_id: int,
    phone: Optional[str],
    abonent_id: Optional[str],
    region: Optional[Union[int, str]],
    address: str,
    description: Optional[str],
    business_type: str = "B2C",
    created_by_role: str = "manager",
) -> int:
    """
    Manager TOMONIDAN texnik xizmat arizasini yaratish.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        async with conn.transaction():
            next_number = await conn.fetchval(
                "SELECT COALESCE(MAX(CAST(SUBSTRING(application_number FROM '\\d+$') AS INTEGER)), 0) + 1 FROM staff_orders WHERE application_number LIKE $1",
                f"STAFF-TECH-{business_type}-%"
            )
            application_number = f"STAFF-TECH-{business_type}-{next_number:04d}"

            normalized_region = normalize_region_code(region) or (str(region).strip() if region is not None else None)
            normalized_phone = normalize_phone(phone) if phone else None

            row = await conn.fetchrow(
                """
                INSERT INTO staff_orders (
                    application_number, user_id, phone, abonent_id, region, address,
                    description, business_type, type_of_zayavka, status, is_active, created_by_role, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'technician', 'in_controller'::staff_order_status, TRUE, $9, NOW(), NOW())
                RETURNING id, application_number
                """,
                application_number,
                user_id,
                normalized_phone,
                abonent_id,
                normalized_region,
                address,
                description,
                business_type,
                created_by_role,
            )
            return {"id": row["id"], "application_number": row["application_number"]}
    finally:
        await conn.close()

# =========================================================
#  Manager Orders ro'yxatlari
# =========================================================

async def fetch_manager_orders(user_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Manager yaratgan arizalarni olish.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT
                so.id,
                so.application_number,
                so.address,
                so.region,
                so.status,
                so.type_of_zayavka,
                so.description,
                so.created_at,
                so.updated_at,
                u.full_name AS client_name,
                u.phone AS client_phone,
                t.name AS tariff
            FROM staff_orders so
            LEFT JOIN users u ON u.id = so.abonent_id::bigint
            LEFT JOIN tarif t ON t.id = so.tarif_id::bigint
            WHERE so.user_id = $1
              AND COALESCE(so.is_active, TRUE) = TRUE
            ORDER BY so.created_at DESC, so.id DESC
            LIMIT $2 OFFSET $3
            """,
            user_id, limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def count_manager_orders(user_id: int) -> int:
    """
    Manager yaratgan arizalar soni.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
              FROM staff_orders so
             WHERE so.user_id = $1
               AND COALESCE(so.is_active, TRUE) = TRUE
            """,
            user_id
        )
    finally:
        await conn.close()

# =========================================================
#  Manager Statistics funksiyalari
# =========================================================

async def get_all_total_connection_orders_count() -> int:
    """Barcha faol ulanish arizalarining umumiy sonini qaytaradi (mijozlar va xodimlar ochgan)."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        total_count = await conn.fetchval(
            """
            SELECT 
                (SELECT COUNT(*) FROM connection_orders WHERE is_active = TRUE)
                +
                (SELECT COUNT(*) FROM staff_orders WHERE is_active = TRUE AND type_of_zayavka = 'connection')
            """
        )
        return total_count if total_count is not None else 0
    finally:
        await conn.close()

async def get_total_orders_count(user_id: int) -> int:
    """Manager yaratgan jami arizalar soni."""
    return await count_manager_orders(user_id)

async def get_in_progress_count(user_id: int) -> int:
    """Manager yaratgan ish jarayonidagi arizalar soni."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
              FROM staff_orders so
             WHERE so.user_id = $1
               AND COALESCE(so.is_active, TRUE) = TRUE
               AND so.status IN ('in_junior_manager', 'in_controller', 'in_technician')
            """,
            user_id
        )
    finally:
        await conn.close()

async def get_completed_today_count(user_id: int) -> int:
    """Manager yaratgan bugun yakunlangan arizalar soni."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
              FROM staff_orders so
             WHERE so.user_id = $1
               AND COALESCE(so.is_active, TRUE) = TRUE
               AND so.status = 'completed'
               AND DATE(so.updated_at) = CURRENT_DATE
            """,
            user_id
        )
    finally:
        await conn.close()

async def get_cancelled_count(user_id: int) -> int:
    """Manager yaratgan bekor qilingan arizalar soni."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
              FROM staff_orders so
             WHERE so.user_id = $1
               AND COALESCE(so.is_active, TRUE) = TRUE
               AND so.status = 'cancelled'
            """,
            user_id
        )
    finally:
        await conn.close()

async def get_all_cancelled_count() -> int:
    """Barcha bekor qilingan ulanish arizalari soni (client va xodim yaratgani)."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        total_count = await conn.fetchval(
            """
            SELECT 
                (SELECT COUNT(*) FROM connection_orders WHERE is_active = TRUE AND status = 'cancelled')
                +
                (SELECT COUNT(*) FROM staff_orders WHERE is_active = TRUE AND status = 'cancelled' AND type_of_zayavka = 'connection')
            """
        )
        return total_count if total_count is not None else 0
    finally:
        await conn.close()

async def get_all_new_orders_count() -> int:
    """Barcha manager'ga kelgan yangi arizalar soni (mijozlar va xodimlar ochgani)."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        total_count = await conn.fetchval(
            """
            SELECT 
                (SELECT COUNT(*) FROM connection_orders WHERE is_active = TRUE AND status = 'in_manager')
                +
                (SELECT COUNT(*) FROM staff_orders WHERE is_active = TRUE AND status = 'in_manager' AND type_of_zayavka = 'connection')
            """
        )
        return total_count if total_count is not None else 0
    finally:
        await conn.close()

async def get_new_orders_today_count(user_id: int) -> int:
    """Manager yaratgan bugungi yangi arizalar soni."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
              FROM staff_orders so
             WHERE so.user_id = $1
               AND COALESCE(so.is_active, TRUE) = TRUE
               AND so.status = 'in_manager'
               AND DATE(so.created_at) = CURRENT_DATE
            """,
            user_id
        )
    finally:
        await conn.close()

# =========================================================
#  Manager Orders ro'yxatlari
# =========================================================

async def list_new_orders(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Barcha yangi ulanish arizalari (client va xodim yaratgani)."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Client arizalari va staff arizalarini birlashtiramiz
        rows = await conn.fetch(
            """
            (
                -- Client arizalari
                SELECT
                    co.id,
                    co.application_number,
                    co.address,
                    co.status::text,
                    'connection' as type_of_zayavka,
                    co.created_at,
                    co.updated_at,
                    u.full_name AS client_name,
                    u.phone AS client_phone,
                    t.name AS tariff,
                    'client' as source_type
                FROM connection_orders co
                LEFT JOIN users u ON u.id = co.user_id
                LEFT JOIN tarif t ON t.id = co.tarif_id
                WHERE co.is_active = TRUE 
                  AND co.status = 'in_manager'
            )
            UNION ALL
            (
                -- Staff arizalari (xodimlar yaratgani)
                SELECT
                    so.id,
                    so.application_number,
                    so.address,
                    so.status::text,
                    so.type_of_zayavka,
                    so.created_at,
                    so.updated_at,
                    u.full_name AS client_name,
                    u.phone AS client_phone,
                    t.name AS tariff,
                    'staff' as source_type
                FROM staff_orders so
                LEFT JOIN users u ON u.id = so.abonent_id::bigint
                LEFT JOIN tarif t ON t.id = so.tarif_id
                WHERE so.is_active = TRUE 
                  AND so.status = 'in_manager'
                  AND so.type_of_zayavka = 'connection'
            )
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def list_all_in_progress_orders(limit: int = 50) -> List[Dict[str, Any]]:
    """Barcha jarayondagi ulanish arizalari - mijozlar va xodimlar ochgani."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT
                co.id,
                co.application_number,
                co.address,
                co.status::text,
                co.created_at,
                co.updated_at,
                u.full_name AS client_name,
                u.phone AS client_phone,
                t.name AS tariff,
                'connection' as type_of_zayavka,
                'client' as order_source
            FROM connection_orders co
            LEFT JOIN users u ON u.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            WHERE co.is_active = TRUE
              AND co.status NOT IN ('cancelled', 'completed')
            
            UNION ALL
            
            SELECT
                so.id,
                so.application_number,
                so.address,
                so.status::text,
                so.created_at,
                so.updated_at,
                u.full_name AS client_name,
                u.phone AS client_phone,
                t.name AS tariff,
                so.type_of_zayavka,
                'staff' as order_source
            FROM staff_orders so
            LEFT JOIN users u ON u.id = so.abonent_id::bigint
            LEFT JOIN tarif t ON t.id = so.tarif_id
            WHERE so.is_active = TRUE
              AND so.status NOT IN ('cancelled', 'completed')
              AND so.type_of_zayavka = 'connection'
            
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def get_all_in_progress_count() -> int:
    """Barcha jarayondagi ulanish arizalari soni."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval(
            """
            SELECT 
                (SELECT COUNT(*) FROM connection_orders WHERE is_active = TRUE AND status NOT IN ('cancelled', 'completed'))
                +
                (SELECT COUNT(*) FROM staff_orders WHERE is_active = TRUE AND status NOT IN ('cancelled', 'completed') AND type_of_zayavka = 'connection')
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def list_completed_today_orders(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Manager yaratgan bugun yakunlangan arizalar."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT
                so.id,
                so.application_number,
                so.address,
                so.status,
                so.type_of_zayavka,
                so.created_at,
                so.updated_at,
                u.full_name AS client_name,
                u.phone AS client_phone,
                t.name AS tariff
            FROM staff_orders so
            LEFT JOIN users u ON u.id = so.abonent_id::bigint
            LEFT JOIN tarif t ON t.id = so.tarif_id
            WHERE so.user_id = $1
              AND COALESCE(so.is_active, TRUE) = TRUE
              AND so.status = 'completed'
              AND DATE(so.updated_at) = CURRENT_DATE
            ORDER BY so.updated_at DESC
            LIMIT $2
            """,
            user_id, limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def list_cancelled_orders(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Manager yaratgan bekor qilingan arizalar."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT
                so.id,
                so.application_number,
                so.address,
                so.status,
                so.type_of_zayavka,
                so.created_at,
                so.updated_at,
                u.full_name AS client_name,
                u.phone AS client_phone,
                t.name AS tariff
            FROM staff_orders so
            LEFT JOIN users u ON u.id = so.abonent_id::bigint
            LEFT JOIN tarif t ON t.id = so.tarif_id
            WHERE so.user_id = $1
              AND COALESCE(so.is_active, TRUE) = TRUE
              AND so.status = 'cancelled'
            ORDER BY so.updated_at DESC
            LIMIT $2
            """,
            user_id, limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def list_my_created_orders_by_type(user_id: int, order_type: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Manager yaratgan arizalar turi bo'yicha."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT
                so.id,
                so.application_number,
                so.address,
                so.status,
                so.type_of_zayavka,
                so.created_at,
                so.updated_at,
                u.full_name AS client_name,
                u.phone AS client_phone,
                t.name AS tariff
            FROM staff_orders so
            LEFT JOIN users u ON u.id = so.abonent_id::bigint
            LEFT JOIN tarif t ON t.id = so.tarif_id
            WHERE so.user_id = $1
              AND COALESCE(so.is_active, TRUE) = TRUE
              AND so.type_of_zayavka = $2
            ORDER BY so.created_at DESC
            LIMIT $3
            """,
            user_id, order_type, limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# =========================================================
#  Connection Orders uchun funksiyalar (Manager applications uchun)
# =========================================================

async def get_connection_orders_count() -> int:
    """Barcha connection orders soni."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM connection_orders WHERE is_active = TRUE")
        return int(count or 0)
    finally:
        await conn.close()

async def get_connection_orders_in_progress_count() -> int:
    """Jarayondagi connection orders soni."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM connection_orders WHERE is_active = TRUE AND status IN ('in_junior_manager', 'in_controller', 'in_technician', 'in_warehouse', 'in_repairs', 'in_technician_work')"
        )
        return int(count or 0)
    finally:
        await conn.close()

async def get_connection_orders_completed_today_count() -> int:
    """Bugun bajarilgan connection orders soni."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM connection_orders WHERE is_active = TRUE AND status = 'completed' AND DATE(updated_at) = CURRENT_DATE"
        )
        return int(count or 0)
    finally:
        await conn.close()

async def get_connection_orders_cancelled_count() -> int:
    """Bekor qilingan connection orders soni."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM connection_orders WHERE is_active = FALSE"
        )
        return int(count or 0)
    finally:
        await conn.close()

async def get_connection_orders_new_today_count() -> int:
    """Bugun yaratilgan connection orders soni."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM connection_orders WHERE is_active = TRUE AND status = 'in_manager' AND DATE(created_at) = CURRENT_DATE"
        )
        return int(count or 0)
    finally:
        await conn.close()

async def list_connection_orders_new(limit: int = 10) -> List[Dict[str, Any]]:
    """Yangi connection orders."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT
                co.id,
                co.application_number,
                co.address,
                co.status,
                co.created_at,
                co.updated_at,
                u.full_name AS client_name,
                u.phone AS client_phone,
                t.name AS tariff
            FROM connection_orders co
            LEFT JOIN users u ON u.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            WHERE co.is_active = TRUE
              AND co.status = 'in_manager'
            ORDER BY co.created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def list_connection_orders_in_progress(limit: int = 10) -> List[Dict[str, Any]]:
    """Jarayondagi connection orders."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT
                co.id,
                co.application_number,
                co.address,
                co.status,
                co.created_at,
                co.updated_at,
                u.full_name AS client_name,
                u.phone AS client_phone,
                t.name AS tariff
            FROM connection_orders co
            LEFT JOIN users u ON u.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            WHERE co.is_active = TRUE
              AND co.status IN ('in_junior_manager', 'in_controller', 'in_technician', 'in_warehouse', 'in_repairs', 'in_technician_work')
            ORDER BY co.created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def list_connection_orders_completed_today(limit: int = 10) -> List[Dict[str, Any]]:
    """Bugun bajarilgan connection orders."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT
                co.id,
                co.application_number,
                co.address,
                co.status,
                co.created_at,
                co.updated_at,
                u.full_name AS client_name,
                u.phone AS client_phone,
                t.name AS tariff
            FROM connection_orders co
            LEFT JOIN users u ON u.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            WHERE co.is_active = TRUE
              AND co.status = 'completed'
              AND DATE(co.updated_at) = CURRENT_DATE
            ORDER BY co.updated_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def list_connection_orders_cancelled(limit: int = 10) -> List[Dict[str, Any]]:
    """Bekor qilingan connection orders."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT
                co.id,
                co.application_number,
                co.address,
                co.status,
                co.created_at,
                co.updated_at,
                u.full_name AS client_name,
                u.phone AS client_phone,
                t.name AS tariff
            FROM connection_orders co
            LEFT JOIN users u ON u.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            WHERE co.is_active = FALSE
            ORDER BY co.updated_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def fetch_staff_activity() -> List[Dict[str, Any]]:
    """Xodimlar faoliyati - barcha xodimlar va ularning arizalari."""
    return await fetch_staff_activity_with_time_filter("total")

async def fetch_staff_activity_with_time_filter(time_filter: str = "total") -> List[Dict[str, Any]]:
    """
    Xodimlar faoliyati - vaqt filtri bilan.
    time_filter: 'today', '3days', '7days', 'month', 'total'
    Counts connection_orders and staff_orders where connection exists.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Vaqt filtri uchun WHERE sharti
        # created - order yaratilgan vaqt
        # assigned/sent - workflow orqali tayinlangan/yuborilgan vaqt (la.created_at)
        if time_filter == "total":
            time_condition_co = "TRUE"
            time_condition_so = "TRUE"
            time_condition_assign = "TRUE"  # Assignment vaqt filtri
        else:
            time_conditions = {
                "today": "created_at >= CURRENT_DATE",
                "3days": "created_at >= CURRENT_DATE - INTERVAL '3 days'",
                "7days": "created_at >= CURRENT_DATE - INTERVAL '7 days'",
                "month": "created_at >= CURRENT_DATE - INTERVAL '30 days'"
            }
            base_condition = time_conditions.get(time_filter, "TRUE")
            # Table alias bilan to'liq shart
            if base_condition == "TRUE":
                time_condition_co = "TRUE"
                time_condition_so = "TRUE"
                time_condition_assign = "TRUE"
            else:
                # Created uchun - order yaratilgan vaqt
                time_condition_co = f"co.{base_condition}"
                time_condition_so = f"so.{base_condition}"
                # Assigned/Sent uchun - assignment vaqti (la.created_at)
                time_condition_assign = f"la.{base_condition}"
        
        rows = await conn.fetch(
            f"""
            WITH last_assign AS (
                SELECT DISTINCT ON (c.application_number)
                       c.application_number,
                       c.recipient_id,
                       c.sender_id,
                       c.recipient_status,
                       c.sender_status,
                       c.created_at
                FROM connections c
                WHERE c.application_number IS NOT NULL
                ORDER BY c.application_number, c.created_at DESC
            ),
            manager_connection_stats AS (
                SELECT
                    u.id,
                    u.full_name,
                    u.phone,
                    u.role,
                    u.created_at,
                    -- Orders they created (as user_id) - Connection orders
                    COUNT(DISTINCT CASE WHEN co.user_id = u.id AND {time_condition_co} THEN co.id END) as created_conn_orders,
                    COUNT(DISTINCT CASE WHEN co.user_id = u.id AND co.status NOT IN ('cancelled', 'completed') AND {time_condition_co} THEN co.id END) as created_conn_active,
                    -- Orders assigned to them through workflow (as recipient) - Connection orders
                    -- Time filter: la.created_at (assignment vaqti)
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND la.recipient_status IN ('in_manager', 'in_junior_manager') AND {time_condition_assign} THEN co.id END) as assigned_conn_orders,
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND la.recipient_status IN ('in_manager', 'in_junior_manager') AND co.status NOT IN ('cancelled', 'completed') AND {time_condition_assign} THEN co.id END) as assigned_conn_active,
                    -- Orders they sent (as sender_id) - Connection orders
                    -- Time filter: la.created_at (send vaqti)
                    COUNT(DISTINCT CASE WHEN la.sender_id = u.id AND co.id IS NOT NULL AND {time_condition_assign} THEN co.id END) as sent_conn_orders,
                    COUNT(DISTINCT CASE WHEN la.sender_id = u.id AND co.id IS NOT NULL AND co.status NOT IN ('cancelled', 'completed') AND {time_condition_assign} THEN co.id END) as sent_conn_active
                FROM users u
                LEFT JOIN connection_orders co ON COALESCE(co.is_active, TRUE) = TRUE
                LEFT JOIN last_assign la ON la.application_number = co.application_number
                WHERE u.role IN ('junior_manager', 'manager')
                  AND COALESCE(u.is_blocked, FALSE) = FALSE
                GROUP BY u.id, u.full_name, u.phone, u.role, u.created_at
            ),
            manager_staff_orders_stats AS (
                SELECT
                    u.id,
                    -- Orders they created (as user_id) - Staff orders
                    COUNT(DISTINCT CASE WHEN so.user_id = u.id AND {time_condition_so} THEN so.id END) as created_staff_orders,
                    COUNT(DISTINCT CASE WHEN so.user_id = u.id AND so.status NOT IN ('cancelled', 'completed') AND {time_condition_so} THEN so.id END) as created_staff_active,
                    -- Orders assigned to them through workflow (as recipient) - Staff orders
                    -- Time filter: la.created_at (assignment vaqti)
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND la.recipient_status IN ('in_manager', 'in_junior_manager') AND {time_condition_assign} THEN so.id END) as assigned_staff_orders,
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND la.recipient_status IN ('in_manager', 'in_junior_manager') AND so.status NOT IN ('cancelled', 'completed') AND {time_condition_assign} THEN so.id END) as assigned_staff_active,
                    -- Orders they sent (as sender_id) - Staff orders
                    -- Time filter: la.created_at (send vaqti)
                    COUNT(DISTINCT CASE WHEN la.sender_id = u.id AND so.id IS NOT NULL AND {time_condition_assign} THEN so.id END) as sent_staff_orders,
                    COUNT(DISTINCT CASE WHEN la.sender_id = u.id AND so.id IS NOT NULL AND so.status NOT IN ('cancelled', 'completed') AND {time_condition_assign} THEN so.id END) as sent_staff_active
                FROM users u
                LEFT JOIN staff_orders so ON COALESCE(so.is_active, TRUE) = TRUE
                LEFT JOIN last_assign la ON la.application_number = so.application_number
                WHERE u.role IN ('junior_manager', 'manager')
                  AND COALESCE(u.is_blocked, FALSE) = FALSE
                GROUP BY u.id
            )
            SELECT
                mcs.id,
                mcs.full_name,
                mcs.phone,
                mcs.role,
                mcs.created_at,
                -- Total orders: Manager uchun created+sent, Junior Manager uchun assigned+sent
                CASE 
                    WHEN mcs.role = 'junior_manager' THEN
                        (COALESCE(mcs.assigned_conn_orders, 0) + COALESCE(mcs.sent_conn_orders, 0) +
                         COALESCE(msos.assigned_staff_orders, 0) + COALESCE(msos.sent_staff_orders, 0))
                    ELSE
                        (COALESCE(mcs.created_conn_orders, 0) + COALESCE(mcs.sent_conn_orders, 0) +
                         COALESCE(msos.created_staff_orders, 0) + COALESCE(msos.sent_staff_orders, 0))
                END as total_orders,
                -- Connection count: Manager uchun created+sent, Junior Manager uchun assigned+sent
                CASE 
                    WHEN mcs.role = 'junior_manager' THEN
                        (COALESCE(mcs.assigned_conn_orders, 0) + COALESCE(mcs.sent_conn_orders, 0))
                    ELSE
                        (COALESCE(mcs.created_conn_orders, 0) + COALESCE(mcs.sent_conn_orders, 0))
                END as conn_count,
                -- Active count: barcha role lar uchun bir xil
                (COALESCE(mcs.created_conn_active, 0) + COALESCE(mcs.assigned_conn_active, 0) + COALESCE(mcs.sent_conn_active, 0) +
                 COALESCE(msos.created_staff_active, 0) + COALESCE(msos.assigned_staff_active, 0) + COALESCE(msos.sent_staff_active, 0)) as active_count,
                -- Detailed counts (barcha role lar uchun saqlanadi)
                COALESCE(mcs.assigned_conn_orders, 0) as assigned_conn_count,
                COALESCE(mcs.created_conn_orders, 0) as created_conn_count,
                COALESCE(mcs.sent_conn_orders, 0) as sent_conn_count,
                COALESCE(msos.created_staff_orders, 0) as created_staff_count,
                COALESCE(msos.assigned_staff_orders, 0) as assigned_staff_count,
                COALESCE(msos.sent_staff_orders, 0) as sent_staff_count,
                -- Tech counts (set to 0 for now)
                0 as tech_count,
                0 as created_tech_count,
                0 as sent_tech_count
            FROM manager_connection_stats mcs
            LEFT JOIN manager_staff_orders_stats msos ON msos.id = mcs.id
            ORDER BY total_orders DESC, mcs.full_name
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()