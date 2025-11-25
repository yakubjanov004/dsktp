# database/basic/tariff.py
# Umumiy tariff bilan bog'liq funksiyalar

import asyncpg
import re
from typing import Optional, Dict, Any
from config import settings

def _code_to_name(tariff_code: Optional[str]) -> Optional[str]:
    """Tarif kodini nomga aylantirish."""
    if not tariff_code:
        return None
    
    # Remove 'tariff_' prefix if exists
    code = tariff_code.replace("tariff_", "") if tariff_code.startswith("tariff_") else tariff_code
    
    mapping = {
        # B2C Plans
        "b2c_plan_0": "Oddiy-20",
        "b2c_plan_1": "Oddiy-50",
        "b2c_plan_2": "Oddiy-100",
        "b2c_plan_3": "XIT-200",
        "b2c_plan_4": "VIP-500",
        "b2c_plan_5": "PREMIUM",
        # BizNET-Pro Plans
        "biznet_plan_0": "BizNET-Pro-1",
        "biznet_plan_1": "BizNET-Pro-2",
        "biznet_plan_2": "BizNET-Pro-3",
        "biznet_plan_3": "BizNET-Pro-4",
        "biznet_plan_4": "BizNET-Pro-5",
        "biznet_plan_5": "BizNET-Pro-6",
        "biznet_plan_6": "BizNET-Pro-7+",
        # Tijorat Plans
        "tijorat_plan_0": "Tijorat-1",
        "tijorat_plan_1": "Tijorat-2",
        "tijorat_plan_2": "Tijorat-3",
        "tijorat_plan_3": "Tijorat-4",
        "tijorat_plan_4": "Tijorat-5",
        "tijorat_plan_5": "Tijorat-100",
        "tijorat_plan_6": "Tijorat-300",
        "tijorat_plan_7": "Tijorat-500",
        "tijorat_plan_8": "Tijorat-1000",
    }
    return mapping.get(code)

async def get_or_create_tarif_by_code(tariff_code: Optional[str]) -> Optional[int]:
    """
    Jadvalda 'code' yo'q. Shuning uchun 'name' bo'yicha izlaymiz/yaratamiz.
    """
    if not tariff_code:
        return None

    name = _code_to_name(tariff_code)
    if not name:
        # fallback: kodni sarlavhaga aylantiramiz
        base = re.sub(r"^tariff_", "", tariff_code)  # tariff_xxx -> xxx
        name = re.sub(r"_+", " ", base).title()

    conn = await asyncpg.connect(settings.DB_URL)
    try:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id FROM public.tarif WHERE name = $1 LIMIT 1",
                name,
            )
            if row:
                return row["id"]
            row = await conn.fetchrow(
                """
                INSERT INTO public.tarif (name, created_at, updated_at)
                VALUES ($1, NOW(), NOW())
                RETURNING id
                """,
                name,
            )
            return row["id"]
    finally:
        await conn.close()

async def get_tariff_by_id(tariff_id: int) -> Optional[Dict[str, Any]]:
    """Tarif ma'lumotlarini ID bo'yicha olish."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            "SELECT * FROM tarif WHERE id = $1",
            tariff_id
        )
        return dict(row) if row else None
    finally:
        await conn.close()

async def get_all_tariffs() -> list[Dict[str, Any]]:
    """Barcha tariflarni olish."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch("SELECT * FROM tarif ORDER BY name")
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def search_tariffs_by_name(name_pattern: str) -> list[Dict[str, Any]]:
    """Tarif nomi bo'yicha qidirish."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            "SELECT * FROM tarif WHERE name ILIKE $1 ORDER BY name",
            f"%{name_pattern}%"
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()
