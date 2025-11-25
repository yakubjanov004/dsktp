import asyncpg
from config import settings
from typing import Optional

from database.basic.phone import normalize_phone

async def find_user_by_telegram_id(telegram_id: int) -> Optional[asyncpg.Record]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.fetchrow(
            """
            SELECT * FROM users WHERE telegram_id = $1
            """
        , telegram_id)
        return result
    finally:
        await conn.close()

# Region code to display name mapping
REGION_DISPLAY_NAMES = {
    'tashkent_city': 'Toshkent shahri',
    'toshkent_region': 'Toshkent viloyati',
    'andijon': 'Andijon viloyati',
    'fergana': 'Farg\'ona viloyati',
    'namangan': 'Namangan viloyati',
    'sirdaryo': 'Sirdaryo viloyati',
    'jizzax': 'Jizzax viloyati',
    'samarkand': 'Samarqand viloyati',
    'bukhara': 'Buxoro viloyati',
    'navoi': 'Navoiy viloyati',
    'kashkadarya': 'Qashqadaryo viloyati',
    'surkhandarya': 'Surxondaryo viloyati',
    'khorezm': 'Xorazm viloyati',
    'karakalpakstan': 'Qoraqalpog\'iston Respublikasi',
}

# Function to get region display name by code
def get_region_display_name(region_code):
    """Convert region code to human-readable name"""
    if not region_code:
        return 'Noma\'lum hudud'
    
    # If it's already a display name, return as is
    if region_code in REGION_DISPLAY_NAMES.values():
        return region_code
    
    # Convert code to display name
    return REGION_DISPLAY_NAMES.get(region_code.lower(), f'Hudud: {region_code}')

# -----------------------------
# Phone helpers
# -----------------------------

async def get_user_phone_by_telegram_id(telegram_id: int) -> Optional[str]:
    """Return user's phone by telegram_id or None."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            "SELECT phone FROM users WHERE telegram_id = $1",
            telegram_id
        )
    finally:
        await conn.close()

async def update_user_phone_by_telegram_id(telegram_id: int, phone: Optional[str]) -> bool:
    """Update user's phone by telegram_id; return True if updated."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        sanitized = (phone or "").strip()
        if sanitized:
            normalized = normalize_phone(sanitized)
            if not normalized:
                return False
        else:
            normalized = None

        result = await conn.execute(
            "UPDATE users SET phone = $1 WHERE telegram_id = $2",
            normalized, telegram_id
        )
        return result != 'UPDATE 0'
    finally:
        await conn.close()

# -----------------------------
# Order history helpers
# -----------------------------

async def get_user_orders_count(telegram_id: int) -> int:
    """Get total count of user orders (connection + technician orders)."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if not user:
            return 0
        
        user_id = user['id']
        
        connection_count = await conn.fetchval(
            "SELECT COUNT(*) FROM connection_orders WHERE user_id = $1",
            user_id
        )
        
        technician_count = await conn.fetchval(
            "SELECT COUNT(*) FROM technician_orders WHERE user_id = $1",
            user_id
        )
        
        return (connection_count or 0) + (technician_count or 0)
    finally:
        await conn.close()

async def get_user_orders_paginated(telegram_id: int, offset: int = 0, limit: int = 1) -> list:
    """Get user orders with pagination (connection + technician orders)."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if not user:
            return []
        
        user_id = user['id']
        
        # Union connection_orders va technician_orders
        orders = await conn.fetch(
            """
            (
                SELECT 
                    id, 
                    'connection' as order_type,
                    region as region,
                    address,
                    status::text as status,
                    created_at,
                    updated_at,
                    tarif_id,
                    NULL as abonent_id,
                    NULL as description,
                    application_number,
                    NULL as media_file_id,
                    NULL as media_type
                FROM connection_orders 
                WHERE user_id = $1
            )
            UNION ALL
            (
                SELECT 
                    id,
                    'technician' as order_type,
                    region as region,
                    address,
                    status::text as status,
                    created_at,
                    updated_at,
                    NULL as tarif_id,
                    abonent_id,
                    description,
                    application_number,
                    media as media_file_id,
                    CASE 
                        WHEN media IS NOT NULL THEN 'photo'
                        ELSE NULL
                    END as media_type
                FROM technician_orders 
                WHERE user_id = $1
            )
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id, limit, offset
        )
        
        return orders
    finally:
        await conn.close()

async def get_smart_service_orders_by_user(user_id: int, limit: int = 10, offset: int = 0):
    """Get smart service orders for a specific user."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        orders = await conn.fetch(
            """
            SELECT 
                id,
                'smart_service' as order_type,
                category,
                service_type,
                address,
                created_at,
                updated_at
            FROM smart_service_orders 
            WHERE user_id = $1 AND is_active = true
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id, limit, offset
        )
        
        return orders
    finally:
        await conn.close()

async def update_user_full_name(telegram_id: int, full_name: str) -> bool:
    """Foydalanuvchi to'liq ismini yangilaydi.
    
    Args:
        telegram_id: Telegram foydalanuvchi IDsi
        full_name: Yangi to'liq ism
        
    Returns:
        bool: Muvaffaqiyatli yangilangan bo'lsa True, aks holda False
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            'UPDATE users SET full_name = $1 WHERE telegram_id = $2',
            full_name, telegram_id
        )
        return result != 'UPDATE 0'
    finally:
        await conn.close()
