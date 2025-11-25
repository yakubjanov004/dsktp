# database/technician/call_center.py
from config import settings  # settings.DB_URL
from typing import List, Dict, Any, Optional, Union
import asyncpg

from database.basic.region import normalize_region_code
from database.basic.phone import normalize_phone

__all__ = ["list_technicians_by_region", "staff_orders_create", "staff_orders_technician_create"]

async def _conn() -> asyncpg.Connection:
    # Endi fallback DSN YO'Q. Faqat settings.DB_URL ishlatiladi.
    return await asyncpg.connect(settings.DB_URL)


async def list_technicians_by_region(region_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Optional helper if you later want region-filtered list.
    Requires a mapping table 'technician_regions(technician_id, region_id)'.
    Adjust query if your schema differs.
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT u.id, u.full_name, u.phone
            FROM users u
            JOIN technician_regions tr ON tr.technician_id = u.id
            WHERE u.role = 'technician'
              AND COALESCE(u.is_blocked, false) = false
              AND tr.region_id = $1
            ORDER BY u.full_name NULLS LAST, u.id
            LIMIT $2
            """,
            region_id, limit,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

  # adjust import if needed

async def staff_orders_create(
    user_id: int,
    phone: Optional[str],
    abonent_id: Optional[str],
    region: Optional[Union[int, str]],
    address: str,
    description: Optional[str],
    business_type: str = "B2C",
    created_by_role: str = "technician",
) -> str:
    conn = await _conn()
    try:
        region_value = normalize_region_code(region) or (str(region).strip() if region is not None else None)
        normalized_phone = normalize_phone(phone) if phone else None
        next_number = await conn.fetchval(
            "SELECT COALESCE(MAX(CAST(SUBSTRING(application_number FROM '\\d+$') AS INTEGER)), 0) + 1 FROM staff_orders WHERE application_number LIKE $1",
            f"STAFF-TECH-{business_type}-%"
        )
        application_number = f"STAFF-TECH-{business_type}-{next_number:04d}"
        row = await conn.fetchrow(
            """
            INSERT INTO staff_orders (
                application_number, user_id, phone, region, abonent_id,
                address, description, business_type, status, type_of_zayavka, is_active, created_by_role, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5,
                    $6, $7, $8, 'in_controller', 'technician', TRUE, $9, NOW(), NOW())
            RETURNING id, application_number
            """,
            application_number,
            user_id,
            normalized_phone,
            region_value,
            abonent_id,
            address,
            (description or ""),
            business_type,
            created_by_role
        )
        return row["application_number"]
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
    created_by_role: str = "technician",
) -> int:
    conn = await _conn()
    try:
        region_value = normalize_region_code(region) or (str(region).strip() if region is not None else None)
        normalized_phone = normalize_phone(phone) if phone else None
        row = await conn.fetchrow(
            """
            INSERT INTO staff_orders (
                user_id, phone, region, abonent_id,
                address, description, status, type_of_zayavka, is_active, created_by_role, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4,
                    $5, $6, 'in_controller', 'technician', TRUE, $7, NOW(), NOW())
            RETURNING id
            """,
            user_id,
            normalized_phone,
            region_value,
            abonent_id,
            address,
            (description or ""),
            created_by_role
        )
        return row["id"]
    finally:
        await conn.close()
