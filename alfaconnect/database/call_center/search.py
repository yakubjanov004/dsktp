# database/call_center/search.py
import re
import asyncpg
from typing import Optional, Dict, Any
from config import settings

_PHONE_RE = re.compile(r"^\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$|^\+?998\d{9}$|^\d{9,12}$")

def _normalize_phone(raw: str) -> Optional[str]:
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
    phone_n = _normalize_phone(phone)
    if not phone_n:
        return None
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT id, telegram_id, full_name, username, phone, language, region, address,
                   abonent_id
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
