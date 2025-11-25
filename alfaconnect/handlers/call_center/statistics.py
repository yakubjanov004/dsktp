from typing import Dict
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from filters.role_filter import RoleFilter
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime
import logging

from database.call_center.statistics import (
    get_user_id_by_telegram_id,
    get_operator_stats_by_range,
)
from database.basic.language import get_user_language
router = Router()
logger = logging.getLogger(__name__)
router.message.filter(RoleFilter("callcenter_operator"))
router.callback_query.filter(RoleFilter("callcenter_operator"))

# --- Localization helpers ---
def t(lang: str, key: str) -> str:
    uz = {
        "stats_title": "📊 <b>Call-center statistikasi — {range_title}</b>\n\n"
                       "🔌 Ulanish arizalari (connection_orders): <b>{co}</b>\n"
                       "🛠️ Texnik arizalar (technician_orders): <b>{to}</b>\n"
                       "📤 Controllerga yuborilgan: <b>{sent}</b>\n"
                       "✅ Operator yopgan arizalar: <b>{closed}</b>\n",
        "err_no_operator": "❌ Operator tizimda topilmadi. Avval ro‘yxatdan o‘tkazing.",
        "err_bad_range": "Noto‘g‘ri oraliq",
        "btn_prev": "⬅️ Oldingisi",
        "btn_next": "➡️ Keyingisi",
        "btn_refresh": "🔄 Yangilash",
        "range_day": "1 kun",
        "range_week": "1 hafta",
        "range_month": "1 oy",
        "range_year": "1 yil",
        "refreshed": "🔄 Yangilandi",
    }
    ru = {
        "stats_title": "📊 <b>Статистика колл-центра — {range_title}</b>\n\n"
                       "🔌 Заявки на подключение (connection_orders): <b>{co}</b>\n"
                       "🛠️ Технические заявки (technician_orders): <b>{to}</b>\n"
                       "📤 Отправлено контроллеру: <b>{sent}</b>\n"
                       "✅ Закрыто оператором: <b>{closed}</b>\n",
        "err_no_operator": "❌ Профиль оператора не найден. Сначала зарегистрируйте в системе.",
        "err_bad_range": "Неверный интервал",
        "btn_prev": "⬅️ Предыдущая",
        "btn_next": "➡️ Следующая",
        "btn_refresh": "🔄 Обновить",
        "range_day": "1 день",
        "range_week": "1 неделя",
        "range_month": "1 месяц",
        "range_year": "1 год",
        "refreshed": "🔄 Обновлено",
    }
    table = uz if lang == "uz" else ru
    return table.get(key, key)

# Faqat whitelist: SQLga qo‘yiladigan interval matni
INTERVALS = {
    "day":   "1 day",
    "week":  "7 days",
    "month": "1 month",
    "year":  "1 year",
}

def range_title(lang: str, key: str) -> str:
    mapping = {
        "day": t(lang, "range_day"),
        "week": t(lang, "range_week"),
        "month": t(lang, "range_month"),
        "year": t(lang, "range_year"),
    }
    return mapping.get(key, t(lang, "range_day"))

def ranges_keyboard(lang: str, active_key: str = "day") -> InlineKeyboardMarkup:
    labels = {
        "day": range_title(lang, "day"),
        "week": range_title(lang, "week"),
        "month": range_title(lang, "month"),
        "year": range_title(lang, "year"),
    }
    rows = []
    row = []
    for key in ("day", "week", "month", "year"):
        label = f"✅ {labels[key]}" if key == active_key else labels[key]
        row.append(InlineKeyboardButton(text=label, callback_data=f"stats_range:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t(lang, "btn_refresh"),
                                      callback_data=f"stats_refresh:{active_key}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def render_stats_text(lang: str, stats: Dict[str, int], range_key: str) -> str:
    return t(lang, "stats_title").format(
        range_title=range_title(lang, range_key),
        co=stats["connection_orders_total"],
        to=stats["technician_orders_total"],
        sent=stats["sent_to_controller_total"],
        closed=stats["closed_by_operator_total"],
    )

# === /statistika ===
@router.message(F.text.in_(["📊 Statistikalar", "📊 Статистика"]))
async def statistics_handler(message: Message):
    # foydalanuvchi tilini olamiz (uz/ru), default uz
    lang = await get_user_language(message.from_user.id) or "uz"

    operator_id = await get_user_id_by_telegram_id(message.from_user.id)
    if not operator_id:
        await message.answer(t(lang, "err_no_operator"))
        return

    # default: 1 kun (UZ) / 1 день (RU) -> interval 'day'
    stats = await get_operator_stats_by_range(operator_id, "day")
    text = render_stats_text(lang, stats, "day")
    await message.answer(text, reply_markup=ranges_keyboard(lang, "day"), parse_mode="HTML")

# === Inline: vaqt oraliqlarini almashtirish ===
@router.callback_query(F.data.startswith("stats_range:"))
async def stats_range(cq: CallbackQuery):
    lang = await get_user_language(cq.from_user.id) or "uz"

    key = cq.data.split(":")[1]
    if key not in INTERVALS:
        await cq.answer(t(lang, "err_bad_range"), show_alert=True)
        return

    operator_id = await get_user_id_by_telegram_id(cq.from_user.id)
    if not operator_id:
        await cq.answer(t(lang, "err_no_operator"), show_alert=True)
        return

    stats = await get_operator_stats_by_range(operator_id, key)
    text = render_stats_text(lang, stats, key)
    try:
        await cq.message.edit_text(
            text,
            reply_markup=ranges_keyboard(lang, key),
            parse_mode="HTML",
        )
    except TelegramBadRequest as e:
        # Aktiv oraliqni yana bosganda yoki kontent aynan bir xil bo'lsa shu keladi
        if "message is not modified" in str(e):
            # shunchaki toast ko'rsatamiz
            await cq.answer(range_title(lang, key))
            return
        raise
    await cq.answer(range_title(lang, key))


@router.callback_query(F.data.startswith("stats_refresh:"))
async def stats_refresh(cq: CallbackQuery):
    lang = await get_user_language(cq.from_user.id) or "uz"

    key = cq.data.split(":")[1]
    if key not in INTERVALS:
        key = "day"

    operator_id = await get_user_id_by_telegram_id(cq.from_user.id)
    if not operator_id:
        await cq.answer(t(lang, "err_no_operator"), show_alert=True)
        return

    stats = await get_operator_stats_by_range(operator_id, key)
    text = render_stats_text(lang, stats, key) + f"\n<i>{datetime.now().strftime('%H:%M:%S')}</i>"
    try:
        await cq.message.edit_text(
            text,
            reply_markup=ranges_keyboard(lang, key),
            parse_mode="HTML",
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Hech narsa o'zgarmagan bo'lsa — faqat toast
            await cq.answer(t(lang, "refreshed"))
            return
        raise
    await cq.answer(t(lang, "refreshed"))
