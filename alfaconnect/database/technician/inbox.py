# database/technician/inbox.py
import asyncpg
from typing import List, Dict, Any, Optional
from config import settings


# ----------------- YORDAMCHI -----------------
async def _conn():
    return await asyncpg.connect(settings.DB_URL)

def _as_dicts(rows):
    return [dict(r) for r in rows]


# ======================= INBOX: CONNECTION_ORDERS =======================
async def fetch_technician_inbox(
    technician_user_id: Optional[int] = None,
    *,
    technician_id: Optional[int] = None,   # alias
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Connection orders: oxirgi biriktirish (connections) bo'yicha texnikka tegishli faol arizalar.
    E'TIBOR: connections.connection_id (sic) — connection_orders.id ni bildiradi.
    """
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("fetch_technician_inbox(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            WITH last_conn AS (
                SELECT
                    c.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.application_number, c.recipient_id
                        ORDER BY c.created_at DESC, c.id DESC
                    ) AS rn
                FROM connections c
                WHERE c.recipient_id = $1
                  AND c.application_number IS NOT NULL
            )
            SELECT
                co.id,
                co.application_number,
                co.address,
                co.region,
                co.status,
                co.created_at,
                co.jm_notes,
                COALESCE(u.full_name, 'Mijoz') AS client_name,
                COALESCE(u.phone, '-') AS client_phone,
                t.name AS tariff
            FROM last_conn c
            JOIN connection_orders co ON co.application_number = c.application_number
            LEFT JOIN users u ON u.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            WHERE
                c.rn = 1
                AND co.is_active = TRUE
                AND co.status IN (
                    'between_controller_technician'::connection_order_status,
                    'in_technician'::connection_order_status,
                    'in_technician_work'::connection_order_status
                )
            ORDER BY
                CASE co.status
                    WHEN 'between_controller_technician'::connection_order_status THEN 0
                    WHEN 'in_technician'::connection_order_status                 THEN 1
                    WHEN 'in_technician_work'::connection_order_status            THEN 2
                    ELSE 3
                END,
                co.created_at DESC,
                co.id DESC
            LIMIT $2 OFFSET $3
            """,
            uid, limit, offset
        )
        return _as_dicts(rows)
    finally:
        await conn.close()


async def count_technician_inbox(
    technician_user_id: Optional[int] = None,
    *,
    technician_id: Optional[int] = None  # alias
) -> int:
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("count_technician_inbox(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        cnt = await conn.fetchval(
            """
            WITH last_conn AS (
                SELECT
                    c.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.application_number, c.recipient_id
                        ORDER BY c.created_at DESC, c.id DESC
                    ) AS rn
                FROM connections c
                WHERE c.recipient_id = $1
                  AND c.application_number IS NOT NULL
            )
            SELECT COUNT(*)
            FROM last_conn c
            JOIN connection_orders co ON co.application_number = c.application_number
            WHERE
                c.rn = 1
                AND co.is_active = TRUE
                AND co.status IN (
                    'between_controller_technician'::connection_order_status,
                    'in_technician'::connection_order_status,
                    'in_technician_work'::connection_order_status
                )
            """,
            uid
        )
        return int(cnt or 0)
    finally:
        await conn.close()


# ======================= INBOX: TECHNICIAN_ORDERS =======================
async def fetch_technician_inbox_tech(
    technician_user_id: Optional[int] = None,  # eski nom (asosiy)
    *,
    technician_id: Optional[int] = None,       # yangi nom (alias)
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Technician orders: oxirgi biriktirish bo'yicha texnikka tegishli faol arizalar.
    DIQQAT: Ba'zi eski yozuvlarda connections.technician_id NULL, lekin connection_id
    (imlo bilan) ichida technician_orders.id turgan — shu holatni ham qo'llab-quvvatlaymiz.
    """
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("fetch_technician_inbox_tech(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            WITH last_conn AS (
                SELECT
                    c.id,
                    c.application_number,
                    c.recipient_id,
                    c.created_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.application_number, c.recipient_id
                        ORDER BY c.created_at DESC, c.id DESC
                    ) AS rn
                FROM connections c
                WHERE c.recipient_id = $1
                  AND c.application_number IS NOT NULL
            )
            SELECT
                to2.id,
                to2.application_number,
                to2.address,
                to2.region,
                to2.status,
                to2.created_at,
                to2.description,
                to2.description_ish AS diagnostics,
                to2.media AS media_file_id,
                CASE 
                    WHEN to2.media IS NOT NULL THEN 'photo'
                    ELSE NULL
                END AS media_type,
                to2.description_operator,
                to2.description_ish,
                COALESCE(client_user.full_name, user_user.full_name, 'Mijoz') AS client_name,
                COALESCE(client_user.phone, user_user.phone, '-') AS client_phone,
                NULL        AS tariff
            FROM last_conn lc
            JOIN technician_orders to2 ON to2.application_number = lc.application_number
            LEFT JOIN users client_user ON client_user.id::text = to2.abonent_id
            LEFT JOIN users user_user ON user_user.id = to2.user_id
            WHERE
                lc.rn = 1
                AND to2.is_active = TRUE
                AND to2.status IN ('between_controller_technician','in_technician','in_technician_work')
            ORDER BY
                CASE to2.status
                    WHEN 'between_controller_technician' THEN 0
                    WHEN 'in_technician'                 THEN 1
                    WHEN 'in_technician_work'            THEN 2
                    ELSE 3
                END,
                to2.created_at DESC,
                to2.id DESC
            LIMIT $2 OFFSET $3
            """,
            uid, limit, offset
        )
        return _as_dicts(rows)
    finally:
        await conn.close()


# ======================= INBOX: staff_ORDERS =======================
async def fetch_technician_inbox_staff(
    technician_user_id: Optional[int] = None,
    *,
    technician_id: Optional[int] = None,  # alias
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    staff orders: oxirgi biriktirish bo'yicha texnikka tegishli faol arizalar.
    Eslatma: connections.staff_id — staff_orders.id ni bildiradi.
    Filtr: recipient_id = texnik foydalanuvchi.
    """
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("fetch_technician_inbox_staff(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            WITH last_conn AS (
                SELECT
                    c.id,
                    c.application_number,
                    c.recipient_id,
                    c.created_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.application_number, c.recipient_id
                        ORDER BY c.created_at DESC, c.id DESC
                    ) AS rn
                FROM connections c
                WHERE c.recipient_id = $1
                  AND c.application_number IS NOT NULL
            )
            SELECT 
                so.id,
                so.application_number,
                so.phone,
                so.region,
                so.abonent_id,
                so.address,
                so.description,
                so.diagnostics,
                so.status,
                so.created_at,
                so.type_of_zayavka,
                so.jm_notes,
                
                -- Client (abonent) ma'lumotlari
                COALESCE(client_user.full_name, 'Mijoz') AS client_name,
                COALESCE(client_user.phone, so.phone, '-') AS client_phone,
                client_user.telegram_id,
                
                -- Yaratuvchi xodim ma'lumotlari
                creator.full_name AS staff_creator_name,
                creator.phone AS staff_creator_phone,
                creator.role AS staff_creator_role,
                
                -- Tariff yoki muammo
                CASE 
                    WHEN so.type_of_zayavka = 'connection' THEN t.name
                    WHEN so.type_of_zayavka = 'technician' THEN so.description
                    ELSE NULL
                END AS tariff_or_problem,
                
                NULL AS tariff
            FROM last_conn c
            JOIN staff_orders so ON so.application_number = c.application_number
            LEFT JOIN users creator ON creator.id = so.user_id
            LEFT JOIN users client_user ON client_user.id::text = so.abonent_id
            LEFT JOIN tarif t ON t.id = so.tarif_id
            WHERE
                c.rn = 1
                AND so.is_active = TRUE
                AND so.status IN ('between_controller_technician','in_technician','in_technician_work')
            ORDER BY
                CASE so.status
                    WHEN 'between_controller_technician' THEN 0
                    WHEN 'in_technician'                 THEN 1
                    WHEN 'in_technician_work'            THEN 2
                    ELSE 3
                END,
                so.created_at DESC,
                so.id DESC
            LIMIT $2 OFFSET $3
            """,
            uid, limit, offset
        )
        return _as_dicts(rows)
    finally:
        await conn.close()
