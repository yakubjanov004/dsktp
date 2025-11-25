import asyncpg
from config import settings
from typing import Optional

from database.basic.phone import normalize_phone

async def get_or_create_user(telegram_id: int, username: Optional[str], full_name: Optional[str] = None) -> str:
    """telegram_id bo'yicha userni tekshiradi, bo'lmasa ketma-ket ID bilan 'client' rolida yaratadi.
    
    Args:
        telegram_id: Telegram foydalanuvchi IDsi
        username: Telegram foydalanuvchi nomi (ixtiyoriy)
        full_name: Foydalanuvchi to'liq ismi (ixtiyoriy)
        
    Returns:
        str: Foydalanuvchi roli
    """
    # Bot o'zini bazaga saqlamasligi uchun tekshirish
    if telegram_id == settings.BOT_ID:
        return "client"  # Bot uchun default role qaytaradi, lekin bazaga saqlamaydi
    
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        user = await conn.fetchrow(
            'SELECT role, full_name FROM users WHERE telegram_id = $1',
            telegram_id
        )

        if user:
            # Update username and full_name if they are provided and different
            update_fields = []
            params = []
            param_count = 1
            
            if username is not None and user.get('username') != username:
                update_fields.append(f'username = ${param_count}')
                params.append(username)
                param_count += 1
                
            if full_name is not None and user.get('full_name') != full_name:
                update_fields.append(f'full_name = ${param_count}')
                params.append(full_name)
                param_count += 1
            
            if update_fields:
                params.append(telegram_id)
                await conn.execute(
                    f"UPDATE users SET {', '.join(update_fields)} WHERE telegram_id = ${param_count}",
                    *params
                )
                
            return user['role']
        else:
            # Ketma-ket ID bilan yangi user yaratish
            user_data = await conn.fetchrow(
                """
                SELECT * FROM create_user_sequential($1, $2, $3, NULL, 'client'::user_role)
                """,
                telegram_id, username, full_name
            )
            return "client"
    finally:
        await conn.close()

async def reset_user_sequence() -> None:
    """User ID sequence ni hozirgi ma'lumotlarga moslashtiradi."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        await conn.execute("SELECT reset_user_sequential_sequence()")
    finally:
        await conn.close()

async def get_next_user_id() -> int:
    """Keyingi ketma-ket user ID ni qaytaradi."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.fetchval("SELECT get_next_sequential_user_id()")
        return result
    finally:
        await conn.close()

async def find_user_by_telegram_id(telegram_id: int) -> Optional[asyncpg.Record]:
    """Finds a user by their Telegram ID."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        user = await conn.fetchrow(
            'SELECT * FROM users WHERE telegram_id = $1',
            telegram_id
        )
        return user
    finally:
        await conn.close()

async def find_user_by_phone(phone: str) -> Optional[asyncpg.Record]:
    """Finds a user by their phone number.
    
    After migration 046, all phones in users table are normalized to +998XXXXXXXXX format.
    This function normalizes input and does exact match for efficiency.
    """
    from database.basic.phone import normalize_phone
    
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Normalize input phone (after migration, all phones in DB are normalized)
        normalized = normalize_phone(phone)
        if not normalized:
            return None
        
        # Exact match (efficient - phones are normalized in DB after migration 046)
        user = await conn.fetchrow(
            """
            SELECT * FROM users 
            WHERE phone = $1
            LIMIT 1
            """,
            normalized
        )
        return user
    finally:
        await conn.close()

async def update_user_phone(telegram_id: int, phone: Optional[str]) -> bool:
    """Updates the phone number of a user by their Telegram ID."""
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
            'UPDATE users SET phone = $1 WHERE telegram_id = $2',
            normalized, telegram_id
        )
        return result != 'UPDATE 0'
    finally:
        await conn.close()

async def update_user_role(telegram_id: int, new_role: str) -> bool:
    """Updates the role of a user by their Telegram ID."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            'UPDATE users SET role = $1 WHERE telegram_id = $2',
            new_role, telegram_id
        )
        return result != 'UPDATE 0'
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

async def get_user_language(telegram_id: int) -> str:
    """Get user's language by telegram_id; return 'uz' as default."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        language = await conn.fetchval(
            "SELECT language FROM users WHERE telegram_id = $1",
            telegram_id
        )
        return language if language else 'uz'
    finally:
        await conn.close()

# SmartService Manager Queries
async def get_smart_service_orders_for_manager(limit: int = 10, offset: int = 0) -> list:
    """Menejer uchun SmartService arizalarini olish.
    
    Args:
        limit: Qaytariladigan arizalar soni
        offset: Boshlash pozitsiyasi
        
    Returns:
        list: SmartService arizalari ro'yxati
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        orders = await conn.fetch(
            """
            SELECT sso.id, sso.user_id, sso.category, sso.service_type, 
                   sso.address, sso.created_at, sso.updated_at,
                   u.full_name, u.phone, u.telegram_id
            FROM smart_service_orders sso
            JOIN users u ON sso.user_id = u.id
            ORDER BY sso.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(order) for order in orders]
    finally:
        await conn.close()

async def get_smart_service_order_by_id(order_id: int) -> Optional[dict]:
    """ID bo'yicha SmartService arizasini olish.
    
    Args:
        order_id: Ariza IDsi
        
    Returns:
        dict: Ariza ma'lumotlari yoki None
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        order = await conn.fetchrow(
            """
            SELECT sso.id, sso.user_id, sso.category, sso.service_type, 
                   sso.address, sso.created_at, sso.updated_at,
                   u.full_name, u.phone, u.telegram_id
            FROM smart_service_orders sso
            JOIN users u ON sso.user_id = u.id
            WHERE sso.id = $1
            """,
            order_id
        )
        return dict(order) if order else None
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
    finally:
        await conn.close()