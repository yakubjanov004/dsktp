import asyncpg
from config import settings
from typing import Optional

async def update_user_language(telegram_id: int, language: str) -> bool:
    """Foydalanuvchi tilini yangilaydi.
    
    Args:
        telegram_id: Telegram foydalanuvchi IDsi
        language: Yangi til (uz yoki ru)
        
    Returns:
        bool: Muvaffaqiyatli yangilangan bo'lsa True
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.execute(
            'UPDATE users SET language = $1 WHERE telegram_id = $2',
            language, telegram_id
        )
        return result == "UPDATE 1"
    except Exception as e:
        print(f"Til yangilashda xatolik: {e}")
        return False
    finally:
        await conn.close()

async def get_user_language(telegram_id: int) -> Optional[str]:
    """Foydalanuvchi tilini oladi.
    
    Args:
        telegram_id: Telegram foydalanuvchi IDsi
        
    Returns:
        Optional[str]: Foydalanuvchi tili (uz yoki ru) yoki None
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.fetchval(
            'SELECT language FROM users WHERE telegram_id = $1',
            telegram_id
        )
        return result
    except Exception as e:
        print(f"Til olishda xatolik: {e}")
        return None
    finally:
        await conn.close()