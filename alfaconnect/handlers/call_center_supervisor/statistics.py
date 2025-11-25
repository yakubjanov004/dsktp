from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import logging
from datetime import datetime, timedelta

from filters.role_filter import RoleFilter
from database.basic.user import get_user_by_telegram_id
from database.call_center_supervisor.statistics import (
    get_callcenter_comprehensive_stats,
    get_operator_orders_stat,
    get_daily_statistics,
    get_monthly_statistics,
    get_status_statistics,
    get_type_statistics,
    get_performance_metrics,
    get_active_connection_tasks_count,
    get_callcenter_operator_count,
    get_canceled_connection_tasks_count,
)

router = Router()
logger = logging.getLogger(__name__)
router.message.filter(RoleFilter("callcenter_supervisor"))
router.callback_query.filter(RoleFilter("callcenter_supervisor"))

# ---------------- I18N ----------------
T = {
    "title": {
        "uz": "📊 Call Center Statistika",
        "ru": "📊 Статистика Call Center",
    },
    "overview": {
        "uz": "📈 Umumiy ko'rinish",
        "ru": "📈 Общий обзор",
    },
    "operators": {
        "uz": "👥 Operatorlar",
        "ru": "👥 Операторы",
    },
    "daily": {
        "uz": "📅 Kunlik statistika",
        "ru": "📅 Дневная статистика",
    },
    "monthly": {
        "uz": "📆 Oylik statistika",
        "ru": "📆 Месячная статистика",
    },
    "status": {
        "uz": "📊 Status bo'yicha",
        "ru": "📊 По статусам",
    },
    "type": {
        "uz": "🔧 Tur bo'yicha",
        "ru": "🔧 По типам",
    },
    "performance": {
        "uz": "⚡ Ishlash ko'rsatkichlari",
        "ru": "⚡ Показатели производительности",
    },
    "refresh": {
        "uz": "♻️ Yangilash",
        "ru": "♻️ Обновить",
    },
    "back": {
        "uz": "⬅️ Orqaga",
        "ru": "⬅️ Назад",
    },
    "total_operators": {
        "uz": "Jami operatorlar",
        "ru": "Всего операторов",
    },
    "total_supervisors": {
        "uz": "Jami supervisorlar",
        "ru": "Всего супервизоров",
    },
    "today_orders": {
        "uz": "Bugungi arizalar",
        "ru": "Заявки за сегодня",
    },
    "week_orders": {
        "uz": "Haftalik arizalar",
        "ru": "Заявки за неделю",
    },
    "month_orders": {
        "uz": "Oylik arizalar",
        "ru": "Заявки за месяц",
    },
    "active_orders": {
        "uz": "Aktiv arizalar",
        "ru": "Активные заявки",
    },
    "completed_orders": {
        "uz": "Tugallangan arizalar",
        "ru": "Завершенные заявки",
    },
    "cancelled_orders": {
        "uz": "Bekor qilingan arizalar",
        "ru": "Отмененные заявки",
    },
    "avg_completion_time": {
        "uz": "O'rtacha tugallanish vaqti",
        "ru": "Среднее время завершения",
    },
    "hours": {
        "uz": "soat",
        "ru": "часов",
    },
    "no_data": {
        "uz": "📭 Ma'lumotlar mavjud emas",
        "ru": "📭 Данные отсутствуют",
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

def _build_main_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Asosiy statistika keyboard"""
    builder = InlineKeyboardBuilder()
    
    buttons = [
        ("overview", _t(lang, "overview")),
        ("operators", _t(lang, "operators")),
        ("daily", _t(lang, "daily")),
        ("monthly", _t(lang, "monthly")),
        ("status", _t(lang, "status")),
        ("type", _t(lang, "type")),
        ("performance", _t(lang, "performance")),
        ("refresh", _t(lang, "refresh")),
    ]
    
    for callback_data, text in buttons:
        builder.button(text=text, callback_data=f"ccs_stats_{callback_data}")
    
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()

def _build_back_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Orqaga qaytish keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text=_t(lang, "back"), callback_data="ccs_stats_back")
    builder.button(text=_t(lang, "refresh"), callback_data="ccs_stats_refresh")
    return builder.as_markup()

def _format_overview_stats(lang: str, stats: dict) -> str:
    """Umumiy statistika formatlash"""
    overview = stats.get('overview', {})
    
    text = f"{_t(lang, 'title')}\n\n"
    text += f"{_t(lang, 'overview')}\n\n"
    
    text += f"👥 {_t(lang, 'total_operators')}: {overview.get('total_operators', 0)}\n"
    text += f"👨‍💼 {_t(lang, 'total_supervisors')}: {overview.get('total_supervisors', 0)}\n"
    text += f"📅 {_t(lang, 'today_orders')}: {overview.get('today_orders', 0)}\n"
    text += f"📊 {_t(lang, 'week_orders')}: {overview.get('week_orders', 0)}\n"
    text += f"📆 {_t(lang, 'month_orders')}: {overview.get('month_orders', 0)}\n"
    
    return text

def _format_operator_stats(lang: str, stats: dict) -> str:
    """Operatorlar statistikasi formatlash"""
    operators = stats.get('operator_statistics', [])
    
    text = f"{_t(lang, 'title')}\n\n"
    text += f"{_t(lang, 'operators')}\n\n"
    
    if not operators:
        text += _t(lang, "no_data")
        return text
    
    for i, op in enumerate(operators[:10], 1):  # Faqat top 10
        name = op.get('full_name', 'N/A')
        total = op.get('total_orders', 0)
        active = op.get('active_orders', 0)
        completed = op.get('completed_orders', 0)
        today = op.get('today_orders', 0)
        
        text += f"{i}. {name}\n"
        text += f"   📊 Jami: {total} | ⚡ Aktiv: {active} | ✅ Tugallangan: {completed} | 📅 Bugun: {today}\n\n"
    
    return text

def _format_daily_stats(lang: str, daily_trends: list) -> str:
    """Kunlik statistika formatlash"""
    text = f"{_t(lang, 'title')}\n\n"
    text += f"{_t(lang, 'daily')}\n\n"
    
    if not daily_trends:
        text += _t(lang, "no_data")
        return text
    
    for day in daily_trends[:7]:  # Faqat oxirgi 7 kun
        date = day.get('date', '')
        total = day.get('total_orders', 0)
        active = day.get('active_orders', 0)
        completed = day.get('completed_orders', 0)
        
        text += f"📅 {date}\n"
        text += f"   📊 Jami: {total} | ⚡ Aktiv: {active} | ✅ Tugallangan: {completed}\n\n"
    
    return text

def _format_status_stats(lang: str, status_stats: dict) -> str:
    """Status bo'yicha statistika formatlash"""
    text = f"{_t(lang, 'title')}\n\n"
    text += f"{_t(lang, 'status')}\n\n"
    
    if not status_stats:
        text += _t(lang, "no_data")
        return text
    
    for status, count in status_stats.items():
        text += f"📊 {status}: {count}\n"
    
    return text

def _format_type_stats(lang: str, type_stats: dict) -> str:
    """Tur bo'yicha statistika formatlash"""
    text = f"{_t(lang, 'title')}\n\n"
    text += f"{_t(lang, 'type')}\n\n"
    
    if not type_stats:
        text += _t(lang, "no_data")
        return text
    
    for type_name, count in type_stats.items():
        text += f"🔧 {type_name}: {count}\n"
    
    return text

def _format_performance_stats(lang: str, performance: dict) -> str:
    """Ishlash ko'rsatkichlari formatlash"""
    text = f"{_t(lang, 'title')}\n\n"
    text += f"{_t(lang, 'performance')}\n\n"
    
    today = performance.get('today', {})
    week = performance.get('week', {})
    
    if today:
        text += f"📅 Bugun:\n"
        text += f"   📊 Jami: {today.get('total_orders', 0)}\n"
        text += f"   ✅ Tugallangan: {today.get('completed_orders', 0)}\n"
        text += f"   ❌ Bekor qilingan: {today.get('cancelled_orders', 0)}\n"
        avg_time = today.get('avg_completion_hours', 0)
        if avg_time:
            text += f"   ⏱️ {_t(lang, 'avg_completion_time')}: {avg_time:.1f} {_t(lang, 'hours')}\n"
        text += "\n"
    
    if week:
        text += f"📊 Hafta:\n"
        text += f"   📊 Jami: {week.get('total_orders', 0)}\n"
        text += f"   ✅ Tugallangan: {week.get('completed_orders', 0)}\n"
        text += f"   ❌ Bekor qilingan: {week.get('cancelled_orders', 0)}\n"
        avg_time = week.get('avg_completion_hours', 0)
        if avg_time:
            text += f"   ⏱️ {_t(lang, 'avg_completion_time')}: {avg_time:.1f} {_t(lang, 'hours')}\n"
    
    return text

async def _get_lang(user_tg_id: int) -> str:
    """User tilini olish"""
    user = await get_user_by_telegram_id(user_tg_id)
    lng = (user or {}).get("language")
    return _norm_lang(lng)

# ---------------- ENTRY ----------------

UZ_ENTRY_TEXT = "📊 Statistikalar"
RU_ENTRY_TEXT = "📊 Статистика"

@router.message(F.text.in_([UZ_ENTRY_TEXT, RU_ENTRY_TEXT]))
async def callcenter_statistics_entry(message: Message, state: FSMContext):
    """Call center statistika asosiy menyu"""
    lang = await _get_lang(message.from_user.id)
    
    # Oddiy statistika (eski versiya bilan moslik uchun)
    active_tasks = await get_active_connection_tasks_count()
    co_count = await get_callcenter_operator_count()
    canceled_tasks = await get_canceled_connection_tasks_count()
    
    text = f"{_t(lang, 'title')}\n\n"
    text += f"🧾 {_t(lang, 'active_orders')}: {active_tasks}\n"
    text += f"🧑‍💼 Jami xodimlar: {co_count}\n"
    text += f"❌ {_t(lang, 'cancelled_orders')}: {canceled_tasks}\n\n"
    text += "Quyidagi bo'limlardan birini tanlang:" if lang == "uz" else "Выберите один из следующих разделов:"
    
    await message.answer(
        text,
        reply_markup=_build_main_keyboard(lang)
    )

# ---------------- CALLBACK HANDLERS ----------------

@router.callback_query(F.data.startswith("ccs_stats_"))
async def callcenter_statistics_callback(callback: CallbackQuery, state: FSMContext):
    """Statistika callback handler"""
    lang = "uz"
    try:
        action = callback.data.replace("ccs_stats_", "")
        lang = await _get_lang(callback.from_user.id)
        
        if action == "back":
            # Asosiy menyuga qaytish
            active_tasks = await get_active_connection_tasks_count()
            co_count = await get_callcenter_operator_count()
            canceled_tasks = await get_canceled_connection_tasks_count()
            
            text = f"{_t(lang, 'title')}\n\n"
            text += f"🧾 {_t(lang, 'active_orders')}: {active_tasks}\n"
            text += f"🧑‍💼 Jami xodimlar: {co_count}\n"
            text += f"❌ {_t(lang, 'cancelled_orders')}: {canceled_tasks}\n\n"
            text += "Quyidagi bo'limlardan birini tanlang:" if lang == "uz" else "Выберите один из следующих разделов:"
            
            await callback.message.edit_text(
                text,
                reply_markup=_build_main_keyboard(lang)
            )
            return
        
        elif action == "refresh":
            await callback.answer("Yangilanmoqda…" if lang == "uz" else "Обновляется…")
            # Asosiy menyuni yangilash
            active_tasks = await get_active_connection_tasks_count()
            co_count = await get_callcenter_operator_count()
            canceled_tasks = await get_canceled_connection_tasks_count()
            
            text = f"{_t(lang, 'title')}\n\n"
            text += f"🧾 {_t(lang, 'active_orders')}: {active_tasks}\n"
            text += f"🧑‍💼 Jami xodimlar: {co_count}\n"
            text += f"❌ {_t(lang, 'cancelled_orders')}: {canceled_tasks}\n\n"
            text += "Quyidagi bo'limlardan birini tanlang:" if lang == "uz" else "Выберите один из следующих разделов:"
            
            await callback.message.edit_text(
                text,
                reply_markup=_build_main_keyboard(lang)
            )
            return
        
        elif action == "overview":
            stats = await get_callcenter_comprehensive_stats()
            text = _format_overview_stats(lang, stats)
            await callback.message.edit_text(
                text,
                reply_markup=_build_back_keyboard(lang)
            )
        
        elif action == "operators":
            stats = await get_callcenter_comprehensive_stats()
            text = _format_operator_stats(lang, stats)
            await callback.message.edit_text(
                text,
                reply_markup=_build_back_keyboard(lang)
            )
        
        elif action == "daily":
            stats = await get_callcenter_comprehensive_stats()
            text = _format_daily_stats(lang, stats.get('daily_trends', []))
            await callback.message.edit_text(
                text,
                reply_markup=_build_back_keyboard(lang)
            )
        
        elif action == "monthly":
            monthly_stats = await get_monthly_statistics(6)
            text = f"{_t(lang, 'title')}\n\n"
            text += f"{_t(lang, 'monthly')}\n\n"
            
            if monthly_stats:
                for month_data in monthly_stats[:6]:
                    month = month_data.get('month', '')
                    total = month_data.get('total_orders', 0)
                    active = month_data.get('active_orders', 0)
                    completed = month_data.get('completed_orders', 0)
                    
                    text += f"📆 {month}\n"
                    text += f"   📊 Jami: {total} | ⚡ Aktiv: {active} | ✅ Tugallangan: {completed}\n\n"
            else:
                text += _t(lang, "no_data")
            
            await callback.message.edit_text(
                text,
                reply_markup=_build_back_keyboard(lang)
            )
        
        elif action == "status":
            status_stats = await get_status_statistics()
            text = _format_status_stats(lang, status_stats)
            await callback.message.edit_text(
                text,
                reply_markup=_build_back_keyboard(lang)
            )
        
        elif action == "type":
            type_stats = await get_type_statistics()
            text = _format_type_stats(lang, type_stats)
            await callback.message.edit_text(
                text,
                reply_markup=_build_back_keyboard(lang)
            )
        
        elif action == "performance":
            performance = await get_performance_metrics()
            text = _format_performance_stats(lang, performance)
            await callback.message.edit_text(
                text,
                reply_markup=_build_back_keyboard(lang)
            )
        
        await callback.answer()
        
    except TelegramBadRequest as e:
        message = str(e)
        if "message is not modified" in message:
            notify = "Kontent allaqachon yangilangan" if lang == "uz" else "Контент уже актуален"
            await callback.answer(notify)
            return
        logger.error(f"Call center statistics callback error: {e}")
        await callback.answer("Xatolik yuz berdi!", show_alert=True)

    except Exception as e:
        logger.error(f"Call center statistics callback error: {e}")
        await callback.answer("Xatolik yuz berdi!", show_alert=True)
