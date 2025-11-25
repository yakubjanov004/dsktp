# database/basic/user.py
# Umumiy user bilan bog'liq queries (barcha rollar uchun)

import asyncpg
from typing import List, Dict, Any, Optional
from config import settings

# =========================================================
#  User yaratish va topish
# =========================================================

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
                INSERT INTO users (telegram_id, username, full_name, role, language, is_blocked)
                VALUES ($1, $2, $3, 'client', 'uz', FALSE)
                RETURNING role
                """,
                telegram_id, username, full_name
            )
            return user_data['role']
    finally:
        await conn.close()

async def find_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """
    Telegram ID orqali user ma'lumotlarini olish.
    Bu funksiya get_user_by_telegram_id bilan bir xil, lekin eski nom bilan.
    """
    return await get_user_by_telegram_id(telegram_id)

async def update_user_phone(telegram_id: int, phone: Optional[str]) -> bool:
    """
    Foydalanuvchi telefonini yangilaydi.
    Bu funksiya update_user_phone_by_telegram_id bilan bir xil, lekin eski nom bilan.
    """
    return await update_user_phone_by_telegram_id(telegram_id, phone)

# =========================================================

async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    User ID orqali user ma'lumotlarini olish.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT 
                id,
                telegram_id,
                full_name,
                username,
                phone,
                role,
                language,
                region,
                address,
                abonent_id,
                is_blocked,
                created_at,
                updated_at
            FROM users
            WHERE id = $1
            """,
            user_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()

async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """
    Telegram ID orqali user ma'lumotlarini olish.
    Barcha rollar uchun umumiy funksiya.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT 
                id,
                telegram_id,
                full_name,
                username,
                phone,
                role,
                language,   -- 🔑 tilni ham olish kerak
                region,
                address,
                abonent_id,
                is_blocked,
                is_online,
                last_seen_at,
                created_at,
                updated_at
            FROM users
            WHERE telegram_id = $1
            """,
            telegram_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()

async def get_users_by_role(role: str) -> List[Dict[str, Any]]:
    """
    Role bo'yicha userlarni olish.
    Faqat faol (is_blocked=FALSE) userlarni qaytaradi.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT id, full_name, username, phone, telegram_id
              FROM users
             WHERE role = $1
               AND COALESCE(is_blocked, FALSE) = FALSE
             ORDER BY full_name NULLS LAST, id
            """,
            role,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def ensure_user(telegram_id: int, full_name: str, username: str, role: str = 'client') -> Dict[str, Any]:
    """
    User mavjudligini tekshirish va kerak bo'lsa yaratish.
    """
    # Bot o'zini bazaga saqlamasligi uchun tekshirish
    if telegram_id == settings.BOT_ID:
        return {"id": 0, "telegram_id": telegram_id, "full_name": full_name, "username": username, "role": role}
    
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Avval mavjudligini tekshiramiz
        existing = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if existing:
            return dict(existing)
        
        # Yangi user yaratamiz
        new_user = await conn.fetchrow(
            """
            INSERT INTO users (telegram_id, full_name, username, role, language, is_blocked)
            VALUES ($1, $2, $3, $4, 'uz', FALSE)
            RETURNING *
            """,
            telegram_id, full_name, username, role
        )
        return dict(new_user)
    finally:
        await conn.close()

# =========================================================
#  Telefon bilan ishlash
# =========================================================

import re

_PHONE_RE = re.compile(
    r"^\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$|^\+?998\d{9}$|^\d{9,12}$"
)

def normalize_phone(raw: str) -> Optional[str]:
    """Telefon raqamini normalizatsiya qilish."""
    raw = (raw or "").strip()
    if not _PHONE_RE.match(raw):
        return None
    digits = re.sub(r"[^\d]", "", raw)
    if digits.startswith("998") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 9:
        return "+998" + digits
    return raw if raw.startswith("+") else ("+" + digits if digits else None)

async def find_user_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    """
    Telefon bo'yicha users dagi yozuvni qidiradi (raqamlar bo'yicha taqqoslash).
    """
    phone_n = normalize_phone(phone)
    if not phone_n:
        return None
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT id, telegram_id, full_name, username, phone, language, region, address,
                   abonent_id, is_blocked, role
              FROM users
             WHERE regexp_replace(phone, '[^0-9]', '', 'g')
                   = regexp_replace($1,   '[^0-9]', '', 'g')
             LIMIT 1
            """,
            phone_n,
        )
        return dict(row) if row else None
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

# =========================================================
#  User ma'lumotlarini yangilash
# =========================================================

async def update_user_full_name(telegram_id: int, full_name: str) -> bool:
    """Foydalanuvchi to'liq ismini yangilaydi."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            'UPDATE users SET full_name = $1 WHERE telegram_id = $2',
            full_name, telegram_id
        )
        return result != 'UPDATE 0'
    finally:
        await conn.close()

async def update_user_address(telegram_id: int, address: str) -> bool:
    """Foydalanuvchi manzilini yangilaydi."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            'UPDATE users SET address = $1 WHERE telegram_id = $2',
            address, telegram_id
        )
        return result != 'UPDATE 0'
    finally:
        await conn.close()

async def update_user_region(telegram_id: int, region: str) -> bool:
    """Foydalanuvchi regionini yangilaydi."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            'UPDATE users SET region = $1 WHERE telegram_id = $2',
            region, telegram_id
        )
        return result != 'UPDATE 0'
    finally:
        await conn.close()

async def update_user_username(telegram_id: int, username: Optional[str]) -> bool:
    """
    Foydalanuvchi username ni yangilaydi.
    
    Args:
        telegram_id: Telegram foydalanuvchi IDsi
        username: Yangi username (@ belgisi bo'lsa olib tashlanadi, None bo'lsa NULL saqlanadi)
        
    Returns:
        bool: Muvaffaqiyatli yangilangan bo'lsa True
        
    Features:
        - @ belgisini olib tashlaydi
        - Bo'sh/None qiymatni NULL sifatida saqlaydi
        - Idempotent: bir xil qiymat bo'lsa UPDATE qilmaydi
    """
    # @ belgisini olib tashlash
    clean_username = None
    if username:
        clean_username = username.strip().lstrip('@')
        if not clean_username:  # Faqat @ yoki bo'sh string bo'lsa
            clean_username = None
    
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Avval mavjud username ni olish
        current_username = await conn.fetchval(
            'SELECT username FROM users WHERE telegram_id = $1',
            telegram_id
        )
        
        # Agar bir xil bo'lsa, UPDATE qilmaslik
        if current_username == clean_username:
            return True
            
        # Yangilash
        result = await conn.execute(
            'UPDATE users SET username = $1 WHERE telegram_id = $2',
            clean_username, telegram_id
        )
        return result != 'UPDATE 0'
    finally:
        await conn.close()

# =========================================================
#  User holatini tekshirish
# =========================================================

async def is_user_blocked(telegram_id: int) -> bool:
    """Foydalanuvchi bloklanganligini tekshirish."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.fetchval(
            "SELECT COALESCE(is_blocked, FALSE) FROM users WHERE telegram_id = $1",
            telegram_id
        )
        return bool(result)
    finally:
        await conn.close()

async def block_user(telegram_id: int) -> bool:
    """Foydalanuvchini bloklash."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            "UPDATE users SET is_blocked = TRUE WHERE telegram_id = $1",
            telegram_id
        )
        return result != 'UPDATE 0'
    finally:
        await conn.close()

async def unblock_user(telegram_id: int) -> bool:
    """Foydalanuvchini blokdan chiqarish."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            "UPDATE users SET is_blocked = FALSE WHERE telegram_id = $1",
            telegram_id
        )
        return result != 'UPDATE 0'
    finally:
        await conn.close()

# =========================================================
#  User roli bilan ishlash
# =========================================================

async def get_user_role(telegram_id: int) -> Optional[str]:
    """Foydalanuvchi roli."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        return await conn.fetchval(
            "SELECT role FROM users WHERE telegram_id = $1",
            telegram_id
        )
    finally:
        await conn.close()

async def update_user_role(telegram_id: int, role: str) -> bool:
    """Foydalanuvchi roli."""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            "UPDATE users SET role = $1 WHERE telegram_id = $2",
            role, telegram_id
        )
        return result != 'UPDATE 0'
    finally:
        await conn.close()

# =========================================================
#  User statistika
# =========================================================

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
