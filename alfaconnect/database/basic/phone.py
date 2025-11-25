# database/basic/phone.py
# Telefon raqamlari bilan bog'liq umumiy funksiyalar

import re
import asyncpg
from typing import Optional, Dict, Any
from config import settings

# Telefon raqam validatsiyasi uchun regex
_PHONE_RE = re.compile(
    r"^\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$|^\+?998\d{9}$|^\d{9,12}$"
)

def normalize_phone(raw: str) -> Optional[str]:
    """
    Telefon raqamini normalizatsiya qilish.
    
    Args:
        raw: Qo'lda kiritilgan telefon raqam
        
    Returns:
        Normalizatsiya qilingan telefon raqam (+998XXXXXXXXX formatida)
        yoki None agar raqam noto'g'ri bo'lsa
    """
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
    Telefon raqam orqali user topish.
    
    Args:
        phone: Qidiriladigan telefon raqam
        
    Returns:
        User ma'lumotlari yoki None
    """
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        return None
    
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT id, full_name, phone, username, telegram_id, role, language, is_blocked, created_at
            FROM users
            WHERE phone = $1
            """,
            normalized_phone
        )
        return dict(row) if row else None
    finally:
        await conn.close()

def validate_phone(phone: str) -> bool:
    """
    Telefon raqamning to'g'riligini tekshirish.
    
    Args:
        phone: Tekshiriladigan telefon raqam
        
    Returns:
        True agar raqam to'g'ri bo'lsa, False aks holda
    """
    return normalize_phone(phone) is not None

def format_phone_display(phone: str) -> str:
    """
    Telefon raqamni ko'rinish uchun formatlash.
    
    Args:
        phone: Formatlanadigan telefon raqam
        
    Returns:
        Formatlangan telefon raqam (+998 XX XXX XX XX)
    """
    normalized = normalize_phone(phone)
    if not normalized:
        return phone
    
    digits = normalized[1:]  # + ni olib tashlash
    if len(digits) == 12 and digits.startswith("998"):
        # +998 XX XXX XX XX formatida
        return f"+{digits[:3]} {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:12]}"
    
    return normalized

def extract_digits_only(phone: str) -> str:
    """
    Telefon raqamdan faqat raqamlarni ajratib olish.
    
    Args:
        phone: Ajratiladigan telefon raqam
        
    Returns:
        Faqat raqamlardan iborat string
    """
    return re.sub(r"[^\d]", "", phone)

def is_uzbek_phone(phone: str) -> bool:
    """
    Telefon raqamning O'zbekiston raqami ekanligini tekshirish.
    
    Args:
        phone: Tekshiriladigan telefon raqam
        
    Returns:
        True agar O'zbekiston raqami bo'lsa, False aks holda
    """
    normalized = normalize_phone(phone)
    return normalized is not None and normalized.startswith("+998")
