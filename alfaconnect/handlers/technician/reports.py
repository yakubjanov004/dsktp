# handlers/technician/reports.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta, timezone
import datetime as dt
import logging

def _get_tashkent_tz():
    """Xavfsiz vaqt mintaqasi olish funksiyasi.
    Avval zoneinfo orqali urinib ko'radi, keyin pytz orqali, oxirida UTC+5 qaytaradi.
    """
    # 1. Try zoneinfo with Asia/Tashkent
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Asia/Tashkent")
    except Exception:
        pass
    
    # 2. Try pytz if available
    try:
        import pytz
        return pytz.timezone('Asia/Tashkent')
    except ImportError:
        pass
    
    # 3. Fallback to UTC+5 (Tashkent time) using datetime.timezone
    return dt.timezone(dt.timedelta(hours=5), 'Asia/Tashkent')

from database.basic.user import find_user_by_telegram_id
from database.technician.report import (
    count_connection_status,
    count_technician_status,
    count_staff_status,
)

router = Router()

# --- i18n helper ---
def tr(uz: str, ru: str, lang: str) -> str:
    return uz if lang == "uz" else ru

def _fmt(n) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return str(n)

def _normalize_stats(raw: dict) -> dict:
    keys = {
        "completed",
        "cancelled",
        "in_warehouse",
        "in_technician_work",
        "in_technician",
        "between_controller_technician",
    }
    total = 0
    out = {k: int(raw.get(k, 0) or 0) for k in keys}
    for k, v in (raw or {}).items():
        c = int(v or 0)
        total += c
    out["total"] = total
    return out

def _block(title: str, stats: dict, lang: str) -> str:
    lines = [
        f"📦 <b>{title}</b>",
        f"• 🆕 {tr('Yangi (controller → technician)','Новые (controller → technician)',lang)}: <b>{_fmt(stats.get('between_controller_technician', 0))}</b>",
        f"• 🧰 {tr('Qabul qilingan (boshlanmagan)','Принято (не начато)',lang)}: <b>{_fmt(stats.get('in_technician', 0))}</b>",
        f"• 🟢 {tr('Ish jarayonida','В работе',lang)}: <b>{_fmt(stats.get('in_technician_work', 0))}</b>",
        f"• 📦 {tr('Omborda','На складе',lang)}: <b>{_fmt(stats.get('in_warehouse', 0))}</b>",
        f"• ✅ {tr('Yopilgan','Закрыто',lang)}: <b>{_fmt(stats.get('completed', 0))}</b>",
        f"• ❌ {tr('Bekor qilingan','Отменено',lang)}: <b>{_fmt(stats.get('cancelled', 0))}</b>",
        "— — —",
        f"📊 {tr('Jami','Итого',lang)}: <b>{_fmt(stats.get('total', 0))}</b>",
    ]
    return "\n".join(lines)

# --- Davr filtri ---
ASIA_TASHKENT = _get_tashkent_tz()

def _make_period(key: str):
    """
    key ∈ {'today','3','7','30','all'}
    Qaytaradi: (date_from_utc_or_none, date_to_utc_or_none, label_local)
    """
    now_local = datetime.now(ASIA_TASHKENT)
    if key == "today":
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        label = f"{start_local:%d.%m.%Y}"
        start_utc = start_local.astimezone(timezone.utc)
        end_utc   = end_local.astimezone(timezone.utc)
        return start_utc, end_utc, label

    if key in {"3","7","30"}:
        days = int(key)
        end_local = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        start_local = end_local - timedelta(days=days)
        label = f"{start_local:%d.%m.%Y} — {(end_local - timedelta(seconds=1)):%d.%m.%Y}"
        start_utc = start_local.astimezone(timezone.utc)
        end_utc   = end_local.astimezone(timezone.utc)
        return start_utc, end_utc, label

    return None, None, "Jami davr"

def _range_kb(selected_key: str, lang: str) -> InlineKeyboardMarkup:
    keys = [
        ("today", tr("📅 Bugun", "📅 Сегодня", lang)),
        ("3",     tr("📅 3 kun", "📅 3 дня", lang)),
        ("7",     tr("📅 7 kun", "📅 7 дней", lang)),
        ("30",    tr("📅 Oy", "📅 Месяц", lang)),
        ("all",   tr("📅 Jami", "📅 Всего", lang)),
    ]
    
    rows = []
    for i in range(0, len(keys), 3):  
        row = []
        for k, title in keys[i:i+3]:
            mark = "✅ " if k == selected_key else ""
            row.append(InlineKeyboardButton(text=mark + title, callback_data=f"rep_range_{k}"))
        rows.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _build_and_send_report(message_or_cb, lang: str, user_id: int, range_key: str):
    # 1) Davr
    df_utc, dt_utc, label_local = _make_period(range_key)
    if range_key == "all":
        label_local = tr("Jami davr", "Весь период", lang)

    # 2) DB so‘rovlar — faqat connections
    conn_raw = await count_connection_status(user_id, df_utc, dt_utc)   
    tech_raw = await count_technician_status(user_id, df_utc, dt_utc)   
    staff_raw = await count_staff_status(user_id, df_utc, dt_utc)         

    conn = _normalize_stats(conn_raw or {})
    tch  = _normalize_stats(tech_raw or {})
    staff = _normalize_stats(staff_raw or {})

    # 3) Matn
    header  = tr("📊 <b>Hisobotlarim</b>", "📊 <b>Мои отчеты</b>", lang)
    period  = tr("Davr", "Период", lang)
    subtitle = f"{period}: <code>{label_local}</code>"

    body = "\n\n".join([
        _block(tr("🔌 Ulanish arizalari", "🔌 Заявки на подключение", lang), conn, lang),
        _block(tr("🔧 Texnik xizmat arizalari", "🔧 Заявки на техобслуживание", lang), tch, lang),
        _block(tr("📞 Xodim (operator) arizalari", "📞 Заявки от сотрудников (операторов)", lang), staff, lang),
    ])

    footer = tr(
        "ℹ️ Hisob faqat texnik sifatida qatnashgan yozuvlar va texnik statuslar bo‘yicha qilindi.",
        "ℹ️ Счёт ведётся только по записям, где вы участвовали как техник, и по тех-статусам.",
        lang
    )

    text = f"{header}\n\n{subtitle}\n\n{body}\n\n{footer}"
    kb = _range_kb(range_key, lang)

    # 4) Jo‘natish
    if isinstance(message_or_cb, Message):
        await message_or_cb.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        try:
            await message_or_cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await message_or_cb.message.answer(text, reply_markup=kb, parse_mode="HTML")

# === Entry: default 30 kun ===
@router.message(F.text.in_(["📊 Hisobotlarim", "📊 Мои отчеты"]))
async def reports_handler(message: Message):
    user = await find_user_by_telegram_id(message.from_user.id)
    if not user or user.get("role") != "technician":
        return
    lang = (user.get("lang") or user.get("user_lang") or "uz").lower()
    if message.text == "📊 Мои отчеты":
        lang = "ru"

    await _build_and_send_report(message, lang, user_id=user["id"], range_key="30")

# === Callback: davr filtri ===
@router.callback_query(F.data.startswith("rep_range_"))
async def reports_range_callback(cb: CallbackQuery):
    user = await find_user_by_telegram_id(cb.from_user.id)
    lang = (user.get("lang") or user.get("user_lang") or "uz").lower() if user else "uz"
    if not user or user.get("role") != "technician":
        return await cb.answer(tr("❌ Ruxsat yo‘q", "❌ Нет доступа", lang), show_alert=True)

    key = cb.data.replace("rep_range_", "")
    if key not in {"today", "3", "7", "30", "all"}:
        key = "30"

    await _build_and_send_report(cb, lang, user_id=user["id"], range_key=key)
    await cb.answer(tr("Filtr qo‘llandi", "Фильтр применён", lang))
