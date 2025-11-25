# database/controller/queries.py

from typing import List, Dict, Any, Optional
import asyncpg
import logging
from config import settings

logger = logging.getLogger(__name__)

# =========================================================
#  Controller uchun asosiy funksiyalar
# =========================================================

async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Telegram ID orqali user ma'lumotlarini olish."""
    from database.basic.user import get_user_by_telegram_id as basic_get_user
    return await basic_get_user(telegram_id)

async def ensure_user_controller(telegram_id: int, full_name: str, username: str) -> Dict[str, Any]:
    """
    Controller uchun user yaratish/yangilash.
    """
    from database.basic.user import ensure_user
    return await ensure_user(telegram_id, full_name, username, 'controller')

# =========================================================
#  Controller Inbox - Staff Orders bilan ishlash
# =========================================================

async def fetch_controller_inbox_staff(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Controller inbox - staff orders ro'yxatini olish.
    Faqat 'in_controller' statusdagi staff orders va faqat texnik xizmat arizalari (type_of_zayavka = 'technician').
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
                COALESCE(client.full_name, u_owner.full_name, 'Mijoz') as client_name,
                COALESCE(client.phone, u_owner.phone, so.phone) as client_phone,
                CASE 
                    WHEN so.type_of_zayavka = 'connection' THEN t.name
                    WHEN so.type_of_zayavka = 'technician' THEN so.description
                    ELSE NULL
                END as tariff_or_problem,
                so.region as region_name,
                creator.full_name as staff_name,
                creator.phone as staff_phone,
                creator.role as staff_role,
                CASE 
                    WHEN so.type_of_zayavka = 'technician' THEN tech_ord.media
                    ELSE NULL
                END as media_file_id,
                CASE 
                    WHEN so.type_of_zayavka = 'technician' AND tech_ord.media IS NOT NULL THEN 'media'
                    ELSE NULL
                END as media_type
            FROM staff_orders so
            JOIN last_assign la ON la.application_number = so.application_number
            LEFT JOIN tarif t ON t.id = so.tarif_id
            LEFT JOIN users creator ON creator.id = so.user_id
            LEFT JOIN users client ON client.id::text = so.abonent_id
            LEFT JOIN users u_owner ON u_owner.id = so.user_id
            LEFT JOIN technician_orders tech_ord ON tech_ord.id = so.id AND so.type_of_zayavka = 'technician'
            WHERE la.recipient_status = 'in_controller'
              AND so.status = 'in_controller'
              AND so.type_of_zayavka = 'technician'
              AND COALESCE(so.is_active, TRUE) = TRUE
            ORDER BY so.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def count_controller_inbox_staff() -> int:
    """
    Controller inbox - staff orders sonini olish.
    Faqat texnik xizmat arizalari (type_of_zayavka = 'technician').
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval(
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
            SELECT COUNT(*)
            FROM staff_orders so
            JOIN last_assign la ON la.application_number = so.application_number
            WHERE la.recipient_status = 'in_controller'
              AND so.status = 'in_controller'
              AND so.type_of_zayavka = 'technician'
              AND COALESCE(so.is_active, TRUE) = TRUE
            """
        )
        return count or 0
    finally:
        await conn.close()

# =========================================================
#  Controller -> Technician assignment
# =========================================================

async def assign_to_technician_for_staff(request_id: int | str, tech_id: int, actor_id: int) -> Dict[str, Any]:
    """
    Controller -> Technician (staff_orders uchun):
      1) staff_orders.status: old -> 'between_controller_technician'
      2) connections: HAR DOIM yangi qator INSERT
         sender_id=controller(actor_id), recipient_id=tech_id,
         sender_status=old_status, recipient_status=new_status
      3) Technician'ga notification yuboradi
    
    Returns:
        Dict with recipient info for notification
    """
    # '8_2025' kabi bo'lsa ham 8 ni olamiz
    try:
        request_id_int = int(str(request_id).split("_")[0])
    except Exception:
        request_id_int = int(request_id)

    conn = await asyncpg.connect(settings.DB_URL)
    try:
        async with conn.transaction():
            # Technician mavjudmi? + uning ma'lumotlarini olamiz
            tech_info = await conn.fetchrow(
                "SELECT id, telegram_id, language FROM users WHERE id = $1 AND role = 'technician'",
                tech_id,
            )
            if not tech_info:
                raise ValueError("Technician topilmadi")

            # 1) Eski statusni va application_number'ni lock bilan o'qiymiz
            row_old = await conn.fetchrow(
                """
                SELECT status, application_number, type_of_zayavka
                  FROM staff_orders
                 WHERE id = $1
                 FOR UPDATE
                """,
                request_id_int
            )
            if not row_old:
                raise ValueError("Staff order topilmadi")

            old_status: str = row_old["status"]
            app_number: str = row_old["application_number"]
            order_type: str = row_old["type_of_zayavka"] or "staff"

            # 2) Yangi statusga o'tkazamiz
            row_new = await conn.fetchrow(
                """
                UPDATE staff_orders
                   SET status     = 'between_controller_technician',
                       updated_at = NOW()
                 WHERE id = $1
             RETURNING status
                """,
                request_id_int
            )
            new_status: str = row_new["status"]  # 'between_controller_technician'

            # 3) Connections yozamiz - Controller -> Technician
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
                VALUES (
                    $1, $2, $3, $4, $5, NOW(), NOW()
                )
                """,
                app_number,         # application_number
                request_id_int,    # staff_id
                actor_id,          # controller
                tech_id,           # technician
                old_status,        # masalan: 'in_controller'
                new_status         # 'between_controller_technician'
            )
            
            # 4) Hozirgi yuklamani hisoblaymiz
            current_load = await conn.fetchval(
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
                SELECT COUNT(*)
                FROM last_assign la
                JOIN staff_orders so ON so.application_number = la.application_number
                WHERE la.recipient_id = $1
                  AND COALESCE(so.is_active, TRUE) = TRUE
                  AND so.status IN ('between_controller_technician', 'in_technician')
                  AND la.recipient_status IN ('between_controller_technician', 'in_technician')
                """,
                tech_id
            )
            
            return {
                "telegram_id": tech_info["telegram_id"],
                "language": tech_info["language"] or "uz",
                "application_number": app_number,
                "order_type": order_type,
                "current_load": current_load or 0,
                # for notifications helper
                "recipient_id": tech_info["id"],
                "recipient_role": "technician",
                "sender_id": actor_id,
                "sender_role": "controller",
                # self-created check (not applicable for staff-to-tech typically)
                "creator_id": None,
            }
    finally:
        await conn.close()

async def get_technicians_with_load_via_history() -> List[Dict[str, Any]]:
    """
    Technicianlarni hozirgi yuklamasi (barcha turdagi arizalar soni) bilan olish.
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
                    COUNT(*) AS cnt
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
                    COUNT(*) AS cnt
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
                    COUNT(*) AS cnt
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
                    SUM(cnt) AS total_count
                FROM (
                    SELECT technician_id, cnt FROM connection_loads
                    UNION ALL
                    SELECT technician_id, cnt FROM technician_loads
                    UNION ALL
                    SELECT technician_id, cnt FROM staff_loads
                ) combined
                GROUP BY technician_id
            )
            SELECT 
                u.id,
                u.full_name,
                u.username,
                u.phone,
                u.telegram_id,
                COALESCE(tl.total_count, 0) AS load_count
            FROM users u
            LEFT JOIN total_loads tl ON tl.technician_id = u.id
            WHERE u.role = 'technician'
              AND COALESCE(u.is_blocked, FALSE) = FALSE
            ORDER BY u.full_name NULLS LAST, u.id
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# =========================================================
#  Controller Orders ro'yxatlari
# =========================================================

async def list_controller_orders_by_status(status: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Controller arizalarini status bo'yicha olish."""
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
                so.created_at
            FROM staff_orders so
            WHERE so.status = $1
              AND COALESCE(so.is_active, TRUE) = TRUE
            ORDER BY so.created_at DESC
            LIMIT $2
            """,
            status, limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# =========================================================
#  Controller Inbox - Connection Orders
# =========================================================

async def fetch_controller_inbox_connection(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Controller inbox - connection orders (ulanish arizalari).
    Faqat 'in_controller' statusdagi connection orders.
    jm_notes ni ham olamiz.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT
                co.id,
                co.application_number,
                co.address,
                co.region,
                co.status,
                co.jm_notes,
                co.created_at,
                co.updated_at,
                u.full_name AS client_name,
                u.phone AS client_phone,
                t.name AS tariff
            FROM connection_orders co
            LEFT JOIN users u ON u.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            WHERE co.is_active = TRUE
              AND co.status = 'in_controller'
            ORDER BY co.created_at DESC, co.id DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# =========================================================
#  Controller Inbox - Tech Orders (Service Orders)
# =========================================================

async def fetch_controller_inbox_tech(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Controller inbox - tech service orders (texnik xizmat arizalari).
    Client tomonidan yaratilgan, 'in_controller' statusdagi technician orders.
    media va description ni ham olamiz.
    Ikkala usulni qo'llab-quvvatlaydi:
    1. technician_orders.media ustunidagi eski usul
    2. media_files jadvalidagi yangi usul
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT
                tech_ord.id,
                tech_ord.application_number,
                tech_ord.address,
                tech_ord.region,
                tech_ord.status,
                tech_ord.description,
                tech_ord.created_at,
                tech_ord.updated_at,
                u.full_name AS client_name,
                u.phone AS client_phone,
                
                -- Eski usul: technician_orders.media ustunidan
                tech_ord.media AS old_media_file_id,
                
                -- Yangi usul: media_files jadvalidan
                mf.file_path AS new_media_file_id,
                mf.file_type AS new_media_type,
                
                -- Media mavjudligini aniqlash
                CASE 
                    WHEN tech_ord.media IS NOT NULL AND tech_ord.media != '' THEN tech_ord.media
                    WHEN mf.file_path IS NOT NULL AND mf.file_path != '' THEN mf.file_path
                    ELSE NULL
                END AS media_file_id,
                
                CASE 
                    WHEN tech_ord.media IS NOT NULL AND tech_ord.media != '' THEN 
                        CASE 
                            WHEN tech_ord.media LIKE 'BAACAgI%' THEN 'video'
                            WHEN tech_ord.media LIKE 'BAADBAAD%' THEN 'video'
                            WHEN tech_ord.media LIKE 'BAAgAgI%' THEN 'video'
                            WHEN tech_ord.media LIKE 'AgACAgI%' THEN 'photo'
                            WHEN tech_ord.media LIKE 'CAAQAgI%' THEN 'photo'
                            WHEN tech_ord.media LIKE '%.mp4' OR tech_ord.media LIKE '%.avi' OR tech_ord.media LIKE '%.mov' THEN 'video'
                            WHEN tech_ord.media LIKE '%.jpg' OR tech_ord.media LIKE '%.jpeg' OR tech_ord.media LIKE '%.png' THEN 'photo'
                            ELSE 'video'  -- Default video sifatida
                        END
                    WHEN mf.file_type IS NOT NULL AND mf.file_type != '' THEN mf.file_type
                    ELSE NULL
                END AS media_type
                
            FROM technician_orders tech_ord
            LEFT JOIN users u ON u.id = tech_ord.user_id
            LEFT JOIN media_files mf ON mf.related_table = 'technician_orders' 
                                    AND mf.related_id = tech_ord.id 
                                    AND mf.is_active = TRUE
            WHERE COALESCE(tech_ord.is_active, TRUE) = TRUE
              AND tech_ord.status = 'in_controller'
            ORDER BY tech_ord.created_at DESC, tech_ord.id DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# =========================================================
#  Assignment Functions
# =========================================================

async def assign_to_technician_connection(request_id: int, tech_id: int, actor_id: int) -> Dict[str, Any]:
    """
    Connection order ni texnikka yuborish.
    Status: in_controller -> in_technician
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Update connection_orders
        await conn.execute(
            """
            UPDATE connection_orders
            SET status = 'between_controller_technician',
                updated_at = NOW()
            WHERE id = $1
            """,
            request_id
        )
        
        # Get application info
        app_info = await conn.fetchrow(
            """
            SELECT application_number FROM connection_orders WHERE id = $1
            """,
            request_id
        )
        
        # Insert into connections table
        await conn.execute(
            """
            INSERT INTO connections (
                application_number, sender_id, recipient_id,
                sender_status, recipient_status, created_at
            ) VALUES ($1, $2, $3, 'in_controller', 'between_controller_technician', NOW())
            """,
            app_info["application_number"], actor_id, tech_id
        )
        
        # Get technician info and current load
        tech_info = await conn.fetchrow(
            """
            SELECT u.telegram_id, u.language, u.full_name
            FROM users u
            WHERE u.id = $1
            """,
            tech_id
        )
        
        # Calculate current load - ALL order types
        load_count = await conn.fetchval(
            """
            WITH connection_loads AS (
                SELECT COUNT(*) AS cnt
                FROM connection_orders co
                WHERE co.status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  AND co.is_active = TRUE
                  AND EXISTS (
                      SELECT 1 FROM connections c
                      WHERE c.application_number = co.id::text
                        AND c.recipient_id = $1
                        AND c.recipient_status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  )
            ),
            technician_loads AS (
                SELECT COUNT(*) AS cnt
                FROM technician_orders to_orders
                WHERE to_orders.status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  AND COALESCE(to_orders.is_active, TRUE) = TRUE
                  AND EXISTS (
                      SELECT 1 FROM connections c
                      WHERE EXISTS (SELECT 1 FROM technician_orders WHERE technician_orders.application_number = c.application_number AND technician_orders.id = to_orders.id)
                        AND c.recipient_id = $1
                        AND c.recipient_status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  )
            ),
            staff_loads AS (
                SELECT COUNT(*) AS cnt
                FROM staff_orders so
                WHERE so.status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  AND COALESCE(so.is_active, TRUE) = TRUE
                  AND EXISTS (
                      SELECT 1 FROM connections c
                      WHERE EXISTS (SELECT 1 FROM staff_orders WHERE staff_orders.application_number = c.application_number AND staff_orders.id = so.id)
                        AND c.recipient_id = $1
                        AND c.recipient_status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  )
            )
            SELECT 
                COALESCE((SELECT cnt FROM connection_loads), 0) +
                COALESCE((SELECT cnt FROM technician_loads), 0) +
                COALESCE((SELECT cnt FROM staff_loads), 0) AS total_load
            """,
            tech_id
        ) or 0
        
        return {
            "telegram_id": tech_info["telegram_id"],
            "language": tech_info["language"],
            "application_number": app_info["application_number"],
            "current_load": load_count
        }
    finally:
        await conn.close()

async def assign_to_technician_tech(request_id: int, tech_id: int, actor_id: int) -> Dict[str, Any]:
    """
    Tech service order ni texnikka yuborish.
    Status: in_controller -> in_technician
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Update technician_orders
        await conn.execute(
            """
            UPDATE technician_orders
            SET status = 'between_controller_technician',
                updated_at = NOW()
            WHERE id = $1
            """,
            request_id
        )
        
        # Get application info
        app_info = await conn.fetchrow(
            """
            SELECT application_number FROM technician_orders WHERE id = $1
            """,
            request_id
        )
        
        # Insert into connections table (technician_id)
        await conn.execute(
            """
            INSERT INTO connections (
                application_number, sender_id, recipient_id,
                sender_status, recipient_status, created_at
            ) VALUES ($1, $2, $3, 'in_controller', 'between_controller_technician', NOW())
            """,
            app_info["application_number"], actor_id, tech_id
        )
        
        # Get technician info and current load
        tech_info = await conn.fetchrow(
            """
            SELECT u.telegram_id, u.language, u.full_name
            FROM users u
            WHERE u.id = $1
            """,
            tech_id
        )
        
        # Calculate current load - ALL order types
        load_count = await conn.fetchval(
            """
            WITH connection_loads AS (
                SELECT COUNT(*) AS cnt
                FROM connection_orders co
                WHERE co.status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  AND co.is_active = TRUE
                  AND EXISTS (
                      SELECT 1 FROM connections c
                      WHERE c.application_number = co.id::text
                        AND c.recipient_id = $1
                        AND c.recipient_status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  )
            ),
            technician_loads AS (
                SELECT COUNT(*) AS cnt
                FROM technician_orders to_orders
                WHERE to_orders.status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  AND COALESCE(to_orders.is_active, TRUE) = TRUE
                  AND EXISTS (
                      SELECT 1 FROM connections c
                      WHERE EXISTS (SELECT 1 FROM technician_orders WHERE technician_orders.application_number = c.application_number AND technician_orders.id = to_orders.id)
                        AND c.recipient_id = $1
                        AND c.recipient_status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  )
            ),
            staff_loads AS (
                SELECT COUNT(*) AS cnt
                FROM staff_orders so
                WHERE so.status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  AND COALESCE(so.is_active, TRUE) = TRUE
                  AND EXISTS (
                      SELECT 1 FROM connections c
                      WHERE EXISTS (SELECT 1 FROM staff_orders WHERE staff_orders.application_number = c.application_number AND staff_orders.id = so.id)
                        AND c.recipient_id = $1
                        AND c.recipient_status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  )
            )
            SELECT 
                COALESCE((SELECT cnt FROM connection_loads), 0) +
                COALESCE((SELECT cnt FROM technician_loads), 0) +
                COALESCE((SELECT cnt FROM staff_loads), 0) AS total_load
            """,
            tech_id
        ) or 0
        
        return {
            "telegram_id": tech_info["telegram_id"],
            "language": tech_info["language"],
            "application_number": app_info["application_number"],
            "current_load": load_count
        }
    finally:
        await conn.close()

async def assign_to_technician_staff(request_id: int, tech_id: int, actor_id: int) -> Dict[str, Any]:
    """
    Staff order ni texnikka yuborish (xodim yaratgan ariza).
    Status: in_controller -> in_technician
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Update staff_orders
        await conn.execute(
            """
            UPDATE staff_orders
            SET status = 'between_controller_technician',
                updated_at = NOW()
            WHERE id = $1
            """,
            request_id
        )
        
        # Get application info
        app_info = await conn.fetchrow(
            """
            SELECT application_number FROM staff_orders WHERE id = $1
            """,
            request_id
        )
        
        # Insert into connections table (staff_id)
        await conn.execute(
            """
            INSERT INTO connections (
                application_number, sender_id, recipient_id,
                sender_status, recipient_status, created_at
            ) VALUES ($1, $2, $3, 'in_controller', 'between_controller_technician', NOW())
            """,
            app_info["application_number"], actor_id, tech_id
        )
        
        # Get technician info and current load
        tech_info = await conn.fetchrow(
            """
            SELECT u.telegram_id, u.language, u.full_name
            FROM users u
            WHERE u.id = $1
            """,
            tech_id
        )
        
        # Calculate current load - ALL order types
        load_count = await conn.fetchval(
            """
            WITH connection_loads AS (
                SELECT COUNT(*) AS cnt
                FROM connection_orders co
                WHERE co.status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  AND co.is_active = TRUE
                  AND EXISTS (
                      SELECT 1 FROM connections c
                      WHERE c.application_number = co.id::text
                        AND c.recipient_id = $1
                        AND c.recipient_status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  )
            ),
            technician_loads AS (
                SELECT COUNT(*) AS cnt
                FROM technician_orders to_orders
                WHERE to_orders.status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  AND COALESCE(to_orders.is_active, TRUE) = TRUE
                  AND EXISTS (
                      SELECT 1 FROM connections c
                      WHERE EXISTS (SELECT 1 FROM technician_orders WHERE technician_orders.application_number = c.application_number AND technician_orders.id = to_orders.id)
                        AND c.recipient_id = $1
                        AND c.recipient_status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  )
            ),
            staff_loads AS (
                SELECT COUNT(*) AS cnt
                FROM staff_orders so
                WHERE so.status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  AND COALESCE(so.is_active, TRUE) = TRUE
                  AND EXISTS (
                      SELECT 1 FROM connections c
                      WHERE EXISTS (SELECT 1 FROM staff_orders WHERE staff_orders.application_number = c.application_number AND staff_orders.id = so.id)
                        AND c.recipient_id = $1
                        AND c.recipient_status IN ('between_controller_technician', 'in_technician', 'in_technician_work')
                  )
            )
            SELECT 
                COALESCE((SELECT cnt FROM connection_loads), 0) +
                COALESCE((SELECT cnt FROM technician_loads), 0) +
                COALESCE((SELECT cnt FROM staff_loads), 0) AS total_load
            """,
            tech_id
        ) or 0
        
        return {
            "telegram_id": tech_info["telegram_id"],
            "language": tech_info["language"],
            "application_number": app_info["application_number"],
            "current_load": load_count
        }
    finally:
        await conn.close()

async def assign_to_ccs_connection(request_id: int, ccs_id: int, actor_id: int) -> Dict[str, Any]:
    """
    Connection order ni CCS Supervisorga yuborish.
    Status: in_controller -> in_call_center_supervisor
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Update connection_orders
        await conn.execute(
            """
            UPDATE connection_orders
            SET status = 'in_call_center_supervisor',
                updated_at = NOW()
            WHERE id = $1
            """,
            request_id
        )
        
        # Get application info
        app_info = await conn.fetchrow(
            """
            SELECT application_number FROM connection_orders WHERE id = $1
            """,
            request_id
        )
        
        # Insert into connections table
        await conn.execute(
            """
            INSERT INTO connections (
                application_number, sender_id, recipient_id,
                sender_status, recipient_status, created_at
            ) VALUES ($1, $2, $3, 'in_controller', 'in_call_center_supervisor', NOW())
            """,
            app_info["application_number"], actor_id, ccs_id
        )
        
        # Get CCS info and current load
        ccs_info = await conn.fetchrow(
            """
            SELECT u.telegram_id, u.language, u.full_name
            FROM users u
            WHERE u.id = $1
            """,
            ccs_id
        )
        
        # Calculate current load for CCS (connection orders)
        load_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM connection_orders co
            WHERE co.status = 'in_call_center_supervisor'
              AND co.is_active = TRUE
              AND EXISTS (
                  SELECT 1 FROM connections c
                  WHERE c.application_number = co.id
                    AND c.recipient_id = $1
                    AND c.recipient_status = 'in_call_center_supervisor'
              )
            """,
            ccs_id
        ) or 0
        
        return {
            "telegram_id": ccs_info["telegram_id"],
            "language": ccs_info["language"],
            "application_number": app_info["application_number"],
            "current_load": load_count
        }
    finally:
        await conn.close()

async def assign_to_ccs_tech(request_id: int, ccs_id: int, actor_id: int) -> Dict[str, Any]:
    """
    Tech service order ni CCS Supervisorga yuborish.
    Status: in_controller -> in_call_center_supervisor
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Update technician_orders
        await conn.execute(
            """
            UPDATE technician_orders
            SET status = 'in_call_center_supervisor',
                updated_at = NOW()
            WHERE id = $1
            """,
            request_id
        )
        
        # Get application info
        app_info = await conn.fetchrow(
            """
            SELECT application_number FROM technician_orders WHERE id = $1
            """,
            request_id
        )
        
        # Insert into connections table
        await conn.execute(
            """
            INSERT INTO connections (
                application_number, sender_id, recipient_id,
                sender_status, recipient_status, created_at
            ) VALUES ($1, $2, $3, 'in_controller', 'in_call_center_supervisor', NOW())
            """,
            app_info["application_number"], actor_id, ccs_id
        )
        
        # Get CCS info and current load
        ccs_info = await conn.fetchrow(
            """
            SELECT u.telegram_id, u.language, u.full_name
            FROM users u
            WHERE u.id = $1
            """,
            ccs_id
        )
        
        # Calculate current load for CCS
        load_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM technician_orders tech_ord
            WHERE tech_ord.status = 'in_call_center_supervisor'
              AND COALESCE(tech_ord.is_active, TRUE) = TRUE
              AND EXISTS (
                  SELECT 1 FROM connections c
                  WHERE EXISTS (SELECT 1 FROM technician_orders WHERE technician_orders.application_number = c.application_number AND technician_orders.id = tech_ord.id)
                    AND c.recipient_id = $1
                    AND c.recipient_status = 'in_call_center_supervisor'
              )
            """,
            ccs_id
        ) or 0
        
        return {
            "telegram_id": ccs_info["telegram_id"],
            "language": ccs_info["language"],
            "application_number": app_info["application_number"],
            "current_load": load_count
        }
    finally:
        await conn.close()

async def assign_to_ccs_staff(request_id: int, ccs_id: int, actor_id: int) -> Dict[str, Any]:
    """
    Staff order ni CCS Supervisorga yuborish.
    Status: in_controller -> in_call_center_supervisor
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Update staff_orders
        await conn.execute(
            """
            UPDATE staff_orders
            SET status = 'in_call_center_supervisor',
                updated_at = NOW()
            WHERE id = $1
            """,
            request_id
        )
        
        # Get application info
        app_info = await conn.fetchrow(
            """
            SELECT application_number FROM staff_orders WHERE id = $1
            """,
            request_id
        )
        
        # Insert into connections table
        await conn.execute(
            """
            INSERT INTO connections (
                application_number, sender_id, recipient_id,
                sender_status, recipient_status, created_at
            ) VALUES ($1, $2, $3, 'in_controller', 'in_call_center_supervisor', NOW())
            """,
            app_info["application_number"], actor_id, ccs_id
        )
        
        # Get CCS info and current load
        ccs_info = await conn.fetchrow(
            """
            SELECT u.telegram_id, u.language, u.full_name
            FROM users u
            WHERE u.id = $1
            """,
            ccs_id
        )
        
        # Calculate current load for CCS (staff orders)
        load_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM staff_orders so
            WHERE so.status = 'in_call_center_supervisor'
              AND COALESCE(so.is_active, TRUE) = TRUE
              AND EXISTS (
                  SELECT 1 FROM connections c
                  WHERE EXISTS (SELECT 1 FROM staff_orders WHERE staff_orders.application_number = c.application_number AND staff_orders.id = so.id)
                    AND c.recipient_id = $1
                    AND c.recipient_status = 'in_call_center_supervisor'
              )
            """,
            ccs_id
        ) or 0
        
        return {
            "telegram_id": ccs_info["telegram_id"],
            "language": ccs_info["language"],
            "application_number": app_info["application_number"],
            "current_load": load_count
        }
    finally:
        await conn.close()

# =========================================================
#  Staff Activity functions
# =========================================================

async def fetch_controller_staff_activity() -> List[Dict[str, Any]]:
    """Controller uchun xodimlar faoliyati - barcha xodimlar va ularning arizalari."""
    return await fetch_controller_staff_activity_with_time_filter("total")

async def fetch_controller_staff_activity_with_time_filter(time_filter: str = "total") -> List[Dict[str, Any]]:
    """
    Controller uchun xodimlar faoliyati - vaqt filtri bilan.
    time_filter: 'today', '3days', '7days', 'month', 'total'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Vaqt filtri uchun WHERE sharti
        if time_filter == "total":
            # Barcha vaqt uchun hech qanday shart qo'shmaslik
            staff_time_condition = "TRUE"
            conn_time_condition = "TRUE"
            tech_time_condition = "TRUE"
        else:
            if time_filter == "today":
                time_condition = "created_at >= CURRENT_DATE"
            elif time_filter == "7days":
                time_condition = "created_at >= CURRENT_DATE - INTERVAL '7 days'"
            elif time_filter == "month":
                time_condition = "created_at >= CURRENT_DATE - INTERVAL '30 days'"
            else:
                time_condition = "TRUE"
            staff_time_condition = f"so.{time_condition}"
            conn_time_condition = f"co.{time_condition}"
            tech_time_condition = f"tech_orders.{time_condition}"
        
        # SQL query'ni alohida qilib yozamiz
        if time_filter == "total":
            # For total filter, add technician completed orders calculation
            query = """
            WITH last_conn_assign AS (
                SELECT DISTINCT ON (c.application_number)
                       c.application_number,
                       c.recipient_id,
                       c.sender_id,
                       c.recipient_status,
                       c.sender_status
                FROM connections c
                WHERE c.application_number IS NOT NULL
                ORDER BY c.application_number, c.created_at DESC
            ),
            controller_connection_stats AS (
                SELECT
                    u.id,
                    u.full_name,
                    u.phone,
                    u.role,
                    u.created_at,
                    -- Orders they created (as user_id) - Connection orders (all statuses for count)
                    COUNT(DISTINCT CASE WHEN co.user_id = u.id THEN co.id END) as created_conn_orders,
                    COUNT(DISTINCT CASE WHEN co.user_id = u.id AND co.status NOT IN ('cancelled', 'completed') THEN co.id END) as created_conn_active,
                    -- Orders assigned to them through workflow (as recipient) - ALL statuses including completed
                    COUNT(DISTINCT CASE WHEN c.recipient_id = u.id AND c.recipient_status = 'in_controller' THEN co.id END) as assigned_conn_orders,
                    COUNT(DISTINCT CASE WHEN c.recipient_id = u.id AND c.recipient_status = 'in_controller' AND co.status NOT IN ('cancelled', 'completed') THEN co.id END) as assigned_conn_active
                FROM users u
                LEFT JOIN connection_orders co ON COALESCE(co.is_active, TRUE) = TRUE
                LEFT JOIN connections c ON c.application_number = co.application_number
                WHERE u.role IN ('controller')
                GROUP BY u.id, u.full_name, u.phone, u.role, u.created_at
            ),
            controller_technician_stats AS (
                SELECT
                    u.id,
                    -- Orders they created (as user_id) - Technician orders (all statuses for count)
                    COUNT(DISTINCT CASE WHEN tech_orders.user_id = u.id THEN tech_orders.id END) as created_tech_orders,
                    COUNT(DISTINCT CASE WHEN tech_orders.user_id = u.id AND tech_orders.status NOT IN ('cancelled', 'completed') THEN tech_orders.id END) as created_tech_active,
                    -- Orders assigned to them through workflow (as recipient) - ALL statuses including completed
                    COUNT(DISTINCT CASE WHEN c.recipient_id = u.id AND c.recipient_status = 'in_controller' THEN tech_orders.id END) as assigned_tech_orders,
                    COUNT(DISTINCT CASE WHEN c.recipient_id = u.id AND c.recipient_status = 'in_controller' AND tech_orders.status NOT IN ('cancelled', 'completed') THEN tech_orders.id END) as assigned_tech_active
                FROM users u
                LEFT JOIN technician_orders tech_orders ON COALESCE(tech_orders.is_active, TRUE) = TRUE
                LEFT JOIN connections c ON c.application_number = tech_orders.application_number
                WHERE u.role = 'controller'
                GROUP BY u.id
            ),
            controller_staff_orders_stats AS (
                SELECT
                    u.id,
                    -- Orders they created (as user_id) - Staff orders (all statuses for count)
                    COUNT(DISTINCT CASE WHEN so.user_id = u.id THEN so.id END) as created_staff_orders,
                    COUNT(DISTINCT CASE WHEN so.user_id = u.id AND so.status NOT IN ('cancelled', 'completed') THEN so.id END) as created_staff_active,
                    -- Orders assigned to them through workflow (as recipient) - ALL statuses including completed
                    COUNT(DISTINCT CASE WHEN c.recipient_id = u.id AND c.recipient_status = 'in_controller' THEN so.id END) as assigned_staff_orders,
                    COUNT(DISTINCT CASE WHEN c.recipient_id = u.id AND c.recipient_status = 'in_controller' AND so.status NOT IN ('cancelled', 'completed') THEN so.id END) as assigned_staff_active
                FROM users u
                LEFT JOIN staff_orders so ON COALESCE(so.is_active, TRUE) = TRUE
                LEFT JOIN connections c ON c.application_number = so.application_number
                WHERE u.role = 'controller'
                GROUP BY u.id
            ),
            controller_sent_orders_stats AS (
                SELECT
                    u.id,
                    -- Orders they sent (as sender_id) - Through connections table (all statuses for count)
                    COUNT(DISTINCT CASE WHEN c.sender_id = u.id THEN co.id END) as sent_conn_orders,
                    COUNT(DISTINCT CASE WHEN c.sender_id = u.id AND co.status NOT IN ('cancelled', 'completed') THEN co.id END) as sent_conn_active,
                    COUNT(DISTINCT CASE WHEN c.sender_id = u.id THEN tech_orders.id END) as sent_tech_orders,
                    COUNT(DISTINCT CASE WHEN c.sender_id = u.id AND tech_orders.status NOT IN ('cancelled', 'completed') THEN tech_orders.id END) as sent_tech_active,
                    COUNT(DISTINCT CASE WHEN c.sender_id = u.id THEN so.id END) as sent_staff_orders,
                    COUNT(DISTINCT CASE WHEN c.sender_id = u.id AND so.status NOT IN ('cancelled', 'completed') THEN so.id END) as sent_staff_active
                FROM users u
                LEFT JOIN connections c ON c.sender_id = u.id
                LEFT JOIN connection_orders co ON co.application_number = c.application_number
                LEFT JOIN technician_orders tech_orders ON tech_orders.application_number = c.application_number
                LEFT JOIN staff_orders so ON so.application_number = c.application_number
                WHERE u.role = 'controller'
                GROUP BY u.id
            ),
            last_assign_for_tech AS (
                -- Get latest connection status for each application_number
                SELECT DISTINCT ON (c.application_number)
                       c.application_number,
                       c.recipient_id,
                       c.recipient_status
                FROM connections c
                WHERE c.application_number IS NOT NULL
                ORDER BY c.application_number, c.created_at DESC
            ),
            technician_stats AS (
                SELECT
                    u.id,
                    u.full_name,
                    u.phone,
                    u.role,
                    u.created_at,
                    -- Ulanish arizalari uchun (Texnikka kelgan va yopilgan) - using latest assignment
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND co.id IS NOT NULL THEN co.id END) as assigned_conn_count,
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND co.status = 'completed' THEN co.id END) as completed_conn_count,
                    -- Texnik xizmat arizalari uchun (Texnikka kelgan va yopilgan) - using latest assignment
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND tech_orders.id IS NOT NULL THEN tech_orders.id END) as assigned_tech_count,
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND tech_orders.status = 'completed' THEN tech_orders.id END) as completed_tech_count,
                    -- Xodim yaratgan arizalar uchun (Texnikka kelgan va yopilgan) - using latest assignment
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND so.id IS NOT NULL THEN so.id END) as assigned_staff_count,
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND so.status = 'completed' THEN so.id END) as completed_staff_count
                FROM users u
                LEFT JOIN last_assign_for_tech la ON la.recipient_id = u.id
                LEFT JOIN connection_orders co ON co.application_number = la.application_number AND COALESCE(co.is_active, TRUE) = TRUE
                LEFT JOIN technician_orders tech_orders ON tech_orders.application_number = la.application_number AND COALESCE(tech_orders.is_active, TRUE) = TRUE
                LEFT JOIN staff_orders so ON so.application_number = la.application_number AND COALESCE(so.is_active, TRUE) = TRUE
                WHERE u.role = 'technician'
                  AND COALESCE(u.is_blocked, FALSE) = FALSE
                GROUP BY u.id, u.full_name, u.phone, u.role, u.created_at
            )
            SELECT
                ccs.id,
                ccs.full_name,
                ccs.phone,
                ccs.role,
                ccs.created_at,
                (COALESCE(ccs.created_conn_orders, 0) + COALESCE(csent.sent_conn_orders, 0) + 
                 COALESCE(cts.created_tech_orders, 0) + COALESCE(csent.sent_tech_orders, 0) +
                 COALESCE(csos.created_staff_orders, 0) + COALESCE(csent.sent_staff_orders, 0)) as total_orders,
                (COALESCE(ccs.created_conn_orders, 0) + COALESCE(csent.sent_conn_orders, 0)) as conn_count,
                (COALESCE(cts.created_tech_orders, 0) + COALESCE(csent.sent_tech_orders, 0)) as tech_count,
                (COALESCE(csos.created_staff_orders, 0) + COALESCE(csent.sent_staff_orders, 0)) as staff_count,
                (COALESCE(ccs.created_conn_active, 0) + COALESCE(csent.sent_conn_active, 0) + 
                 COALESCE(cts.created_tech_active, 0) + COALESCE(csent.sent_tech_active, 0) +
                 COALESCE(csos.created_staff_active, 0) + COALESCE(csent.sent_staff_active, 0)) as active_count,
                -- New detailed counts
                COALESCE(ccs.assigned_conn_orders, 0) as assigned_conn_count,
                COALESCE(ccs.created_conn_orders, 0) as created_conn_count,
                COALESCE(cts.created_tech_orders, 0) as created_tech_count,
                COALESCE(cts.assigned_tech_orders, 0) as assigned_tech_count,
                -- Staff orders they created and assigned
                COALESCE(csos.created_staff_orders, 0) as created_staff_count,
                COALESCE(csos.assigned_staff_orders, 0) as assigned_staff_count,
                -- Orders they sent
                COALESCE(csent.sent_conn_orders, 0) as sent_conn_count,
                COALESCE(csent.sent_tech_orders, 0) as sent_tech_count,
                COALESCE(csent.sent_staff_orders, 0) as sent_staff_count,
                -- Technician uchun completed (controllerlar uchun 0)
                0 as tech_assigned_conn,
                0 as completed_conn_count,
                0 as tech_assigned_tech,
                0 as completed_tech_count,
                0 as tech_assigned_staff,
                0 as completed_staff_count
            FROM controller_connection_stats ccs
            LEFT JOIN controller_technician_stats cts ON cts.id = ccs.id
            LEFT JOIN controller_staff_orders_stats csos ON csos.id = ccs.id
            LEFT JOIN controller_sent_orders_stats csent ON csent.id = ccs.id
            
            UNION ALL
            
            SELECT
                ts.id,
                ts.full_name,
                ts.phone,
                ts.role,
                ts.created_at,
                (COALESCE(ts.assigned_conn_count, 0) + COALESCE(ts.assigned_tech_count, 0) + COALESCE(ts.assigned_staff_count, 0)) as total_orders,
                0 as conn_count,
                0 as tech_count,
                0 as staff_count,
                (COALESCE(ts.assigned_conn_count, 0) - COALESCE(ts.completed_conn_count, 0) +
                 COALESCE(ts.assigned_tech_count, 0) - COALESCE(ts.completed_tech_count, 0) +
                 COALESCE(ts.assigned_staff_count, 0) - COALESCE(ts.completed_staff_count, 0)) as active_count,
                0 as assigned_conn_count,
                0 as created_conn_count,
                0 as created_tech_count,
                0 as assigned_tech_count,
                0 as created_staff_count,
                0 as assigned_staff_count,
                0 as sent_conn_count,
                0 as sent_tech_count,
                0 as sent_staff_count,
                -- Technician ma'lumotlar - assigned
                COALESCE(ts.assigned_conn_count, 0) as tech_assigned_conn,
                COALESCE(ts.completed_conn_count, 0) as completed_conn_count,
                COALESCE(ts.assigned_tech_count, 0) as tech_assigned_tech,
                COALESCE(ts.completed_tech_count, 0) as completed_tech_count,
                COALESCE(ts.assigned_staff_count, 0) as tech_assigned_staff,
                COALESCE(ts.completed_staff_count, 0) as completed_staff_count
            FROM technician_stats ts
            
            ORDER BY role, total_orders DESC, full_name
            """
        else:
            # Vaqt filtri bilan query
            if time_filter == "today":
                time_condition = "created_at >= CURRENT_DATE"
            elif time_filter == "7days":
                time_condition = "created_at >= CURRENT_DATE - INTERVAL '7 days'"
            elif time_filter == "month":
                time_condition = "created_at >= CURRENT_DATE - INTERVAL '30 days'"
            else:
                time_condition = "TRUE"
            
            query = f"""
            WITH last_conn_assign AS (
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
            controller_connection_stats AS (
                SELECT
                    u.id,
                    u.full_name,
                    u.phone,
                    u.role,
                    u.created_at,
                    -- Orders they created (as user_id) - Connection orders (all statuses for count)
                    COUNT(DISTINCT CASE WHEN co.user_id = u.id THEN co.id END) as created_conn_orders,
                    COUNT(DISTINCT CASE WHEN co.user_id = u.id AND co.status NOT IN ('cancelled', 'completed') THEN co.id END) as created_conn_active,
                    -- Orders assigned to them through workflow (as recipient) - ALL statuses including completed
                    COUNT(DISTINCT CASE WHEN c.recipient_id = u.id AND c.recipient_status = 'in_controller' THEN co.id END) as assigned_conn_orders,
                    COUNT(DISTINCT CASE WHEN c.recipient_id = u.id AND c.recipient_status = 'in_controller' AND co.status NOT IN ('cancelled', 'completed') THEN co.id END) as assigned_conn_active
                FROM users u
                LEFT JOIN connection_orders co ON COALESCE(co.is_active, TRUE) = TRUE
                    AND co.{time_condition}
                LEFT JOIN connections c ON c.application_number = co.application_number
                WHERE u.role IN ('controller')
                GROUP BY u.id, u.full_name, u.phone, u.role, u.created_at
            ),
            controller_technician_stats AS (
                SELECT
                    u.id,
                    -- Orders they created (as user_id) - Technician orders (all statuses for count)
                    COUNT(DISTINCT CASE WHEN tech_orders.user_id = u.id THEN tech_orders.id END) as created_tech_orders,
                    COUNT(DISTINCT CASE WHEN tech_orders.user_id = u.id AND tech_orders.status NOT IN ('cancelled', 'completed') THEN tech_orders.id END) as created_tech_active,
                    -- Orders assigned to them through workflow (as recipient) - ALL statuses including completed
                    COUNT(DISTINCT CASE WHEN c.recipient_id = u.id AND c.recipient_status = 'in_controller' THEN tech_orders.id END) as assigned_tech_orders,
                    COUNT(DISTINCT CASE WHEN c.recipient_id = u.id AND c.recipient_status = 'in_controller' AND tech_orders.status NOT IN ('cancelled', 'completed') THEN tech_orders.id END) as assigned_tech_active
                FROM users u
                LEFT JOIN technician_orders tech_orders ON COALESCE(tech_orders.is_active, TRUE) = TRUE
                    AND tech_orders.{time_condition}
                LEFT JOIN connections c ON c.application_number = tech_orders.application_number
                WHERE u.role = 'controller'
                GROUP BY u.id
            ),
            controller_staff_orders_stats AS (
                SELECT
                    u.id,
                    -- Orders they created (as user_id) - Staff orders (all statuses)
                    COUNT(DISTINCT CASE WHEN so.user_id = u.id THEN so.id END) as created_staff_orders,
                    COUNT(DISTINCT CASE WHEN so.user_id = u.id AND so.status NOT IN ('cancelled', 'completed') THEN so.id END) as created_staff_active,
                    -- Orders assigned to them through workflow (as recipient) - ALL statuses including completed
                    COUNT(DISTINCT CASE WHEN c.recipient_id = u.id AND c.recipient_status = 'in_controller' THEN so.id END) as assigned_staff_orders,
                    COUNT(DISTINCT CASE WHEN c.recipient_id = u.id AND c.recipient_status = 'in_controller' AND so.status NOT IN ('cancelled', 'completed') THEN so.id END) as assigned_staff_active
                FROM users u
                LEFT JOIN staff_orders so ON COALESCE(so.is_active, TRUE) = TRUE
                    AND so.{time_condition}
                LEFT JOIN connections c ON c.application_number = so.application_number
                WHERE u.role = 'controller'
                GROUP BY u.id
            ),
            controller_sent_orders_stats AS (
                SELECT
                    u.id,
                    -- Orders they sent (as sender_id) - Through connections table (all statuses)
                    COUNT(DISTINCT CASE WHEN c.sender_id = u.id THEN co.id END) as sent_conn_orders,
                    COUNT(DISTINCT CASE WHEN c.sender_id = u.id AND co.status NOT IN ('cancelled', 'completed') THEN co.id END) as sent_conn_active,
                    COUNT(DISTINCT CASE WHEN c.sender_id = u.id THEN tech_orders.id END) as sent_tech_orders,
                    COUNT(DISTINCT CASE WHEN c.sender_id = u.id AND tech_orders.status NOT IN ('cancelled', 'completed') THEN tech_orders.id END) as sent_tech_active,
                    COUNT(DISTINCT CASE WHEN c.sender_id = u.id THEN so.id END) as sent_staff_orders,
                    COUNT(DISTINCT CASE WHEN c.sender_id = u.id AND so.status NOT IN ('cancelled', 'completed') THEN so.id END) as sent_staff_active
                FROM users u
                LEFT JOIN connections c ON c.sender_id = u.id
                LEFT JOIN connection_orders co ON co.application_number = c.application_number AND co.{time_condition}
                LEFT JOIN technician_orders tech_orders ON tech_orders.application_number = c.application_number AND tech_orders.{time_condition}
                LEFT JOIN staff_orders so ON so.application_number = c.application_number AND so.{time_condition}
                WHERE u.role = 'controller'
                GROUP BY u.id
            ),
            last_assign_for_tech AS (
                -- Get latest connection status for each application_number
                SELECT DISTINCT ON (c.application_number)
                       c.application_number,
                       c.recipient_id,
                       c.recipient_status
                FROM connections c
                WHERE c.application_number IS NOT NULL
                ORDER BY c.application_number, c.created_at DESC
            ),
            technician_stats AS (
                SELECT
                    u.id,
                    u.full_name,
                    u.phone,
                    u.role,
                    u.created_at,
                    -- Ulanish arizalari uchun (Texnikka kelgan va yopilgan) - using latest assignment
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND co.id IS NOT NULL THEN co.id END) as assigned_conn_count,
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND co.status = 'completed' THEN co.id END) as completed_conn_count,
                    -- Texnik xizmat arizalari uchun (Texnikka kelgan va yopilgan) - using latest assignment
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND tech_orders.id IS NOT NULL THEN tech_orders.id END) as assigned_tech_count,
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND tech_orders.status = 'completed' THEN tech_orders.id END) as completed_tech_count,
                    -- Xodim yaratgan arizalar uchun (Texnikka kelgan va yopilgan) - using latest assignment
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND so.id IS NOT NULL THEN so.id END) as assigned_staff_count,
                    COUNT(DISTINCT CASE WHEN la.recipient_id = u.id AND so.status = 'completed' THEN so.id END) as completed_staff_count
                FROM users u
                LEFT JOIN last_assign_for_tech la ON la.recipient_id = u.id
                LEFT JOIN connection_orders co ON co.application_number = la.application_number 
                    AND COALESCE(co.is_active, TRUE) = TRUE 
                    AND co.{time_condition}
                LEFT JOIN technician_orders tech_orders ON tech_orders.application_number = la.application_number 
                    AND COALESCE(tech_orders.is_active, TRUE) = TRUE 
                    AND tech_orders.{time_condition}
                LEFT JOIN staff_orders so ON so.application_number = la.application_number 
                    AND COALESCE(so.is_active, TRUE) = TRUE 
                    AND so.{time_condition}
                WHERE u.role = 'technician'
                  AND COALESCE(u.is_blocked, FALSE) = FALSE
                GROUP BY u.id, u.full_name, u.phone, u.role, u.created_at
            )
            SELECT
                ccs.id,
                ccs.full_name,
                ccs.phone,
                ccs.role,
                ccs.created_at,
                (COALESCE(ccs.created_conn_orders, 0) + COALESCE(csent.sent_conn_orders, 0) + 
                 COALESCE(cts.created_tech_orders, 0) + COALESCE(csent.sent_tech_orders, 0) +
                 COALESCE(csos.created_staff_orders, 0) + COALESCE(csent.sent_staff_orders, 0)) as total_orders,
                (COALESCE(ccs.created_conn_orders, 0) + COALESCE(csent.sent_conn_orders, 0)) as conn_count,
                (COALESCE(cts.created_tech_orders, 0) + COALESCE(csent.sent_tech_orders, 0)) as tech_count,
                (COALESCE(csos.created_staff_orders, 0) + COALESCE(csent.sent_staff_orders, 0)) as staff_count,
                (COALESCE(ccs.created_conn_active, 0) + COALESCE(csent.sent_conn_active, 0) + 
                 COALESCE(cts.created_tech_active, 0) + COALESCE(csent.sent_tech_active, 0) +
                 COALESCE(csos.created_staff_active, 0) + COALESCE(csent.sent_staff_active, 0)) as active_count,
                -- New detailed counts
                COALESCE(ccs.assigned_conn_orders, 0) as assigned_conn_count,
                COALESCE(ccs.created_conn_orders, 0) as created_conn_count,
                COALESCE(cts.created_tech_orders, 0) as created_tech_count,
                COALESCE(cts.assigned_tech_orders, 0) as assigned_tech_count,
                -- Staff orders they created and assigned
                COALESCE(csos.created_staff_orders, 0) as created_staff_count,
                COALESCE(csos.assigned_staff_orders, 0) as assigned_staff_count,
                -- Orders they sent
                COALESCE(csent.sent_conn_orders, 0) as sent_conn_count,
                COALESCE(csent.sent_tech_orders, 0) as sent_tech_count,
                COALESCE(csent.sent_staff_orders, 0) as sent_staff_count,
                -- Technician uchun completed (controllerlar uchun 0)
                0 as tech_assigned_conn,
                0 as completed_conn_count,
                0 as tech_assigned_tech,
                0 as completed_tech_count,
                0 as tech_assigned_staff,
                0 as completed_staff_count
            FROM controller_connection_stats ccs
            LEFT JOIN controller_technician_stats cts ON cts.id = ccs.id
            LEFT JOIN controller_staff_orders_stats csos ON csos.id = ccs.id
            LEFT JOIN controller_sent_orders_stats csent ON csent.id = ccs.id
            
            UNION ALL
            
            SELECT
                ts.id,
                ts.full_name,
                ts.phone,
                ts.role,
                ts.created_at,
                (COALESCE(ts.assigned_conn_count, 0) + COALESCE(ts.assigned_tech_count, 0) + COALESCE(ts.assigned_staff_count, 0)) as total_orders,
                0 as conn_count,
                0 as tech_count,
                0 as staff_count,
                (COALESCE(ts.assigned_conn_count, 0) - COALESCE(ts.completed_conn_count, 0) +
                 COALESCE(ts.assigned_tech_count, 0) - COALESCE(ts.completed_tech_count, 0) +
                 COALESCE(ts.assigned_staff_count, 0) - COALESCE(ts.completed_staff_count, 0)) as active_count,
                0 as assigned_conn_count,
                0 as created_conn_count,
                0 as created_tech_count,
                0 as assigned_tech_count,
                0 as created_staff_count,
                0 as assigned_staff_count,
                0 as sent_conn_count,
                0 as sent_tech_count,
                0 as sent_staff_count,
                -- Technician ma'lumotlar - assigned
                COALESCE(ts.assigned_conn_count, 0) as tech_assigned_conn,
                COALESCE(ts.completed_conn_count, 0) as completed_conn_count,
                COALESCE(ts.assigned_tech_count, 0) as tech_assigned_tech,
                COALESCE(ts.completed_tech_count, 0) as completed_tech_count,
                COALESCE(ts.assigned_staff_count, 0) as tech_assigned_staff,
                COALESCE(ts.completed_staff_count, 0) as completed_staff_count
            FROM technician_stats ts
            
            ORDER BY role, total_orders DESC, full_name
            """
        
        rows = await conn.fetch(query)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# =========================================================
#  Load calculation functions
# =========================================================

async def get_ccs_supervisors_with_load() -> List[Dict[str, Any]]:
    """
    CCS Supervisorlar ro'yxatini yuklama bilan olish.
    Yangi.sql ma'lumotlari bilan moslashtirilgan.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                u.id,
                u.full_name,
                u.telegram_id,
                u.language,
                COALESCE(
                    (SELECT COUNT(*)
                     FROM connections c
                     WHERE c.recipient_id = u.id
                       AND c.recipient_status = 'in_call_center_supervisor'
                       AND (
                           EXISTS (SELECT 1 FROM connection_orders co WHERE co.application_number = c.application_number AND co.status = 'in_junior_manager' AND COALESCE(co.is_active, TRUE) = TRUE)
                           OR
                           EXISTS (SELECT 1 FROM technician_orders tech_ord WHERE tech_ord.application_number = c.application_number AND tech_ord.status = 'in_call_center_supervisor' AND COALESCE(tech_ord.is_active, TRUE) = TRUE)
                           OR
                           EXISTS (SELECT 1 FROM staff_orders so WHERE so.application_number = c.application_number AND so.status = 'in_call_center_supervisor' AND COALESCE(so.is_active, TRUE) = TRUE)
                       )
                    ), 0
                ) AS load_count
            FROM users u
            WHERE u.role = 'callcenter_supervisor'
              AND u.is_blocked = FALSE
            ORDER BY load_count ASC, u.full_name ASC
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def list_controller_orders_by_status(status: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Controller orders ro'yxatini status bo'yicha olish.
    Faqat texnik xizmat arizalari (type_of_zayavka = 'technician').
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
                creator.full_name as staff_name,
                creator.phone as staff_phone,
                creator.role as staff_role
            FROM staff_orders so
            JOIN last_assign la ON la.application_number = so.application_number
            LEFT JOIN users u ON u.id = so.user_id
            LEFT JOIN tarif t ON t.id = so.tarif_id
            LEFT JOIN users creator ON creator.id = so.user_id
            WHERE la.recipient_status = $1
              AND so.status = $1
              AND so.type_of_zayavka = 'technician'
              AND COALESCE(so.is_active, TRUE) = TRUE
            ORDER BY so.created_at DESC
            LIMIT $2
            """,
            status, limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def get_controller_statistics() -> Dict[str, Any]:
    """
    Controller uchun statistika olish.
    Faqat texnik xizmat arizalari (type_of_zayavka = 'technician').
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
                COUNT(CASE WHEN so.status = 'cancelled' THEN 1 END) as cancelled
            FROM staff_orders so
            JOIN last_assign la ON la.application_number = so.application_number
            WHERE la.recipient_status IN ('in_controller', 'between_controller_technician', 'in_technician')
              AND so.type_of_zayavka = 'technician'
              AND COALESCE(so.is_active, TRUE) = TRUE
            """
        )
        return dict(stats) if stats else {}
    finally:
        await conn.close()
