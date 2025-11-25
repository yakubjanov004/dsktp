# database/warehouse/material_issued_queries.py
import asyncpg
from typing import List, Dict, Any
from config import settings

async def _conn():
    """Database connection helper"""
    return await asyncpg.connect(settings.DB_URL)

async def fetch_technician_used_materials(
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Texniklar qaysi arizaga qaysi materiallarni ishlatganini ko'rsatish
    material_issued jadvalidan olinadi
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT 
                mi.application_number,
                mi.request_type,
                MIN(mi.issued_at) as issued_at,
                u.full_name as technician_name,
                COUNT(mi.id) as materials_count,
                SUM(mi.total_price) as total_cost
            FROM material_issued mi
            JOIN users u ON u.id = mi.issued_by
            WHERE u.role = 'technician'
            GROUP BY mi.application_number, mi.request_type, u.full_name
            ORDER BY MIN(mi.issued_at) DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def fetch_materials_for_application(
    application_number: str,
    request_type: str
) -> List[Dict[str, Any]]:
    """
    Muayyan ariza uchun ishlatilgan materiallarni olish
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT 
                mi.material_name,
                mi.quantity,
                mi.price,
                mi.total_price,
                mi.issued_at,
                u.full_name as technician_name
            FROM material_issued mi
            JOIN users u ON u.id = mi.issued_by
            WHERE mi.application_number = $1 
              AND mi.request_type = $2
            ORDER BY mi.issued_at
            """,
            application_number, request_type
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def fetch_technician_used_materials_by_type(
    request_type: str,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Muayyan turdagi arizalar uchun texniklar ishlatgan materiallarni ko'rsatish
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT 
                mi.application_number,
                mi.request_type,
                MIN(mi.issued_at) as issued_at,
                u.full_name as technician_name,
                COUNT(mi.id) as materials_count,
                SUM(mi.total_price) as total_cost
            FROM material_issued mi
            JOIN users u ON u.id = mi.issued_by
            WHERE u.role = 'technician' AND mi.request_type = $1
            GROUP BY mi.application_number, mi.request_type, u.full_name
            ORDER BY MIN(mi.issued_at) DESC
            LIMIT $2 OFFSET $3
            """,
            request_type, limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def count_technician_used_materials() -> int:
    """
    Texniklar ishlatgan materiallar soni
    """
    conn = await _conn()
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT CONCAT(mi.application_number, '-', mi.request_type))
            FROM material_issued mi
            JOIN users u ON u.id = mi.issued_by
            WHERE u.role = 'technician'
            """
        )
        return count or 0
    finally:
        await conn.close()

async def count_technician_used_materials_by_type(request_type: str) -> int:
    """
    Muayyan turdagi arizalar uchun texniklar ishlatgan materiallar soni
    """
    conn = await _conn()
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT CONCAT(mi.application_number, '-', mi.request_type))
            FROM material_issued mi
            JOIN users u ON u.id = mi.issued_by
            WHERE u.role = 'technician' AND mi.request_type = $1
            """,
            request_type
        )
        return count or 0
    finally:
        await conn.close()
