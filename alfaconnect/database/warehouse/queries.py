# database/warehouse/queries.py

import asyncpg
from typing import List, Dict, Any
from config import settings

async def get_warehouse_inventory_for_export() -> List[Dict[str, Any]]:
    """Warehouse inventory export"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                id,
                name,
                quantity,
                price,
                description,
                serial_number,
                created_at,
                updated_at
            FROM materials
            ORDER BY name
            """
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_warehouse_statistics_for_export(filter_type: str = "all") -> Dict[str, Any]:
    """Warehouse statistics export"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Build query based on filter type
        if filter_type == "low_stock":
            where_clause = "WHERE quantity <= 10"
        elif filter_type == "out_of_stock":
            where_clause = "WHERE quantity = 0"
        else:
            where_clause = ""
        
        stats = await conn.fetchrow(
            f"""
            SELECT 
                COUNT(*) as total_materials,
                SUM(quantity) as total_quantity,
                SUM(price * quantity) as total_value,
                COUNT(CASE WHEN quantity > 0 THEN 1 END) as available_materials,
                COUNT(CASE WHEN quantity = 0 THEN 1 END) as out_of_stock,
                COUNT(CASE WHEN quantity <= 10 THEN 1 END) as low_stock
            FROM materials
            {where_clause}
            """
        )
        return dict(stats) if stats else {}
    finally:
        await conn.close()
