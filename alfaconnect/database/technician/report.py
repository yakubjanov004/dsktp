# database/technician/report.py
from typing import Dict, Optional, Tuple
import asyncpg
from config import settings

# ---------------- DB helpers ----------------
async def _conn():
    return await asyncpg.connect(settings.DB_URL)

async def _pick_column(conn, table: str, candidates: list[str]) -> Optional[str]:
    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = $1
        """,
        table,
    )
    cols = {r["column_name"] for r in rows}
    for c in candidates:
        if c in cols:
            return c
    return None

async def _detect_columns_for_kind(kind: str) -> Tuple[str, str]:
    """
    kind ∈ {'connection','technician','staff'}
    Qaytaradi: (order_id_col, date_col)
      - order_id_col: connections dagi shu turga mos ID ustuni
      - date_col: updated_at bo'lsa o'sha, bo'lmasa created_at
    """
    conn = await _conn()
    try:
        if kind == "connection":
            # sizda connection_id (typo) mavjud — birinchi bo'lib shuni tanlaymiz
            order_col = await _pick_column(conn, "connections", ["connection_id", "connection_id"])
            if not order_col:
                raise RuntimeError("[connections] connection_id/connection_id topilmadi")
        elif kind == "technician":
            # technician_orders.id ga bog'lanadigan ustun nomi sxemaga ko'ra farq qilishi mumkin
            order_col = await _pick_column(conn, "connections", ["technician_id", "technician_order_id", "tech_order_id"])
            if not order_col:
                raise RuntimeError("[connections] technician_order_id (technician_id/...) topilmadi")
        elif kind == "staff":
            order_col = await _pick_column(conn, "connections", ["staff_id"])
            if not order_col:
                raise RuntimeError("[connections] staff_id ustuni topilmadi")
        else:
            raise ValueError("kind must be connection|technician|staff")

        date_col = await _pick_column(conn, "connections", ["updated_at", "created_at"])
        if not date_col:
            raise RuntimeError("[connections] updated_at/created_at topilmadi")
        return order_col, date_col
    finally:
        await conn.close()

# -------------- Core counter (FAQAT connections) --------------
async def _count_from_connections_by_status(
    *,
    user_id: int,           # users.id (bot foydalanuvchisi)
    kind: str,              # 'connection' | 'technician' | 'staff'
    date_from,              # tz-aware UTC yoki None
    date_to,                # tz-aware UTC yoki None
) -> Dict[str, int]:
    """
    - Faqat connections'dan oladi.
    - Foydalanuvchi texnik sifatida qatnashgan yozuvlar (sender_id=USER yoki recipient_id=USER).
    - Texnikning ko'rinadigan statusi (tech_status) quyidagicha:
        * Agar ikkala tomonda ham foydalanuvchi bo'lsa, PRIORITET bilan tanlanadi:
          completed > in_warehouse > in_technician_work > in_technician > between_*
        * Aks holda, foydalanuvchi turgan tomondagi status olinadi
          (between_* normallashtiriladi).
    - Har bir ORDER uchun eng so'nggi yozuv olinadi (DISTINCT ON (order_id) by {date_col} DESC, id DESC).
    - Sana filtri ixtiyoriy: date_from/date_to None bo'lsa, filter qo'llanmaydi.
    """
    order_id_col, date_col = await _detect_columns_for_kind(kind)

    # Order table nomini aniqlash
    if kind == "connection":
        order_table = "connection_orders"
        order_status_col = "status"
    elif kind == "technician":
        order_table = "technician_orders"
        order_status_col = "status"
    elif kind == "staff":
        order_table = "staff_orders"
        order_status_col = "status"
    
    q = f"""
    WITH involvement AS (
        SELECT
            c.{order_id_col} AS order_id,
            c.{date_col}     AS ts,
            /* texnikka tegishli statusni hisoblash
               faqat quyidagi ro'yxatdagilar qiziq:
               between_controller_technician | in_between_controller_technician
               in_technician | in_technician_work | in_warehouse | completed
            */
            CASE
                /* Ikkala tomonda ham foydalanuvchi */
                WHEN c.sender_id = $1 AND c.recipient_id = $1 THEN
                    CASE
                        WHEN c.sender_status    = 'completed' OR c.recipient_status = 'completed'
                            THEN 'completed'
                        WHEN c.sender_status    = 'in_warehouse' OR c.recipient_status = 'in_warehouse'
                            THEN 'in_warehouse'
                        WHEN c.sender_status    = 'in_technician_work' OR c.recipient_status = 'in_technician_work'
                            THEN 'in_technician_work'
                        WHEN c.sender_status    = 'in_technician' OR c.recipient_status = 'in_technician'
                            THEN 'in_technician'
                        WHEN (c.sender_status IN ('between_controller_technician','in_between_controller_technician'))
                          OR (c.recipient_status IN ('between_controller_technician','in_between_controller_technician'))
                            THEN 'between_controller_technician'
                        ELSE NULL
                    END

                /* Faqat sender tomonda foydalanuvchi */
                WHEN c.sender_id = $1 THEN
                    CASE
                        WHEN c.sender_status IN ('between_controller_technician','in_between_controller_technician')
                            THEN 'between_controller_technician'
                        WHEN c.sender_status IN ('in_technician','in_technician_work','in_warehouse','completed')
                            THEN c.sender_status
                        ELSE NULL
                    END

                /* Faqat recipient tomonda foydalanuvchi */
                WHEN c.recipient_id = $1 THEN
                    CASE
                        WHEN c.recipient_status IN ('between_controller_technician','in_between_controller_technician')
                            THEN 'between_controller_technician'
                        WHEN c.recipient_status IN ('in_technician','in_technician_work','in_warehouse','completed')
                            THEN c.recipient_status
                        ELSE NULL
                    END
                ELSE NULL
            END AS tech_status,
            c.id,
            o.{order_status_col} AS order_status
        FROM connections c
        LEFT JOIN {order_table} o ON o.id = c.{order_id_col}
        WHERE c.{order_id_col} IS NOT NULL
          AND ($2::timestamptz IS NULL OR c.{date_col} >= $2)
          AND ($3::timestamptz IS NULL OR c.{date_col} <  $3)
          AND (c.sender_id = $1 OR c.recipient_id = $1)
    ),
    last_per_order AS (
        SELECT DISTINCT ON (order_id)
            order_id, tech_status, order_status, ts, id
        FROM involvement
        WHERE order_id IS NOT NULL AND tech_status IS NOT NULL
        ORDER BY order_id, ts DESC, id DESC
    )
    SELECT
        CASE
            -- Arizaning o'z statusi completed bo'lsa
            WHEN order_status = 'completed' THEN 'completed'
            -- Arizaning o'z statusi cancelled bo'lsa
            WHEN order_status = 'cancelled' THEN 'cancelled'
            -- Arizaning o'z statusi boshqa bo'lsa, connection statusini ishlat
            WHEN tech_status IN ('between_controller_technician','in_between_controller_technician') THEN 'between_controller_technician'
            WHEN tech_status = 'in_technician'       THEN 'in_technician'
            WHEN tech_status = 'in_technician_work'  THEN 'in_technician_work'
            WHEN tech_status = 'in_warehouse'        THEN 'in_warehouse'
            ELSE 'other'
        END AS status,
        COUNT(*)::int AS cnt
    FROM last_per_order
    GROUP BY 1
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(q, user_id, date_from, date_to)
        return {r["status"]: int(r["cnt"]) for r in rows}
    finally:
        await conn.close()

# -------------- Public API --------------
async def count_connection_status(user_id: int, date_from, date_to) -> Dict[str, int]:
    return await _count_from_connections_by_status(user_id=user_id, kind="connection",  date_from=date_from, date_to=date_to)

async def count_technician_status(user_id: int, date_from, date_to) -> Dict[str, int]:
    return await _count_from_connections_by_status(user_id=user_id, kind="technician", date_from=date_from, date_to=date_to)

async def count_staff_status(user_id: int, date_from, date_to) -> Dict[str, int]:
    return await _count_from_connections_by_status(user_id=user_id, kind="staff",       date_from=date_from, date_to=date_to)
