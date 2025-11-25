from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
import logging
from datetime import datetime, timedelta

from filters.role_filter import RoleFilter
from database.manager.orders import fetch_staff_activity_with_time_filter
from database.basic.user import get_user_by_telegram_id

router = Router()
logger = logging.getLogger(__name__)
router.message.filter(RoleFilter("manager"))
router.callback_query.filter(RoleFilter("manager"))

# ---------------- I18N ----------------
T = {
    "title": {
        "uz": "👥 Xodimlar faoliyati",
        "ru": "👥 Активность сотрудников",
    },
    "legend": {
        "uz": "📊 Menejerlar va kichik menejerlar faoliyati",
        "ru": "📊 Активность менеджеров и младших менеджеров",
    },
    "time_filter": {
        "uz": "Vaqt bo'yicha filtrlash:",
        "ru": "Фильтр по времени:",
    },
    "btn_today": {"uz": "📅 Bugun", "ru": "📅 Сегодня"},
    "btn_3days": {"uz": "📅 3 kun", "ru": "📅 3 дня"},
    "btn_7days": {"uz": "📅 7 kun", "ru": "📅 7 дней"},
    "btn_month": {"uz": "📅 Oy", "ru": "📅 Месяц"},
    "btn_total": {"uz": "📅 Jami", "ru": "📅 Всего"},
    "period_today": {"uz": "Bugungi hisobot", "ru": "Отчёт за сегодня"},
    "period_3days": {"uz": "So'nggi 3 kun", "ru": "Последние 3 дня"},
    "period_7days": {"uz": "So'nggi 7 kun", "ru": "Последние 7 дней"},
    "period_month": {"uz": "So'nggi oy", "ru": "Последний месяц"},
    "period_total": {"uz": "Jami hisobot", "ru": "Общий отчёт"},
    "totals": {
        "uz": "📈 Jami: {staff_cnt} xodim | Ulanish: {conn_sum} ta | Barcha arizalar: {total_sum} ta",
        "ru": "📈 Всего: {staff_cnt} сотрудников | Подключение: {conn_sum} шт. | Все заявки: {total_sum} шт.",
    },
    "conn": {"uz": "Ulanish", "ru": "Подключение"},
    "conn_assigned": {"uz": "📥 Ulanish arizalari (tayinlangan)", "ru": "📥 Заявки на подключение (назначенные)"},
    "conn_created": {"uz": "📤 Ulanish arizalari (yaratilgan)", "ru": "📤 Заявки на подключение (созданные)"},
    "conn_sent": {"uz": "📤 Ulanish arizalari (yuborilgan)", "ru": "📤 Заявки на подключение (отправленные)"},
    "tech_created": {"uz": "🔧 Texnik arizalar (yaratilgan)", "ru": "🔧 Технические заявки (созданные)"},
    "tech_sent": {"uz": "🔧 Texnik arizalar (yuborilgan)", "ru": "🔧 Технические заявки (отправленные)"},
    "staff_created": {"uz": "📋 Xodim arizalari (yaratilgan)", "ru": "📋 Служебные заявки (созданные)"},
    "staff_assigned": {"uz": "📥 Xodim arizalari (tayinlangan)", "ru": "📥 Служебные заявки (назначенные)"},
    "staff_sent": {"uz": "📋 Xodim arizalari (yuborilgan)", "ru": "📋 Служебные заявки (отправленные)"},
    "active": {"uz": "⚡ Hozir ishlayotgan", "ru": "⚡ Сейчас в работе"},
    "role_manager": {"uz": "Menejer", "ru": "Менеджер"},
    "role_jm": {"uz": "Kichik menejer", "ru": "Младший менеджер"},
    "empty": {
        "uz": "📭 Bu davrda hech qanday ariza topilmadi.",
        "ru": "📭 За этот период заявки не найдены.",
    },
}

def _norm_lang(v: str | None) -> str:
    if not v:
        return "uz"
    v = v.strip().lower()
    if v in {"ru","rus","russian","ru-ru","ru_ru"}:
        return "ru"
    return "uz"

def _t(lang: str, key: str, **fmt) -> str:
    lang = _norm_lang(lang)
    s = T.get(key, {}).get(lang, T.get(key, {}).get("uz", key))
    return s.format(**fmt) if fmt else s

def _role_label(lang: str, role: str) -> str:
    role = (role or "").lower()
    if role == "junior_manager":
        return _t(lang, "role_jm")
    return _t(lang, "role_manager")

def _medal(i: int) -> str:
    return "🥇" if i == 0 else ("🥈" if i == 1 else ("🥉" if i == 2 else "•"))

def _build_time_filter_keyboard(lang: str, current_filter: str = "total") -> InlineKeyboardMarkup:
    """Vaqt filtrlari uchun inline keyboard"""
    kb = InlineKeyboardBuilder()
    
    # Time filter buttons
    filters = [
        ("today", _t(lang, "btn_today")),
        ("3days", _t(lang, "btn_3days")),
        ("7days", _t(lang, "btn_7days")),
        ("month", _t(lang, "btn_month")),
        ("total", _t(lang, "btn_total"))
    ]
    
    for filter_key, filter_text in filters:
        if filter_key == current_filter:
            filter_text = f"✅ {filter_text}"
        kb.button(text=filter_text, callback_data=f"staff_filter_{filter_key}")
    
    kb.adjust(3, 2)  
    return kb.as_markup()

def _build_report(lang: str, items: list[dict], period: str = "total") -> str:
    if not items:
        return _t(lang, "empty")

    # Umumiy yig'indilar
    conn_sum = sum(x.get("conn_count", 0) for x in items)
    total_sum = sum(x.get("total_orders", 0) for x in items)

    # Period title
    period_titles = {
        "today": _t(lang, "period_today"),
        "3days": _t(lang, "period_3days"),
        "7days": _t(lang, "period_7days"),
        "month": _t(lang, "period_month"),
        "total": _t(lang, "period_total")
    }
    
    period_title = period_titles.get(period, _t(lang, "period_total"))
    
    lines = [f"{_t(lang,'title')}\n", f"{period_title}\n", _t(lang, "legend"), ""]
    for i, it in enumerate(items):
        name = it.get("full_name") or "—"
        role = _role_label(lang, it.get("role"))
        conn_c = it.get("conn_count", 0)
        active_c = it.get("active_count", 0)
        
        # Role ga qarab ko'rsatish:
        # Manager: yaratilgan + yuborilgan
        # Junior Manager: tayinlangan (assigned) + yuborilgan
        role_type = (it.get("role") or "").lower()
        is_junior_manager = role_type == "junior_manager"
        
        # Detailed counts for connection orders
        created_conn = it.get("created_conn_count", 0)
        assigned_conn = it.get("assigned_conn_count", 0)
        sent_conn = it.get("sent_conn_count", 0)
        
        # Detailed counts for staff orders
        created_staff = it.get("created_staff_count", 0)
        assigned_staff = it.get("assigned_staff_count", 0)
        sent_staff = it.get("sent_staff_count", 0)

        # Ko'rinish:
        # Manager: yaratilgan + yuborilgan
        # Junior Manager: tayinlangan + yuborilgan
        head = f"{i+1}. {_medal(i)} {name} ({role})"
        # birliklarni UZ: "ta" / RU: "шт."
        unit = "ta" if _norm_lang(lang) == "uz" else "шт."
        lines.append(head)
        
        # Manager uchun: created + sent
        # Junior Manager uchun: assigned + sent
        if is_junior_manager:
            # Junior Manager: assigned + sent
            has_any = assigned_conn > 0 or sent_conn > 0 or assigned_staff > 0 or sent_staff > 0
            
            if has_any:
                # Ulanish (tayinlangan)
                if assigned_conn > 0:
                    lines.append(f"├ {_t(lang,'conn_assigned')}: {assigned_conn} {unit}")
                
                # Ulanish (yuborilgan)
                if sent_conn > 0:
                    lines.append(f"├ {_t(lang,'conn_sent')}: {sent_conn} {unit}")
                
                # Xodim (tayinlangan)
                if assigned_staff > 0:
                    lines.append(f"├ {_t(lang,'staff_assigned')}: {assigned_staff} {unit}")
                
                # Xodim (yuborilgan)
                if sent_staff > 0:
                    lines.append(f"├ {_t(lang,'staff_sent')}: {sent_staff} {unit}")
        else:
            # Manager: created + sent
            has_any = created_conn > 0 or sent_conn > 0 or created_staff > 0 or sent_staff > 0
            
            if has_any:
                # Ulanish (yaratilgan)
                if created_conn > 0:
                    lines.append(f"├ {_t(lang,'conn_created')}: {created_conn} {unit}")
                
                # Ulanish (yuborilgan)
                if sent_conn > 0:
                    lines.append(f"├ {_t(lang,'conn_sent')}: {sent_conn} {unit}")
                
                # Xodim (yaratilgan)
                if created_staff > 0:
                    lines.append(f"├ {_t(lang,'staff_created')}: {created_staff} {unit}")
                
                # Xodim (yuborilgan)
                if sent_staff > 0:
                    lines.append(f"├ {_t(lang,'staff_sent')}: {sent_staff} {unit}")
        
        # Aktiv
        lines.append(f"└ {_t(lang,'active')}: {active_c} {unit}")

    lines.append("")
    lines.append(_t(lang, "totals",
                    staff_cnt=len(items),
                    conn_sum=conn_sum,
                    total_sum=total_sum))
    return "\n".join(lines)

async def _get_lang(user_tg_id: int) -> str:
    # users jadvalidan language olib, 'uz'/'ru' ga normalize qilamiz
    user = await get_user_by_telegram_id(user_tg_id)
    lng = (user or {}).get("language")
    return _norm_lang(lng)

# ---------------- ENTRY ----------------

UZ_ENTRY_TEXT = "👥 Xodimlar faoliyati"
RU_ENTRY_TEXT = "👥 Активность сотрудников"

@router.message(F.text.in_([UZ_ENTRY_TEXT, RU_ENTRY_TEXT]))
async def staff_activity_entry(message: Message, state: FSMContext):
    lang = await _get_lang(message.from_user.id)
    items = await fetch_staff_activity_with_time_filter("total")
    text = _build_report(lang, items, "total")
    keyboard = _build_time_filter_keyboard(lang, "total")

    # Telegram xabar uzunligi limitidan oshmasligi uchun bo'laklab yuboramiz
    CHUNK = 3500
    if len(text) <= CHUNK:
        await message.answer(text, reply_markup=keyboard)
        return

    start = 0
    while start < len(text):
        if start == 0:
            await message.answer(text[start:start+CHUNK], reply_markup=keyboard)
        else:
            await message.answer(text[start:start+CHUNK])
        start += CHUNK

# ---------------- CALLBACK HANDLERS ----------------

@router.callback_query(F.data.startswith("staff_filter_"))
async def staff_filter_callback(callback: CallbackQuery, state: FSMContext):
    lang = await _get_lang(callback.from_user.id)
    filter_type = callback.data.replace("staff_filter_", "")
    
    items = await fetch_staff_activity_with_time_filter(filter_type)
    text = _build_report(lang, items, filter_type)
    keyboard = _build_time_filter_keyboard(lang, filter_type)
    
    # Telegram xabar uzunligi limitidan oshmasligi uchun bo'laklab yuboramiz
    CHUNK = 3500
    if len(text) <= CHUNK:
        await callback.message.edit_text(text, reply_markup=keyboard)
        return
    
    # Agar xabar juda uzun bo'lsa, yangi xabar yuboramiz
    await callback.message.delete()
    start = 0
    while start < len(text):
        if start == 0:
            await callback.message.answer(text[start:start+CHUNK], reply_markup=keyboard)
        else:
            await callback.message.answer(text[start:start+CHUNK])
        start += CHUNK
    
    await callback.answer()
