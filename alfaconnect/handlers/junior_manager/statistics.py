# handlers/junior_manager/statistics.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from zoneinfo import ZoneInfo
from datetime import timezone, timedelta
import logging

from filters.role_filter import RoleFilter
from database.basic.user import get_user_by_telegram_id
from database.junior_manager.statistics import get_jm_stats_for_telegram

router = Router()
logger = logging.getLogger(__name__)
router.message.filter(RoleFilter("junior_manager"))
router.callback_query.filter(RoleFilter("junior_manager"))

# --- I18N ---
def _norm_lang(v: str | None) -> str:
    v = (v or "uz").lower()
    return "ru" if v.startswith("ru") else "uz"

TR = {
    "title": {
        "uz": "📊 <b>Kichik menejer — Statistika</b>\n",
        "ru": "📊 <b>Младший менеджер — Статистика</b>\n",
    },
    "today": {"uz": "📅 <b>Bugun</b>", "ru": "📅 <b>Сегодня</b>"},
    "7d": {"uz": "🗓 <b>So‘nggi 7 kun</b>", "ru": "🗓 <b>Последние 7 дней</b>"},
    "10d": {"uz": "🗓 <b>So‘nggi 10 kun</b>", "ru": "🗓 <b>Последние 10 дней</b>"},
    "30d": {"uz": "🗓 <b>So‘nggi 30 kun</b>", "ru": "🗓 <b>Последние 30 дней</b>"},
    "received": {"uz": "• Qabul qilingan", "ru": "• Принято"},
    "sent_to_controller": {"uz": "• Controllerga yuborilgan", "ru": "• Отправлено контролёру"},
    "completed_from_sent": {
        "uz": "• Yuborganlaridan <code>completed</code>",
        "ru": "• Из отправленных <code>completed</code>",
    },
    # 🆕 staff_orders metrikalari:
    "created_by_me": {"uz": "• O‘zim yaratgan", "ru": "• Создано мной"},
    "created_completed": {"uz": "• O‘zim yaratganlardan <code>completed</code>",
                          "ru": "• Из созданных мной <code>completed</code>"},
    "no_user": {
        "uz": "Foydalanuvchi profili topilmadi (users jadvali bilan moslik yo'q).",
        "ru": "Профиль пользователя не найден (нет соответствия с таблицей users).",
    },
    "total_orders": {"uz": "📊 Jami arizalar", "ru": "📊 Всего заявок"},
    "new_orders": {"uz": "🆕 Yangi arizalar", "ru": "🆕 Новые заявки"},
    "in_progress_orders": {"uz": "⏳ Ishlayotgan arizalar", "ru": "⏳ Заявки в работе"},
    "completed_orders": {"uz": "✅ Tugallangan arizalar", "ru": "✅ Завершённые заявки"},
    "today_completed": {"uz": "📅 Bugun tugallangan", "ru": "📅 Завершено сегодня"},
}

def tr(lang: str, key: str) -> str:
    lang = _norm_lang(lang)
    return TR.get(key, {}).get(lang, key)

# --- Timezone ---

# --- Format helpers ---

def _fmt_stats(lang: str, stats: dict) -> str:
    if not stats:
        return tr(lang, "no_user")
    
    manager_name = stats.get("manager_name", "Noma'lum")
    
    return (
        f"📊 <b>Kichik menejer — {manager_name}</b>\n\n"
        f"{tr(lang, 'total_orders')}: <b>{stats.get('total_orders', 0)}</b>\n"
        f"{tr(lang, 'new_orders')}: <b>{stats.get('new_orders', 0)}</b>\n"
        f"{tr(lang, 'in_progress_orders')}: <b>{stats.get('in_progress_orders', 0)}</b>\n"
        f"{tr(lang, 'completed_orders')}: <b>{stats.get('completed_orders', 0)}</b>\n"
        f"{tr(lang, 'today_completed')}: <b>{stats.get('today_completed', 0)}</b>\n"
    )

# --- Entry (reply button) ---
ENTRY_TEXTS = [
    "📊 Statistika",  # uz
    "📊 Статистика",  # ru
]

@router.message(F.text.in_(ENTRY_TEXTS))
async def jm_stats_msg(msg: Message, state: FSMContext):
    # tilni olish uchun foydalanuvchini DBdan olamiz
    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = _norm_lang(u.get("language") if u else "uz")

    stats = await get_jm_stats_for_telegram(msg.from_user.id)
    if not stats:
        await msg.answer(tr(lang, "no_user"))
        return
    await msg.answer(_fmt_stats(lang, stats))

# --- Callback variant ---
@router.callback_query(F.data == "jm_stats")
async def jm_stats_cb(cb: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(cb.from_user.id)
    lang = _norm_lang(u.get("language") if u else "uz")

    stats = await get_jm_stats_for_telegram(cb.from_user.id)
    if not stats:
        await cb.message.edit_text(tr(lang, "no_user"))
        return
    await cb.message.edit_text(_fmt_stats(lang, stats))
