# database/basic/smart_service.py

import asyncpg
from typing import List, Dict, Any
from config import settings

async def fetch_smart_service_orders(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    SmartService arizalarini olish.
    
    Args:
        limit: Maksimal arizalar soni
        offset: Boshlang'ich pozitsiya
        
    Returns:
        List[Dict]: SmartService arizalari ro'yxati
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                sso.id,
                sso.application_number,
                sso.category,
                sso.service_type,
                sso.address,
                sso.latitude,
                sso.longitude,
                sso.created_at,
                u.full_name,
                u.phone,
                u.username
            FROM smart_service_orders sso
            LEFT JOIN users u ON u.id = sso.user_id
            WHERE sso.is_active = TRUE
            ORDER BY sso.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error fetching smart service orders: {e}")
        return []
    finally:
        await conn.close()

async def create_smart_service_order(user_id: int, category: str, service_type: str, address: str) -> int:
    """Yangi SmartService arizasini yaratish.
    
    Args:
        user_id: Foydalanuvchi IDsi
        category: Xizmat kategoriyasi
        service_type: Xizmat turi
        address: Manzil
        
    Returns:
        int: Yaratilgan ariza IDsi
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Generate application number for smart service
        # Get next number for smart service orders
        next_num = await conn.fetchval(
            """
            SELECT COALESCE(MAX(
                CASE 
                    WHEN application_number ~ '^SMA-[0-9]+$' THEN 
                        CAST(SUBSTRING(application_number FROM 'SMA-([0-9]+)$') AS INTEGER)
                    ELSE 0
                END
            ), 0) + 1
            FROM smart_service_orders 
            WHERE application_number IS NOT NULL
            """
        )
        
        application_number = f"SMA-{next_num:04d}"
        
        order_id = await conn.fetchval(
            """
            INSERT INTO smart_service_orders (application_number, user_id, category, service_type, address)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            application_number, user_id, category, service_type, address
        )
        return order_id
    except Exception as e:
        print(f"Error creating smart service order: {e}")
        return 0
    finally:
        await conn.close()

async def get_smart_service_orders_count() -> int:
    """Jami SmartService arizalari sonini olish.
    
    Returns:
        int: Jami arizalar soni
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM smart_service_orders")
        return count or 0
    except Exception as e:
        print(f"Error getting smart service orders count: {e}")
        return 0
    finally:
        await conn.close()
