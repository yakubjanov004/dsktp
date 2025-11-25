# handlers/junior_manager/client_search.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.fsm.state import StatesGroup, State
import html
import re
import logging

from filters.role_filter import RoleFilter
from database.basic.user import get_user_by_telegram_id, find_user_by_phone
from database.junior_manager.orders import (
    get_client_order_history,
    get_client_order_count,
)

router = Router()
logger = logging.getLogger(__name__)
router.message.filter(RoleFilter("junior_manager"))
router.callback_query.filter(RoleFilter("junior_manager"))

# --- State ---
class JMClientSearchStates(StatesGroup):
    waiting_client_phone = State()
    viewing_history = State()

# --- i18n helpers ---
def _norm_lang(v: str | None) -> str:
    v = (v or "ru").lower()
    return "ru" if v.startswith("ru") else "uz"

TR = {
    "prompt": {
        "uz": "📞 Qidirish uchun mijoz telefon raqamini kiriting (masalan, +998901234567):",
        "ru": "📞 Введите номер телефона клиента для поиска (например: +998901234567):",
    },
    "bad_format": {
        "uz": "❗️ Noto'g'ri format. Masalan: +998901234567",
        "ru": "❗️ Неверный формат. Например: +998901234567",
    },
    "not_found": {
        "uz": "❌ Bu raqam bo'yicha mijoz topilmadi. Qayta urinib ko'ring.",
        "ru": "❌ Клиент с таким номером не найден. Попробуйте снова.",
    },
    "found_title": {"uz": "✅ Mijoz topildi:", "ru": "✅ Клиент найден:"},
    "id": {"uz": "🆔 ID", "ru": "🆔 ID"},
    "fio": {"uz": "👤 F.I.Sh", "ru": "👤 ФИО"},
    "phone": {"uz": "📞 Telefon", "ru": "📞 Телефон"},
    "username": {"uz": "🌐 Username", "ru": "🌐 Username"},
    "region": {"uz": "📍 Region", "ru": "📍 Регион"},
    "address": {"uz": "🏠 Manzil", "ru": "🏠 Адрес"},
    "abonent": {"uz": "🔑 Abonent ID", "ru": "🔑 ID абонента"},
    "order_stats": {"uz": "📊 Ariza statistikasi:", "ru": "📊 Статистика заявок:"},
    "total_orders": {"uz": "Jami arizalar", "ru": "Всего заявок"},
    "connection_orders": {"uz": "Ulanishlar", "ru": "Подключения"},
    "staff_orders": {"uz": "Xizmatlar", "ru": "Служебные"},
    "tech_connection_orders": {"uz": "Texnik ulanishlar", "ru": "Технические подключения"},
    "smartservice_orders": {"uz": "SmartService", "ru": "SmartService"},
    "order_history": {"uz": "📋 Ariza tarixi:", "ru": "📋 История заявок:"},
    "no_history": {"uz": "Ariza tarixi bo'sh", "ru": "История заявок пуста"},
    "order_id": {"uz": "№", "ru": "№"},
    "order_status": {"uz": "Holat", "ru": "Статус"},
    "order_date": {"uz": "Sana", "ru": "Дата"},
    "order_type": {"uz": "Turi", "ru": "Тип"},
    "connection_type": {"uz": "Ulanish", "ru": "Подключение"},
    "staff_type": {"uz": "Xizmat", "ru": "Служебная"},
    "tech_connection_type": {"uz": "Texnik ulanish", "ru": "Техническое подключение"},
    "smartservice_type": {"uz": "SmartService", "ru": "SmartService"},
}

def t(lang: str, key: str) -> str:
    lang = _norm_lang(lang)
    val = TR.get(key)
    if isinstance(val, dict):
        return val.get(lang, val.get("uz", key))
    return val or key

def _esc(v) -> str:
    return html.escape(str(v) if v is not None else "-", quote=False)

# --- Local format validator (oddiy feedback uchun) ---
_PHONE_RE = re.compile(
    r"^\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$|^\+?998\d{9}$|^\d{9,12}$"
)
def _looks_like_phone(raw: str) -> bool:
    return bool(_PHONE_RE.match((raw or "").strip()))

def _create_history_keyboard(current_page: int, total_pages: int, lang: str) -> InlineKeyboardMarkup:
    """Ariza tarixi uchun paginatsiya tugmalari"""
    kb = InlineKeyboardBuilder()
    
    if total_pages > 1:
        if current_page > 0:
            kb.button(text="⬅️ Oldingi", callback_data=f"history_prev:{current_page}")
        kb.button(text=f"{current_page + 1}/{total_pages}", callback_data="noop")
        if current_page < total_pages - 1:
            kb.button(text="Keyingi ➡️", callback_data=f"history_next:{current_page}")
        kb.adjust(3)
    
    return kb.as_markup()

async def _show_history_page(message: Message, history: list, page: int, lang: str, user_info: dict = None, order_count: dict = None):
    """Ariza tarixi sahifasini ko'rsatish"""
    ITEMS_PER_PAGE = 5
    total_pages = (len(history) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_history = history[start_idx:end_idx]
    
    # Mijoz ma'lumotlari va statistika
    text = ""
    if user_info and order_count:
        text += f"{t(lang,'found_title')}\n"
        text += f"{'=' * 40}\n\n"
        text += f"{t(lang,'id')}: <b>{_esc(user_info.get('id'))}</b>\n"
        text += f"{t(lang,'fio')}: <b>{_esc(user_info.get('full_name'))}</b>\n"
        text += f"{t(lang,'phone')}: <b>{_esc(user_info.get('phone'))}</b>\n"
        text += f"{t(lang,'username')}: <b>@{_esc(user_info.get('username'))}</b>\n"
        text += f"{t(lang,'region')}: <b>{_esc(user_info.get('region'))}</b>\n"
        text += f"{t(lang,'address')}: <b>{_esc(user_info.get('address'))}</b>\n"
        text += f"{t(lang,'abonent')}: <b>{_esc(user_info.get('abonent_id'))}</b>\n\n"
        text += f"<b>{t(lang,'order_stats')}</b>\n"
        text += f"• {t(lang,'total_orders')}: <b>{order_count['total_orders']}</b>\n"
        text += f"• {t(lang,'connection_orders')}: <b>{order_count['connection_orders']}</b>\n"
        text += f"• {t(lang,'tech_connection_orders')}: <b>{order_count['technician_orders']}</b>\n"
        text += f"• {t(lang,'smartservice_orders')}: <b>{order_count['smartservice_orders']}</b>\n\n"
    
    text += f"<b>{t(lang,'order_history')}</b>\n"
    text += f"{'=' * 30}\n\n"
    
    for order in page_history:
        order_id = _esc(order.get("application_number") or f"#{order.get('id')}")
        status = _esc(order.get("status") or "—")
        order_type_raw = order.get("order_type")
        
        # Ariza turini aniqlash
        if order_type_raw == "connection":
            order_type = t(lang, "connection_type")
        elif order_type_raw == "staff":
            order_type = t(lang, "staff_type")
        elif order_type_raw == "technician":
            order_type = t(lang, "tech_connection_type")
        elif order_type_raw == "smartservice":
            order_type = t(lang, "smartservice_type")
        else:
            order_type = order_type_raw or "—"
        
        created_at = order.get("created_at")
        
        if created_at and hasattr(created_at, 'strftime'):
            date_str = created_at.strftime("%d.%m.%Y %H:%M")
        else:
            date_str = str(created_at or "—")
        
        text += f"<b>{t(lang,'order_id')} {order_id}</b>\n"
        text += f"• {t(lang,'order_type')}: {order_type}\n"
        text += f"• {t(lang,'order_status')}: {status}\n"
        text += f"• {t(lang,'order_date')}: {date_str}\n\n"
    
    keyboard = _create_history_keyboard(page, total_pages, lang)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

# ===================== ENTRY (reply button) =====================
@router.message(F.text.in_(["🔍 Mijoz qidiruv", "🔍 Поиск клиентов"]))
async def jm_client_search_start(message: Message, state: FSMContext):
    u = await get_user_by_telegram_id(message.from_user.id)
    lang = _norm_lang(u.get("language") if u else "uz")

    await state.set_state(JMClientSearchStates.waiting_client_phone)
    await message.answer(t(lang, "prompt"))

# ===================== STEP: phone input =====================
@router.message(StateFilter(JMClientSearchStates.waiting_client_phone))
async def jm_client_search_process_phone(message: Message, state: FSMContext):
    u = await get_user_by_telegram_id(message.from_user.id)
    lang = _norm_lang(u.get("language") if u else "uz")

    phone = (message.text or "").strip()

    # Avval formatni tekshirib, foydalanuvchiga tezkor javob beramiz
    if not _looks_like_phone(phone):
        await message.answer(t(lang, "bad_format"))
        return

    user = await find_user_by_phone(phone)
    if not user:
        await message.answer(t(lang, "not_found"))
        return

    # Mijozning ariza sonini olish
    order_count = await get_client_order_count(user["id"])
    
    # Mijoz ma'lumotini chiqaramiz
    text = (
        f"{t(lang,'found_title')}\n"
        f"{'=' * 40}\n\n"
        f"{t(lang,'id')}: <b>{_esc(user.get('id'))}</b>\n"
        f"{t(lang,'fio')}: <b>{_esc(user.get('full_name'))}</b>\n"
        f"{t(lang,'phone')}: <b>{_esc(user.get('phone'))}</b>\n"
        f"{t(lang,'username')}: <b>@{_esc(user.get('username'))}</b>\n"
        f"{t(lang,'region')}: <b>{_esc(user.get('region'))}</b>\n"
        f"{t(lang,'address')}: <b>{_esc(user.get('address'))}</b>\n"
        f"{t(lang,'abonent')}: <b>{_esc(user.get('abonent_id'))}</b>\n\n"
        f"<b>{t(lang,'order_stats')}</b>\n"
        f"• {t(lang,'total_orders')}: <b>{order_count['total_orders']}</b>\n"
        f"• {t(lang,'connection_orders')}: <b>{order_count['connection_orders']}</b>\n"
        f"• {t(lang,'tech_connection_orders')}: <b>{order_count['technician_orders']}</b>\n"
        f"• {t(lang,'smartservice_orders')}: <b>{order_count['smartservice_orders']}</b>\n\n"
    )
    
    # Mijozning ariza tarixini olish va ko'rsatish
    history = await get_client_order_history(user["id"])
    
    if history:
        # Paginatsiya ma'lumotlarini saqlash
        await state.update_data(
            client_history=history,
            current_page=0,
            client_user_id=user["id"],
            client_user_info=user,
            client_order_count=order_count
        )
        await state.set_state(JMClientSearchStates.viewing_history)
        
        # Birinchi sahifani ko'rsatish
        await _show_history_page(message, history, 0, lang, user, order_count)
    else:
        text += f"<i>{t(lang,'no_history')}</i>"
        await message.answer(text, parse_mode="HTML")
        await state.clear()

# ===================== Paginatsiya handlers =====================
@router.callback_query(F.data.startswith("history_prev:"))
async def history_prev(callback: CallbackQuery, state: FSMContext):
    """Oldingi sahifaga o'tish"""
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = _norm_lang(u.get("language") if u else "uz")
    
    data = await state.get_data()
    history = data.get("client_history", [])
    user_info = data.get("client_user_info", {})
    order_count = data.get("client_order_count", {})
    current_page = int(callback.data.split(":")[1])
    
    if current_page > 0:
        new_page = current_page - 1
        await state.update_data(current_page=new_page)
        await callback.message.delete()
        await _show_history_page(callback.message, history, new_page, lang, user_info, order_count)
    
    await callback.answer()

@router.callback_query(F.data.startswith("history_next:"))
async def history_next(callback: CallbackQuery, state: FSMContext):
    """Keyingi sahifaga o'tish"""
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = _norm_lang(u.get("language") if u else "uz")
    
    data = await state.get_data()
    history = data.get("client_history", [])
    user_info = data.get("client_user_info", {})
    order_count = data.get("client_order_count", {})
    current_page = int(callback.data.split(":")[1])
    
    ITEMS_PER_PAGE = 5
    total_pages = (len(history) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    if current_page < total_pages - 1:
        new_page = current_page + 1
        await state.update_data(current_page=new_page)
        await callback.message.delete()
        await _show_history_page(callback.message, history, new_page, lang, user_info, order_count)
    
    await callback.answer()

@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    """Bo'sh callback"""
    await callback.answer()
