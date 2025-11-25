# database/manager/queries.py
# Manager roli uchun asosiy queries (inbox)

import asyncpg
from typing import List, Dict, Any, Optional
from config import settings

# Umumiy user funksiyalarini import qilamiz
from database.basic.user import get_user_by_telegram_id, get_users_by_role

# =========================================================
#  Manager Inbox bilan ishlash
# =========================================================

async def fetch_manager_inbox(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Manager ko'rishi uchun inbox arizalari.
    Statusi 'in_manager' bo'lgan arizalar.
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
                co.created_at,
                co.updated_at,
                u.full_name AS client_name,
                u.phone      AS client_phone,
                t.name       AS tariff
            FROM connection_orders co
            LEFT JOIN users u ON u.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            WHERE co.is_active = TRUE
              AND co.status IN ('in_manager')
            ORDER BY co.created_at DESC, co.id DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def count_manager_inbox() -> int:
    """
    Manager inboxdagi arizalar soni.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
              FROM connection_orders co
             WHERE co.is_active = TRUE
               AND co.status IN ('in_manager')
            """
        )
    finally:
        await conn.close()

async def assign_to_junior_manager(request_id: int | str, jm_id: int, actor_id: int, bot=None) -> Dict[str, Any]:
    """
    Manager -> Junior Manager:
      1) connection_orders.status: old -> 'in_junior_manager'
      2) connections: HAR DOIM yangi qator INSERT
         sender_id=manager(actor_id), recipient_id=jm_id,
         sender_status=old_status, recipient_status=new_status
      3) Junior Manager'ga notification yuboradi
    
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
            # JM mavjudmi? + uning ma'lumotlarini olamiz
            jm_info = await conn.fetchrow(
                "SELECT id, telegram_id, language, full_name FROM users WHERE id = $1 AND role = 'junior_manager'",
                jm_id,
            )
            if not jm_info:
                raise ValueError("Junior manager topilmadi")

            # 1) Eski statusni va application_number'ni lock bilan o'qiymiz
            row_old = await conn.fetchrow(
                """
                SELECT status, application_number, user_id
                  FROM connection_orders
                 WHERE id = $1
                 FOR UPDATE
                """,
                request_id_int
            )
            if not row_old:
                raise ValueError("Ariza topilmadi")

            old_status: str = row_old["status"]
            app_number: str = row_old["application_number"]
            creator_id: Optional[int] = row_old["user_id"]

            # 2) Yangi statusga o'tkazamiz
            row_new = await conn.fetchrow(
                """
                UPDATE connection_orders
                   SET status     = 'in_junior_manager'::connection_order_status,
                       updated_at = NOW()
                 WHERE id = $1
             RETURNING status
                """,
                request_id_int
            )
            new_status: str = row_new["status"]  # 'in_junior_manager'

            # 3) TARIX: HAR DOIM YANGI QATOR KIRITAMIZ
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
                    $1, $2, $3, $4::connection_order_status, $5::connection_order_status, NOW(), NOW()
                )
                """,
                app_number,
                actor_id,          # manager
                jm_id,             # junior manager
                old_status,        # masalan: 'in_manager' yoki 'new'
                new_status         # 'in_junior_manager'
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
                LEFT JOIN connection_orders co ON co.application_number = la.application_number AND COALESCE(co.is_active, TRUE) AND co.status = 'in_junior_manager'
                LEFT JOIN staff_orders so ON so.application_number = la.application_number AND COALESCE(so.is_active, TRUE) AND so.status = 'in_junior_manager'
                WHERE la.recipient_id = $1
                  AND la.recipient_status = 'in_junior_manager'
                  AND (co.id IS NOT NULL OR so.id IS NOT NULL)
                """,
                jm_id
            )
            
            return {
                "telegram_id": jm_info["telegram_id"],
                "language": jm_info["language"] or "uz",
                "application_number": app_number,
                "current_load": current_load or 0,
                "jm_name": jm_info["full_name"] or "Noma'lum",
                # for notifications helper
                "recipient_id": jm_info["id"],
                "recipient_role": "junior_manager",
                "sender_id": actor_id,
                "sender_role": "manager",
                "creator_id": creator_id,
                "order_type": "connection",
            }
    finally:
        await conn.close()

async def get_juniors_with_load_via_history() -> List[Dict[str, Any]]:
    """
    Junior managerlarni hozirgi yuklamasi (ochiq arizalar soni) bilan olish.
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
            ),
            workloads AS (
                SELECT
                    la.recipient_id AS jm_id,
                    COUNT(*) AS cnt
                FROM last_assign la
                JOIN connection_orders co
                  ON co.application_number = la.application_number
                WHERE co.is_active = TRUE
                  AND co.status = 'in_junior_manager'
                  AND la.recipient_status = 'in_junior_manager'
                GROUP BY la.recipient_id
            )
            SELECT 
                u.id,
                u.full_name,
                u.username,
                u.phone,
                u.telegram_id,
                COALESCE(w.cnt, 0) AS load_count
            FROM users u
            LEFT JOIN workloads w ON w.jm_id = u.id
            WHERE u.role = 'junior_manager'
              AND COALESCE(u.is_blocked, FALSE) = FALSE
            ORDER BY u.full_name NULLS LAST, u.id
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# =========================================================
#  Manager Inbox Staff Orders bilan ishlash
# =========================================================

async def fetch_manager_inbox_staff(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Manager ko'rishi uchun staff_orders inbox arizalari.
    Statusi 'in_manager' bo'lgan staff_orders arizalar.
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
                so.type_of_zayavka AS req_type,
                so.description,
                so.created_at,
                so.updated_at,

                st.full_name  AS staff_name,
                st.phone      AS staff_phone,
                st.role       AS staff_role,

                ab.full_name  AS client_name,
                ab.phone      AS client_phone,

                t.name        AS tariff
            FROM staff_orders AS so
            LEFT JOIN users st ON st.id = so.user_id::bigint
            LEFT JOIN users ab ON ab.id = so.abonent_id::bigint
            LEFT JOIN tarif  t ON t.id  = so.tarif_id::bigint
            WHERE COALESCE(so.is_active, TRUE) = TRUE
              AND so.status = 'in_manager'
            ORDER BY so.created_at DESC, so.id DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def count_manager_inbox_staff() -> int:
    """
    Manager inboxdagi staff_orders arizalar soni.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
              FROM staff_orders so
             WHERE COALESCE(so.is_active, TRUE) = TRUE
               AND so.status = 'in_manager'
            """
        )
    finally:
        await conn.close()

async def assign_to_junior_manager_for_staff(request_id: int | str, jm_id: int, actor_id: int) -> None:
    """
    Manager -> Junior Manager: Staff Orders uchun
      1) staff_orders.status: old -> 'in_junior_manager'
      2) connections: HAR DOIM yangi qator INSERT
         sender_id=manager(actor_id), recipient_id=jm_id,
         sender_status=old_status, recipient_status=new_status
    """
    # '8_2025' kabi bo'lsa ham 8 ni olamiz
    try:
        request_id_int = int(str(request_id).split("_")[0])
    except Exception:
        request_id_int = int(request_id)

    conn = await asyncpg.connect(settings.DB_URL)
    try:
        async with conn.transaction():
            # JM mavjudmi?
            jm_exists = await conn.fetchval(
                "SELECT 1 FROM users WHERE id = $1 AND role = 'junior_manager'",
                jm_id,
            )
            if not jm_exists:
                raise ValueError("Junior manager topilmadi")

            # 1) Eski statusni va application_number ni lock bilan o'qiymiz
            row_old = await conn.fetchrow(
                """
                SELECT status, application_number
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

            # 2) Yangi statusga o'tkazamiz
            row_new = await conn.fetchrow(
                """
                UPDATE staff_orders
                   SET status     = 'in_junior_manager',
                       updated_at = NOW()
                 WHERE id = $1
             RETURNING status
                """,
                request_id_int
            )
            new_status: str = row_new["status"]  # 'in_junior_manager'

            # 3) TARIX: HAR DOIM YANGI QATOR KIRITAMIZ
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
                app_number,
                actor_id,          # manager
                jm_id,             # junior manager
                old_status,        # masalan: 'in_manager'
                new_status         # 'in_junior_manager'
            )
    finally:
        await conn.close()

async def assign_to_controller_for_staff(request_id: int | str, controller_id: int, actor_id: int) -> Dict[str, Any]:
    """
    Manager -> Controller (staff_orders uchun):
      1) staff_orders.status: old -> 'in_controller'
      2) connections: HAR DOIM yangi qator INSERT
         sender_id=manager(actor_id), recipient_id=controller_id,
         sender_status=old_status, recipient_status=new_status
      3) Controller'ga notification yuboradi
    
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
            # Controller mavjudmi? + uning ma'lumotlarini olamiz
            controller_info = await conn.fetchrow(
                "SELECT id, telegram_id, language FROM users WHERE id = $1 AND role = 'controller'",
                controller_id,
            )
            if not controller_info:
                raise ValueError("Controller topilmadi")

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
                   SET status     = 'in_controller',
                       updated_at = NOW()
                 WHERE id = $1
             RETURNING status
                """,
                request_id_int
            )
            new_status: str = row_new["status"]  # 'in_controller'

            # 3) Connections yozamiz - Manager -> Controller
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
                app_number,
                actor_id,          # manager
                controller_id,      # controller
                old_status,        # masalan: 'in_manager'
                new_status         # 'in_controller'
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
                LEFT JOIN connection_orders co ON co.application_number = la.application_number AND COALESCE(co.is_active, TRUE) AND co.status = 'in_controller'
                LEFT JOIN staff_orders so ON so.application_number = la.application_number AND COALESCE(so.is_active, TRUE) AND so.status = 'in_controller'
                WHERE la.recipient_id = $1
                  AND la.recipient_status = 'in_controller'
                  AND (co.id IS NOT NULL OR so.id IS NOT NULL)
                """,
                controller_id
            )
            
            return {
                "telegram_id": controller_info["telegram_id"],
                "language": controller_info["language"] or "uz",
                "application_number": app_number,
                "order_type": order_type,
                "current_load": current_load or 0,
                # for notifications helper
                "recipient_id": controller_info["id"],
                "recipient_role": "controller",
                "sender_id": actor_id,
                "sender_role": "manager",
                # self-created check
                "creator_id": None,
            }
    finally:
        await conn.close()

async def get_controllers_with_load_via_history() -> List[Dict[str, Any]]:
    """
    Controllerlarni hozirgi yuklamasi (ochiq staff arizalar soni) bilan olish.
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
            ),
            workloads AS (
                SELECT
                    la.recipient_id AS controller_id,
                    COUNT(*) AS cnt
                FROM last_assign la
                JOIN staff_orders so
                  ON so.application_number = la.application_number
                WHERE COALESCE(so.is_active, TRUE) = TRUE
                  AND so.status = 'in_controller'
                  AND la.recipient_status = 'in_controller'
                GROUP BY la.recipient_id
            )
            SELECT 
                u.id,
                u.full_name,
                u.username,
                u.phone,
                u.telegram_id,
                COALESCE(w.cnt, 0) AS load_count
            FROM users u
            LEFT JOIN workloads w ON w.controller_id = u.id
            WHERE u.role = 'controller'
              AND COALESCE(u.is_blocked, FALSE) = FALSE
            ORDER BY u.full_name NULLS LAST, u.id
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()