# database/warehouse/materials.py
import asyncpg
from typing import Optional, Dict, Any, List
from decimal import Decimal
from config import settings

# ---------- MATERIALLAR ASOSIY CRUD / SELEKTLAR ----------
async def create_material(
    name: str,
    quantity: int,
    price: Optional[Decimal] = None,
    description: Optional[str] = None,
    serial_number: Optional[str] = None,
    material_unit: str = "dona",
) -> Dict[str, Any]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO materials (name, price, description, quantity, serial_number, material_unit, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
            RETURNING id, name, price, description, quantity, serial_number, material_unit, created_at, updated_at
            """,
            name, price, description, quantity, serial_number, material_unit
        )
        return dict(row)
    finally:
        await conn.close()

async def search_materials(search_term: str) -> List[Dict[str, Any]]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT id, name, price, description, quantity, serial_number, material_unit, created_at, updated_at
            FROM materials
            WHERE name ILIKE $1
            ORDER BY name
            LIMIT 20
            """,
            f"%{search_term}%"
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def get_all_materials() -> List[Dict[str, Any]]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT id, name, price, description, quantity, serial_number, material_unit, created_at, updated_at
            FROM materials
            ORDER BY name
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def get_material_by_id(material_id: int) -> Optional[Dict[str, Any]]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT id, name, price, description, quantity, serial_number, created_at, updated_at
            FROM materials
            WHERE id = $1
            """,
            material_id
        )
        return dict(row) if row else None
    finally:
        await conn.close()

async def update_material_quantity(material_id: int, additional_quantity: int) -> Dict[str, Any]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            UPDATE materials
            SET quantity = quantity + $2, updated_at = NOW()
            WHERE id = $1
            RETURNING id, name, price, description, quantity, serial_number, material_unit, created_at, updated_at
            """,
            material_id, additional_quantity
        )
        return dict(row)
    finally:
        await conn.close()

async def update_material_name_description(material_id: int, name: str, description: Optional[str] = None) -> Dict[str, Any]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            UPDATE materials
            SET name = $2, description = $3, updated_at = NOW()
            WHERE id = $1
            RETURNING id, name, price, description, quantity, serial_number, material_unit, created_at, updated_at
            """,
            material_id, name, description
        )
        return dict(row)
    finally:
        await conn.close()

async def get_low_stock_materials(threshold: int = 10) -> List[Dict[str, Any]]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT id, name, price, description, quantity, serial_number, created_at, updated_at
            FROM materials
            WHERE quantity <= $1
            ORDER BY quantity ASC, name
            """,
            threshold
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def get_out_of_stock_materials() -> List[Dict[str, Any]]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT id, name, price, description, quantity, serial_number, created_at, updated_at
            FROM materials
            WHERE quantity = 0
            ORDER BY name
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# ---------- EXPORT FUNKSIYALARI ----------
async def get_warehouse_inventory_for_export() -> List[Dict[str, Any]]:
    """Export uchun ombor inventarini olish"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                id,
                name,
                COALESCE(price, 0) as price,
                description,
                quantity,
                serial_number,
                material_unit,
                created_at,
                updated_at
            FROM materials
            ORDER BY name
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()
