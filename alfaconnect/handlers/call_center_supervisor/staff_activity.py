from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import logging
from datetime import datetime, timedelta

from filters.role_filter import RoleFilter
from database.basic.user import get_user_by_telegram_id
from database.call_center_supervisor.staff_activity import fetch_callcenter_staff_activity_with_time_filter

router = Router()
logger = logging.getLogger(__name__)
router.message.filter(RoleFilter("callcenter_supervisor"))
router.callback_query.filter(RoleFilter("callcenter_supervisor"))

# ---------------- I18N ----------------
T = {
    "title": {
        "uz": "👥 Xodimlar faoliyati",
        "ru": "👥 Активность сотрудников",
    },
    "legend": {
        "uz": "📊 Call center operator va supervisorlar faoliyati",
        "ru": "📊 Активность операторов и супервизоров call center",
    },
    "time_filter": {
        "uz": "Vaqt bo'yicha filtrlash:",
        "ru": "Фильтр по времени:",
    },
    "btn_today": {"uz": "📅 Bugun", "ru": "📅 Сегодня"},
    "btn_7days": {"uz": "📅 Hafta", "ru": "📅 Неделя"},
    "btn_month": {"uz": "📅 Oy", "ru": "📅 Месяц"},
    "btn_total": {"uz": "📅 Jami", "ru": "📅 Всего"},
    "period_today": {"uz": "Bugungi hisobot", "ru": "Отчёт за сегодня"},
    "period_7days": {"uz": "Haftalik hisobot", "ru": "Недельный отчёт"},
    "period_month": {"uz": "So'nggi oy", "ru": "Последний месяц"},
    "period_total": {"uz": "Jami hisobot", "ru": "Общий отчёт"},
    "totals": {
        "uz": "📈 Jami: {staff_cnt} xodim | Ulanish: {conn_sum} ta | Texnik: {tech_sum} ta | Xodim: {staff_sum} ta | Barcha arizalar: {total_sum} ta",
        "ru": "📈 Всего: {staff_cnt} сотрудников | Подключение: {conn_sum} шт. | Технические: {tech_sum} шт. | Служебные: {staff_sum} шт. | Все заявки: {total_sum} шт.",
    },
    "conn": {"uz": "Ulanish", "ru": "Подключение"},
    "conn_assigned": {"uz": "📥 Ulanish arizalari (tayinlangan)", "ru": "📥 Заявки на подключение (назначенные)"},
    "conn_created": {"uz": "📤 Ulanish arizalari (yaratilgan)", "ru": "📤 Заявки на подключение (созданные)"},
    "conn_sent": {"uz": "📤 Ulanish arizalari (yuborilgan)", "ru": "📤 Заявки на подключение (отправленные)"},
    "tech_created": {"uz": "🔧 Texnik arizalar (yaratilgan)", "ru": "🔧 Технические заявки (созданные)"},
    "tech_assigned": {"uz": "📥 Texnik arizalar (tayinlangan)", "ru": "📥 Технические заявки (назначенные)"},
    "tech_sent": {"uz": "🔧 Texnik arizalar (yuborilgan)", "ru": "🔧 Технические заявки (отправленные)"},
    "staff_created": {"uz": "📋 Xodim arizalari (yaratilgan)", "ru": "📋 Служебные заявки (созданные)"},
    "staff_assigned": {"uz": "📥 Xodim arizalari (tayinlangan)", "ru": "📥 Служебные заявки (назначенные)"},
    "staff_sent": {"uz": "📋 Xodim arizalari (yuborilgan)", "ru": "📋 Служебные заявки (отправленные)"},
    "active": {"uz": "⚡ Hozir ishlayotgan", "ru": "⚡ Сейчас в работе"},
    "role_operator": {"uz": "Operator", "ru": "Оператор"},
    "role_supervisor": {"uz": "Supervisor", "ru": "Супервизор"},
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
    if key not in T:
        return f"[{key}]"
    text = T[key].get(lang, T[key]["uz"])
    if fmt:
        try:
            text = text.format(**fmt)
        except KeyError:
            pass
    return text

def _role_label(lang: str, role: str) -> str:
    role = (role or "").lower()
    if role == "callcenter_supervisor":
        return _t(lang, "role_supervisor")
    return _t(lang, "role_operator")

def _medal(i: int) -> str:
    return "🥇" if i == 0 else ("🥈" if i == 1 else ("🥉" if i == 2 else "•"))

def _build_time_filter_keyboard(lang: str, current_filter: str) -> InlineKeyboardMarkup:
    """Vaqt filtri keyboard yaratish"""
    builder = InlineKeyboardBuilder()
    
    filters = [
        ("today", _t(lang, "btn_today")),
        ("7days", _t(lang, "btn_7days")),
        ("month", _t(lang, "btn_month")),
        ("total", _t(lang, "btn_total")),
    ]
    
    for filter_key, filter_text in filters:
        if filter_key == current_filter:
            filter_text = f"✅ {filter_text}"
        builder.button(text=filter_text, callback_data=f"ccs_staff_filter_{filter_key}")
    
    builder.adjust(2, 2)
    return builder.as_markup()

def _build_report(lang: str, items: list, period: str) -> str:
    """Hisobot matnini yaratish - manager kabi to'liq funksionallik"""
    if not items:
        return _t(lang, "empty")
    
    # Period matni
    period_texts = {
        "today": _t(lang, "period_today"),
        "7days": _t(lang, "period_7days"),
        "month": _t(lang, "period_month"),
        "total": _t(lang, "period_total"),
    }
    period_text = period_texts.get(period, period)
    
    # Jami hisoblar
    total_conn = sum(item.get("conn_count", 0) for item in items)
    total_tech = sum(item.get("tech_count", 0) for item in items)
    total_staff = sum(item.get("created_staff_count", 0) + item.get("assigned_staff_count", 0) + item.get("sent_staff_count", 0) for item in items)
    total_all = sum(item.get("total_orders", 0) for item in items)
    staff_count = len(items)
    
    # Header
    text = f"{_t(lang, 'title')}\n"
    text += f"{_t(lang, 'legend')}\n\n"
    text += f"📊 {period_text}\n"
    text += f"{_t(lang, 'time_filter')}\n\n"
    
    # Jami statistika
    text += _t(lang, "totals", 
               staff_cnt=staff_count,
               conn_sum=total_conn,
               tech_sum=total_tech,
               staff_sum=total_staff,
               total_sum=total_all) + "\n\n"
    
    # Har bir xodim uchun - manager kabi batafsil ko'rinish
    for i, item in enumerate(items):
        name = item.get("full_name", "N/A")
        role = _role_label(lang, item.get("role", ""))
        active = item.get("active_count", 0)
        
        # Medal emojisi bilan
        text += f"{i+1}. {_medal(i)} {name} ({role})\n"
        
        # Birliklarni UZ: "ta" / RU: "шт."
        unit = "ta" if _norm_lang(lang) == "uz" else "шт."
        
        # Ulanish arizalari
        conn_assigned = item.get("assigned_conn_count", 0)
        conn_created = item.get("created_conn_count", 0)
        conn_sent = item.get("sent_conn_count", 0)
        
        if conn_assigned > 0:
            text += f"├ {_t(lang, 'conn_assigned')}: {conn_assigned} {unit}\n"
        if conn_created > 0:
            text += f"├ {_t(lang, 'conn_created')}: {conn_created} {unit}\n"
        if conn_sent > 0:
            text += f"├ {_t(lang, 'conn_sent')}: {conn_sent} {unit}\n"
        
        # Texnik arizalar
        tech_created = item.get("created_tech_count", 0)
        tech_assigned = item.get("assigned_tech_count", 0)
        tech_sent = item.get("sent_tech_count", 0)
        
        if tech_created > 0:
            text += f"├ {_t(lang, 'tech_created')}: {tech_created} {unit}\n"
        if tech_assigned > 0:
            text += f"├ {_t(lang, 'tech_assigned')}: {tech_assigned} {unit}\n"
        if tech_sent > 0:
            text += f"├ {_t(lang, 'tech_sent')}: {tech_sent} {unit}\n"
        
        # Xodim arizalari
        staff_created = item.get("created_staff_count", 0)
        staff_assigned = item.get("assigned_staff_count", 0)
        staff_sent = item.get("sent_staff_count", 0)
        
        if staff_created > 0:
            text += f"├ {_t(lang, 'staff_created')}: {staff_created} {unit}\n"
        if staff_assigned > 0:
            text += f"├ {_t(lang, 'staff_assigned')}: {staff_assigned} {unit}\n"
        if staff_sent > 0:
            text += f"├ {_t(lang, 'staff_sent')}: {staff_sent} {unit}\n"
        
        # Aktiv arizalar
        text += f"└ {_t(lang, 'active')}: {active} {unit}\n\n"
    
    return text

async def _get_lang(user_tg_id: int) -> str:
    """User tilini olish"""
    user = await get_user_by_telegram_id(user_tg_id)
    lng = (user or {}).get("language")
    return _norm_lang(lng)

# ---------------- ENTRY ----------------

UZ_ENTRY_TEXT = "👥 Xodimlar faoliyati"
RU_ENTRY_TEXT = "👥 Активность сотрудников"

@router.message(F.text.in_([UZ_ENTRY_TEXT, RU_ENTRY_TEXT]))
async def callcenter_staff_activity_entry(message: Message, state: FSMContext):
    lang = await _get_lang(message.from_user.id)
    items = await fetch_callcenter_staff_activity_with_time_filter("total")
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

@router.callback_query(F.data.startswith("ccs_staff_filter_"))
async def callcenter_staff_filter_callback(callback: CallbackQuery, state: FSMContext):
    """Vaqt filtri callback handler"""
    try:
        filter_type = callback.data.replace("ccs_staff_filter_", "")
        lang = await _get_lang(callback.from_user.id)
        
        items = await fetch_callcenter_staff_activity_with_time_filter(filter_type)
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
            
    except Exception as e:
        logger.error(f"Call center staff filter callback error: {e}")
        await callback.answer("Xatolik yuz berdi!", show_alert=True)