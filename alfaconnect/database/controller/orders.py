# database/controller/orders.py

from typing import Dict, Any, Optional, List, Union
import asyncpg
import logging
from config import settings
from database.basic.region import normalize_region_code
from database.basic.phone import normalize_phone

logger = logging.getLogger(__name__)

# =========================================================
#  Controller Orders yaratish
# =========================================================

async def ensure_user_controller(telegram_id: int, full_name: str, username: str) -> Dict[str, Any]:
    """
    Controller uchun user yaratish/yangilash.
    """
    from database.basic.user import ensure_user
    return await ensure_user(telegram_id, full_name, username, 'controller')

async def staff_orders_create(
    user_id: int,
    phone: Optional[str],
    abonent_id: Optional[str],
    region: Optional[Union[int, str]],
    address: str,
    tarif_id: Optional[int],
    business_type: str = "B2C",
    created_by_role: str = "controller",
) -> Dict[str, Any]:
    """
    Controller TOMONIDAN ulanish arizasini yaratish.
    Ulanish arizasi menejerga yuboriladi (status: 'in_manager').
    Connections jadvaliga ham yozuv qo'shadi.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        async with conn.transaction():
            # Application number generatsiya qilamiz - har bir business_type uchun alohida ketma-ketlikda
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
                        '', $8, 'connection', 'in_manager'::staff_order_status, TRUE, $9, NOW(), NOW())
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
            
            # Connections jadvaliga yozuv qo'shamiz (controller -> manager)
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
                VALUES ($1, $2, $2, 'new', 'in_manager', NOW(), NOW())
                """,
                app_number, user_id  # sender: controller, recipient: manager (hozircha bir xil)
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
    created_by_role: str = "controller",
) -> Dict[str, Any]:
    """
    Controller TOMONIDAN texnik xizmat arizasini yaratish.
    Default status: 'in_controller'.
    Connections jadvaliga ham yozuv qo'shadi.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        async with conn.transaction():
            # Application number generatsiya qilamiz - TECH uchun alohida ketma-ketlikda
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
                VALUES ($1, $2, $3, $4, $5, $6,
                        $7, $8, 'technician', 'in_controller'::staff_order_status, TRUE, $9, NOW(), NOW())
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
            
            staff_order_id = row["id"]
            app_number = row["application_number"]
            
            # Connections jadvaliga yozuv qo'shamiz (yaratilganda to'g'ridan-to'g'ri controller'da)
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
                app_number, user_id  # sender va recipient bir xil (controller yaratdi)
            )
            
            return {"id": staff_order_id, "application_number": row["application_number"]}
    finally:
        await conn.close()

# =========================================================
#  Controller Orders ro'yxatlari
# =========================================================

async def list_my_created_orders_by_type(user_id: int, order_type: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Controller tomonidan yaratilgan orders ro'yxatini type bo'yicha olish.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
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
            WHERE so.user_id = $1
              AND so.type_of_zayavka = $2
              AND COALESCE(so.is_active, TRUE) = TRUE
            ORDER BY so.created_at DESC
            LIMIT $3
            """,
            user_id, order_type, limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def fetch_staff_activity() -> List[Dict[str, Any]]:
    """Xodimlar faoliyati - texniklar va ularning barcha arizalari (client va xodim yaratgan)."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            WITH all_orders AS (
                -- Client yaratgan technician orders
                SELECT 
                    to_orders.id,
                    'technician' as type_of_zayavka,
                    to_orders.status::text,
                    to_orders.created_at,
                    to_orders.updated_at,
                    -- Texnik assignments
                    c.recipient_id as technician_id,
                    c.recipient_status::text as tech_status,
                    -- Controller assignments (yaratgan)
                    to_orders.user_id as controller_id
                FROM technician_orders to_orders
                LEFT JOIN connections c ON c.application_number = to_orders.application_number
                WHERE COALESCE(to_orders.is_active, TRUE) = TRUE
                
                UNION ALL
                
                -- Staff yaratgan connection orders
                SELECT 
                    so.id,
                    'connection' as type_of_zayavka,
                    so.status::text,
                    so.created_at,
                    so.updated_at,
                    -- Texnik assignments
                    c.recipient_id as technician_id,
                    c.recipient_status::text as tech_status,
                    -- Controller assignments (yaratgan)
                    so.user_id as controller_id
                FROM staff_orders so
                LEFT JOIN connections c ON c.application_number = so.application_number
                WHERE so.type_of_zayavka = 'connection'
                  AND COALESCE(so.is_active, TRUE) = TRUE
                
                UNION ALL
                
                -- Staff yaratgan technician orders
                SELECT 
                    so.id,
                    'technician' as type_of_zayavka,
                    so.status::text,
                    so.created_at,
                    so.updated_at,
                    -- Texnik assignments
                    c.recipient_id as technician_id,
                    c.recipient_status::text as tech_status,
                    -- Controller assignments (yaratgan)
                    so.user_id as controller_id
                FROM staff_orders so
                LEFT JOIN connections c ON c.application_number = so.application_number
                WHERE so.type_of_zayavka = 'technician'
                  AND COALESCE(so.is_active, TRUE) = TRUE
            )
            SELECT
                u.id,
                u.full_name,
                u.phone,
                u.role,
                u.created_at,
                -- Connection arizalar soni
                COUNT(CASE WHEN ao.type_of_zayavka = 'connection' THEN 1 END) as conn_count,
                -- Technician arizalar soni
                COUNT(CASE WHEN ao.type_of_zayavka = 'technician' THEN 1 END) as tech_count,
                -- Jami arizalar soni
                COUNT(ao.id) as total_count,
                -- Aktiv arizalar (texnikga yuborilgan va hali tugallanmagan)
                COUNT(CASE WHEN ao.technician_id = u.id 
                           AND ao.tech_status IN ('between_controller_technician', 'in_technician', 'in_technician_work', 'in_repairs', 'in_warehouse') 
                      THEN 1 END) as in_progress_orders,
                -- Tugallangan arizalar
                COUNT(CASE WHEN ao.technician_id = u.id 
                           AND ao.tech_status = 'completed' 
                      THEN 1 END) as completed_orders,
                -- Bekor qilingan arizalar
                COUNT(CASE WHEN ao.technician_id = u.id 
                           AND ao.tech_status = 'cancelled' 
                      THEN 1 END) as cancelled_orders,
                -- Oxirgi ariza sanasi
                MAX(ao.created_at) as last_order_date
            FROM users u
            LEFT JOIN all_orders ao ON (
                (u.role = 'technician' AND ao.technician_id = u.id) OR
                (u.role = 'controller' AND ao.controller_id = u.id)
            )
            WHERE u.role IN ('technician', 'controller')
              AND COALESCE(u.is_blocked, FALSE) = FALSE
            GROUP BY u.id, u.full_name, u.phone, u.role, u.created_at
            ORDER BY u.role, total_count DESC, u.full_name
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()
