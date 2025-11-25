# handlers/controller/staff_activity.py
# Reply tugmadan: "👥 Xodimlar faoliyati" / "👥 Активность сотрудников"
# Hech qanday inline tugma yo'q — darhol matnli hisobot yuboradi (UZ/RU).

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import logging

from filters.role_filter import RoleFilter
from database.controller.orders import (
    fetch_staff_activity,
)
from database.basic.user import get_user_by_telegram_id
from database.basic.language import get_user_language

router = Router()
logger = logging.getLogger(__name__)
router.message.filter(RoleFilter("controller"))

# ---------------- I18N ----------------
T = {
    "title": {
        "uz": "👥 Xodimlar faoliyati",
        "ru": "👥 Активность сотрудников",
    },
    "legend": {
        "uz": "Hisobot: texniklar kesimi (connection/technician/aktiv)",
        "ru": "Отчёт: по техникам (подключение/техник/активные)",
    },
    "totals": {
        "uz": "— Jami xodimlar: {staff_cnt} | Connection: {conn_sum} ta | Technician: {tech_sum} ta | Hammasi: {total_sum} ta",
        "ru": "— Всего сотрудников: {staff_cnt} | Подключение: {conn_sum} шт. | Техник: {tech_sum} шт. | Итого: {total_sum} шт.",
    },
    "conn": {"uz": "Connection", "ru": "Connection"},
    "tech": {"uz": "Technician", "ru": "Technician"},
    "active": {"uz": "Aktiv", "ru": "Активные"},
    "role_technician": {"uz": "Texnik", "ru": "Техник"},
    "role_controller": {"uz": "Controller", "ru": "Контроллер"},
    "empty": {
        "uz": "Ma'lumot topilmadi.",
        "ru": "Данные не найдены.",
    },
}

def _norm_lang(v: str | None) -> str:
    if not v:
        return "uz"
    v = v.strip().lower()
    if v in {"ru", "rus", "russian", "ru-ru", "ru_ru"}:
        return "ru"
    return "uz"

def _t(lang: str, key: str, **fmt) -> str:
    lang = _norm_lang(lang)
    s = T.get(key, {}).get(lang, T.get(key, {}).get("uz", key))
    return s.format(**fmt) if fmt else s

def _medal(i: int) -> str:
    return "🥇" if i == 0 else ("🥈" if i == 1 else ("🥉" if i == 2 else "•"))

def _build_report(lang: str, items: list[dict]) -> str:
    if not items:
        return _t(lang, "empty")

    # Umumiy yig'indilar
    conn_sum = sum(int(x.get("conn_count", 0) or 0) for x in items)
    tech_sum = sum(int(x.get("tech_count", 0) or 0) for x in items)
    total_sum = sum(int(x.get("total_count", 0) or 0) for x in items)

    lines = [f"{_t(lang,'title')}\n", _t(lang, "legend"), ""]
    unit = "ta" if _norm_lang(lang) == "uz" else "шт."

    for i, it in enumerate(items):
        name = it.get("full_name") or "—"
        role = it.get("role", "technician")
        if role == "technician":
            role_text = _t(lang, "role_technician")
        elif role == "controller":
            role_text = _t(lang, "role_controller")
        else:
            role_text = role
            
        conn_c = int(it.get("conn_count", 0) or 0)
        tech_c = int(it.get("tech_count", 0) or 0)
        active_c = int(it.get("in_progress_orders", 0) or 0)

        head = f"{i+1}. {_medal(i)} {name} ({role_text})"
        lines.append(head)
        lines.append(f"├ {_t(lang,'conn')}: {conn_c} {unit}")
        lines.append(f"├ {_t(lang,'tech')}: {tech_c} {unit}")
        lines.append(f"└ {_t(lang,'active')}: {active_c} {unit}")

    lines.append("")
    lines.append(_t(lang, "totals",
                    staff_cnt=len(items),
                    conn_sum=conn_sum,
                    tech_sum=tech_sum,
                    total_sum=total_sum))
    return "\n".join(lines)

# ---------------- ENTRY ----------------

UZ_ENTRY_TEXT = "👥 Xodimlar faoliyati"
RU_ENTRY_TEXT = "👥 Активность сотрудников"

@router.message(F.text.in_([UZ_ENTRY_TEXT, RU_ENTRY_TEXT]))
async def staff_activity_entry(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    items = await fetch_staff_activity()  # texniklar bo‘yicha activity
    text = _build_report(lang, items)

    # Telegram xabar uzunligi limitidan oshmasligi uchun bo'laklab yuboramiz
    CHUNK = 3500
    if len(text) <= CHUNK:
        await message.answer(text)
        return

    start = 0
    while start < len(text):
        await message.answer(text[start:start+CHUNK])
        start += CHUNK
