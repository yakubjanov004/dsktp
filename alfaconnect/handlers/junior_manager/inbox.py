from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
import html
import logging

from filters.role_filter import RoleFilter
from database.junior_manager.queries import (
    get_user_by_telegram_id,
    get_connections_by_recipient,
    get_connection_order_by_id,
    get_staff_order_by_id,
    move_order_to_controller,
    set_jm_notes,
)
from database.junior_manager.orders import update_jm_notes
from handlers.junior_manager.orders import _get_region_display_name
from keyboards.junior_manager_buttons import get_junior_manager_main_menu
from aiogram.fsm.state import StatesGroup, State

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(RoleFilter("junior_manager"))
router.callback_query.filter(RoleFilter("junior_manager"))

# =========================
# I18N helper
# =========================
def _norm_lang(v: str | None) -> str:
    v = (v or "ru").lower()
    return "ru" if v.startswith("ru") else "uz"

TR = {
    "user_not_found": {
        "uz": "❌ Foydalanuvchi topilmadi.",
        "ru": "❌ Пользователь не найден.",
    },
    "blocked": {
        "uz": "🚫 Profil bloklangan.",
        "ru": "🚫 Профиль заблокирован.",
    },
    "inbox_empty": {
        "uz": "📭 Inbox bo‘sh.",
        "ru": "📭 Входящие пусты.",
    },
    "contacted_choose": {
        "uz": "☎️ Mijoz bilan bog'lanildi.\nQuyidagidan birini tanlang:",
        "ru": "☎️ Связались с клиентом.\nВыберите действие:",
    },
    "enter_message_for_client": {
        "uz": "📝 Qo'shimcha ma'lumot kiriting (izoh qo'shing):",
        "ru": "📝 Введите дополнительную информацию (добавить комментарий):",
    },
    "message_sent_to_client": {
        "uz": "✅ Izoh qo'shildi va saqlandi.",
        "ru": "✅ Комментарий добавлен и сохранен.",
    },
    "error_occurred": {
        "uz": "❌ Xatolik yuz berdi.",
        "ru": "❌ Произошла ошибка.",
    },
    "nav_prev": {
        "uz": "⬅️ Oldingi",
        "ru": "⬅️ Предыдущий",
    },
    "nav_next": {
        "uz": "Keyingi ➡️",
        "ru": "Следующий ➡️",
    },
    "btn_add_comment": {
        "uz": "✍️ Izoh qo'shish",
        "ru": "✍️ Добавить комментарий",
    },
    "btn_send_to_controller": {
        "uz": "📤 Controller'ga yuborish",
        "ru": "📤 Отправить контроллеру",
    },
    "note_add": {
        "uz": "✍️ Qo‘shimcha ma'lumot kiritish",
        "ru": "✍️ Добавить доп. информацию",
    },
    "back": {
        "uz": "🔙 Orqaga",
        "ru": "🔙 Назад",
    },
    "card_title": {
        "uz": "🛠 <b>Ulanish arizasi — To‘liq ma'lumot</b>",
        "ru": "🛠 <b>Заявка на подключение — Полные данные</b>",
    },
    "card_id": {
        "uz": "🆔 <b>Ariza ID:</b>",
        "ru": "🆔 <b>ID:</b>",
    },
    "card_date": {
        "uz": "📅 <b>Sana:</b>",
        "ru": "📅 <b>Дата:</b>",
    },
    "card_client": {
        "uz": "👤 <b>Mijoz:</b>",
        "ru": "👤 <b>Клиент:</b>",
    },
    "card_phone": {
        "uz": "📞 <b>Telefon:</b>",
        "ru": "📞 <b>Телефон:</b>",
    },
    "card_region": {
        "uz": "🏙 <b>Hudud:</b>",
        "ru": "🏙 <b>Регион:</b>",
    },
    "card_address": {
        "uz": "📍 <b>Manzil:</b>",
        "ru": "📍 <b>Адрес:</b>",
    },
    "card_notes_title": {
        "uz": "📝 <b>Qo‘shimcha ma'lumotlar:</b>",
        "ru": "📝 <b>Доп. информация:</b>",
    },
    "card_pager": {
        "uz": "📄 <i>Ariza #{idx} / {total}</i>",
        "ru": "📄 <i>Заявка #{idx} / {total}</i>",
    },
    "send_ok": {
        "uz": "✅ Controller'ga yuborildi.",
        "ru": "✅ Отправлено контроллёру.",
    },
    "order_sent_title": {
        "uz": "📤 Ariza Controller'ga yuborildi",
        "ru": "📤 Заявка отправлена контроллёру",
    },
    "order_sent_id": {
        "uz": "🆔 Ariza ID:",
        "ru": "🆔 ID заявки:",
    },
    "order_sent_date": {
        "uz": "📅 Yuborilgan sana:",
        "ru": "📅 Дата отправки:",
    },
    "order_sent_comment": {
        "uz": "📝 Izoh:",
        "ru": "📝 Комментарий:",
    },
    "send_fail": {
        "uz": "❌ Yuborishning iloji yo‘q (status mos emas).",
        "ru": "❌ Не удалось отправить (некорректный статус).",
    },
    "note_prompt": {
        "uz": "✍️ Qo‘shimcha ma'lumot kiriting (matn yuboring).",
        "ru": "✍️ Отправьте текст доп. информации.",
    },
    "note_current": {
        "uz": "<b>Joriy matn:</b>",
        "ru": "<b>Текущий текст:</b>",
    },
    "note_too_short": {
        "uz": "Matn juda qisqa.",
        "ru": "Текст слишком короткий.",
    },
    "note_preview_title": {
        "uz": "📝 Kiritilgan matn:",
        "ru": "📝 Введённый текст:",
    },
    "note_confirm": {
        "uz": "✅ Tasdiqlash",
        "ru": "✅ Подтвердить",
    },
    "note_edit": {
        "uz": "✏️ Tahrirlash",
        "ru": "✏️ Редактировать",
    },
    "note_edit_prompt": {
        "uz": "✍️ Yangi matn yuboring.\n\n<b>Avvalgi:</b>",
        "ru": "✍️ Отправьте новый текст.\n\n<b>Предыдущий:</b>",
    },
    "error_generic": {
        "uz": "Xatolik.",
        "ru": "Ошибка.",
    },
    "note_save_fail": {
        "uz": "❌ Saqlash imkoni yo‘q (ehtimol, ariza sizga tegishli emas yoki status mos emas).",
        "ru": "❌ Не удалось сохранить (возможно, не ваша заявка или некорректный статус).",
    },
    "note_saved": {
        "uz": "✅ Saqlandi.",
        "ru": "✅ Сохранено.",
    },
    "client_id_label": {
        "uz": "Mijoz ID",
        "ru": "ID клиента",
    },
    "abonent_id_label": {
        "uz": "Abonent ID",
        "ru": "ID абонента",
    },
    "order_type_label": {
        "uz": "Ariza turi",
        "ru": "Тип заявки",
    },
    "business_type_label": {
        "uz": "Business turi",
        "ru": "Тип бизнеса",
    },
    "status_label": {
        "uz": "Holat",
        "ru": "Статус",
    },
    "description_label": {
        "uz": "Tavsif",
        "ru": "Описание",
    },
    "created_label": {
        "uz": "Yaratilgan",
        "ru": "Создано",
    },
    "updated_label": {
        "uz": "Yangilangan",
        "ru": "Обновлено",
    },
}

def _t(lang: str, key: str) -> str:
    lang = _norm_lang(lang)
    return TR.get(key, {}).get(lang, key)

# =========================
# States
# =========================
class JMNoteStates(StatesGroup):
    waiting_text = State()   # matn yuborilishini kutish
    confirming   = State()   # tasdiqlash/tahrirlash

class JMContactStates(StatesGroup):
    waiting_message = State()

# =========================
# Utilities
# =========================
def _esc(v) -> str:
    if v is None:
        return "—"
    return html.escape(str(v), quote=False)

def _fmt_dt(dt) -> str:
    if isinstance(dt, datetime):
        # Convert to UTC+5 timezone
        if dt.tzinfo is None:
            # If no timezone info, assume it's UTC and convert to UTC+5
            utc_plus_5 = timezone(timedelta(hours=5))
            dt = dt.replace(tzinfo=timezone.utc).astimezone(utc_plus_5)
        else:
            # If timezone info exists, convert to UTC+5
            utc_plus_5 = timezone(timedelta(hours=5))
            dt = dt.astimezone(utc_plus_5)
        
        return dt.strftime("%d.%m.%Y %H:%M")
    return (str(dt)[:16]) if dt else "—"

# =========================
# Entry: 📥 Inbox (tugma o'zgarmaydi)
# =========================
@router.message(F.text == "📥 Inbox")
async def handle_inbox(msg: Message, state: FSMContext):
    user = await get_user_by_telegram_id(msg.from_user.id)
    if not user:
        # til ma'lum bo'lmagani uchun RU default
        return await msg.answer(_t("ru", "user_not_found"))
    lang = _norm_lang(user.get("language"))

    if user.get("is_blocked"):
        return await msg.answer(_t(lang, "blocked"))

    items = await get_connections_by_recipient(recipient_id=user["id"], limit=50)
    if not items:
        return await msg.answer(_t(lang, "inbox_empty"), reply_markup=get_junior_manager_main_menu(lang))

    await state.update_data(items=items, idx=0, lang=lang)
    await _render_card(target=msg, items=items, idx=0, lang=lang)

# =========================
# Card renderer
# =========================
async def _render_card(target: Message | CallbackQuery, items: List[Dict[str, Any]], idx: int, lang: str):
    total = len(items)
    
    # Bounds checking to prevent IndexError
    if not items or idx < 0 or idx >= total:
        if isinstance(target, Message):
            return await target.answer(_t(lang, "inbox_empty"), reply_markup=get_junior_manager_main_menu(lang))
        else:
            return await target.message.edit_text(_t(lang, "inbox_empty"), reply_markup=get_junior_manager_main_menu(lang))
    
    it = items[idx]

    # Determine which order type we're dealing with
    is_connection_order = it.get("order_id") is not None
    is_staff_order = it.get("staff_order_id") is not None
    
    # Get the appropriate order ID for buttons
    order_id = it.get("order_id") or it.get("staff_order_id")
    
    # Get application number for display
    application_number = it.get("application_number") or it.get("staff_application_number")
    
    # Get creation date
    order_created = _fmt_dt(it.get("created_at"))
    
    # Get client information - ensure we always show name from DB
    if is_staff_order:
        # Prefer explicit client fields from query, then fallback
        client_name_raw = (
            it.get("client_name")
            or it.get("staff_client_full_name")
            or (_t(lang, "client_id_label") + f": {it.get('staff_abonent_id')}")
        )
        client_phone_raw = it.get("client_phone_number") or it.get("staff_client_phone") or it.get("staff_phone") or it.get("phone")
    else:
        # For connection orders, prefer joined user fields
        client_name_raw = it.get("client_full_name") or it.get("user_name")
        client_phone_raw = it.get("client_phone")
    
    # Get location information - handle staff vs connection orders
    if is_staff_order:
        region_raw = it.get("staff_region")
        address_raw = it.get("staff_address")
    else:
        region_raw = it.get("order_region")
        address_raw = it.get("order_address")
    
    # Get notes - check both connection and staff orders
    jm_notes_raw = it.get("order_jm_notes") or it.get("jm_notes")
    
    # Get tariff information
    tariff_name = it.get("tariff_name")
    
    # Get order type and service type
    order_type = it.get("order_type", "connection")
    service_type = it.get("type_of_zayavka", "connection")
    
    # Determine if this is a technician order
    is_technician_order = service_type.lower() == "technician" or order_type.lower() == "technician"

    # Escape all values
    order_id_txt = _esc(application_number) if application_number else _esc(order_id)
    client_name = _esc(client_name_raw)
    client_phone = _esc(client_phone_raw)
    region = _get_region_display_name(region_raw, lang)
    address = _esc(address_raw)
    
    # For technician orders, show problem description instead of tariff
    if is_technician_order:
        description= it.get("description", "-")
        tariff_or_problem = _esc(description) if description else "-"
        tariff_label = "🔧 <b>Muammo:</b>" if lang == "uz" else "🔧 <b>Проблема:</b>"
    else:
        tariff_or_problem = _esc(tariff_name) if tariff_name else "-"
        tariff_label = "💳 <b>Tarif:</b>" if lang == "uz" else "💳 <b>Тариф:</b>"

    # Build notes block
    notes_block = ""
    if jm_notes_raw:
        notes_block = f"\n\n{_t(lang,'card_notes_title')}\n" + _esc(jm_notes_raw)

    # Determine card title based on order type
    if order_type == "technician":
        card_title = f"🔧 <b>Texnik xizmat arizasi — To'liq ma'lumot</b>" if lang == "uz" else f"🔧 <b>Заявка на техническое обслуживание — Полные данные</b>"
    else:
        card_title = _t(lang, 'card_title')

    text = (
        f"{card_title}\n\n"
        f"{_t(lang,'card_id')} {order_id_txt}\n"
        f"{_t(lang,'card_date')} {order_created}\n"
        f"{_t(lang,'card_client')} {client_name}\n"
        f"{_t(lang,'card_phone')} {client_phone}\n"
        f"{_t(lang,'card_region')} {region}\n"
        f"{_t(lang,'card_address')} {address}\n"
        f"🆔 <b>{_t(lang,'abonent_id_label')}:</b> {order_id_txt}\n"
        f"📋 <b>{_t(lang,'order_type_label')}:</b> {service_type}\n"
        f"🏢 <b>{_t(lang,'business_type_label')}:</b> B2C\n"
        f"🕒 <b>{_t(lang,'created_label')}:</b> {order_created}\n"
        f"{tariff_label} {tariff_or_problem}\n"
        f"{notes_block}\n\n"
        f"{_t(lang,'card_pager').format(idx=idx+1, total=total)}"
    )

    kb = _kb(idx, total, conn_id=order_id, lang=lang)
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# =========================
# Inline keyboards
# =========================
def _kb_contact(lang: str, conn_id: int) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(
            text=_t(lang, "note_add"),
            callback_data=f"jm_note_start:{conn_id}"
        ),
        InlineKeyboardButton(
            text=_t(lang, "back"),
            callback_data="jm_note_back"
        ),
    ]]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _kb(idx: int, total: int, conn_id: int | None, lang: str) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []

    if total > 1:
        nav: List[InlineKeyboardButton] = []
        if idx > 0:
            nav.append(InlineKeyboardButton(text=_t(lang, "nav_prev"), callback_data="jm_conn_prev"))
        if idx < total - 1:
            nav.append(InlineKeyboardButton(text=_t(lang, "nav_next"), callback_data="jm_conn_next"))
        if nav:
            rows.append(nav)

    rows.append([
        InlineKeyboardButton(text=_t(lang, "btn_add_comment"), callback_data=f"jm_add_comment:{conn_id}"),
        InlineKeyboardButton(text=_t(lang, "btn_send_to_controller"), callback_data=f"jm_send_to_controller:{conn_id}"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)

# =========================
# Navigation
# =========================
@router.callback_query(F.data == "jm_conn_prev")
async def jm_conn_prev(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    items = data.get("items", [])
    lang  = data.get("lang", "uz")
    idx   = max(0, (data.get("idx") or 0) - 1)
    await state.update_data(idx=idx)
    await _render_card(target=cb, items=items, idx=idx, lang=lang)

@router.callback_query(F.data == "jm_conn_next")
async def jm_conn_next(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    items = data.get("items", [])
    lang  = data.get("lang", "uz")
    idx   = data.get("idx") or 0
    if idx < len(items) - 1:
        idx += 1
    await state.update_data(idx=idx)
    await _render_card(target=cb, items=items, idx=idx, lang=lang)

# =========================
# Contact client (submenu)
# =========================
@router.callback_query(F.data.startswith("jm_add_comment:"))
async def jm_add_comment(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    order_id = int(cb.data.split(":")[1])
    
    # Get user language
    jm_user = await get_user_by_telegram_id(cb.from_user.id)
    if not jm_user:
        return await cb.answer(_t("ru", "user_not_found"), show_alert=True)
    lang = _norm_lang(jm_user.get("language"))
    
    # Set state and ask for message
    await state.set_state(JMContactStates.waiting_message)
    await state.update_data(contact_order_id=order_id)
    
    # Remove inline keyboard and ask for message
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(_t(lang, "enter_message_for_client"))

@router.message(JMContactStates.waiting_message)
async def jm_contact_message_handler(msg: Message, state: FSMContext):
    """Handle the comment added by junior manager"""
    data = await state.get_data()
    order_id = data.get("contact_order_id")
    lang = data.get("lang", "uz")
    
    if not order_id:
        await state.clear()
        return await msg.answer(_t(lang, "error_occurred"))
    
    # Get the message text
    message_text = msg.text or ""
    
    # Determine order type from current items (reliable by presence of IDs)
    items = data.get("items", [])
    idx = data.get("idx", 0)
    
    if not items or idx >= len(items):
        await state.clear()
        return await msg.answer(_t(lang, "error_occurred"))
    
    current_item = items[idx]
    if current_item.get("order_id") is not None:
        order_type = "connection"
    elif current_item.get("staff_order_id") is not None:
        order_type = "staff"
    else:
        # Fallback: if explicit keys missing, default to connection for safety
        order_type = "connection"
    
    # Save the note to database
    success = await update_jm_notes(order_id, message_text, order_type)
    
    if not success:
        await msg.answer(_t(lang, "error_occurred"))
        return
    
    # Update the current item with the new note
    items[idx]["jm_notes"] = message_text
    items[idx]["order_jm_notes"] = message_text
    items[idx]["staff_jm_notes"] = message_text
    
    await msg.answer(_t(lang, "message_sent_to_client"))
    
    await state.update_data(items=items, idx=idx, lang=lang)
    await state.set_state(None)  # Clear the contact state
    
    # Show the inbox again to continue browsing
    await _render_card(target=msg, items=items, idx=idx, lang=lang)

# =========================
# Send to controller
# =========================
@router.callback_query(F.data.startswith("jm_send_to_controller:"))
async def jm_send_to_controller(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    order_id = int(cb.data.split(":")[1])  # = connection_id (order_id)

    # JM foydalanuvchi ID sini olamiz
    jm_user = await get_user_by_telegram_id(cb.from_user.id)
    if not jm_user:
        return await cb.answer(_t("ru", "user_not_found"), show_alert=True)
    lang = _norm_lang(jm_user.get("language"))

    try:
        # Database funksiyasini chaqiramiz - endi notification info qaytaradi
        result = await move_order_to_controller(order_id=order_id, jm_id=jm_user["id"])
        
        if not result:
            return await cb.answer(_t(lang, "send_fail"), show_alert=True)
        
        # Controller'ga notification yuborish - markaziy helper orqali (istisnolar bilan)
        try:
            from loader import bot
            from utils.notification_service import send_cross_role_notification

            await send_cross_role_notification(
                bot,
                sender_role=result.get("sender_role", "junior_manager"),
                recipient_role=result.get("recipient_role", "controller"),
                sender_id=result.get("sender_id"),
                recipient_id=result.get("recipient_id"),
                creator_id=result.get("creator_id"),
                recipient_telegram_id=result.get("telegram_id"),
                application_number=result.get("application_number") or f"ID:{order_id}",
                order_type=result.get("order_type", "connection"),
                current_load=result.get("current_load", 0),
                lang=result.get("language") or "uz",
            )
        except Exception as notif_error:
            logger.error(f"Failed to send notification: {notif_error}")
            # Notification xatosi asosiy jarayonga ta'sir qilmaydi
        
    except Exception as e:
        logger.error(f"Error in jm_send_to_controller: {e}")
        return await cb.answer(_t(lang, "send_fail"), show_alert=True)

    data  = await state.get_data()
    items = data.get("items", [])
    idx   = data.get("idx", 0)
    
    # Get current order information before removing it
    current_order = None
    if items and 0 <= idx < len(items):
        current_order = items[idx]
    
    # Get order information for display
    order_info = ""
    if current_order:
        app_number = current_order.get("application_number") or current_order.get("staff_application_number")
        jm_notes = current_order.get("jm_notes") or current_order.get("order_jm_notes")
        
        order_info = (
            f"\n{_t(lang, 'order_sent_title')}\n"
            f"{_t(lang, 'order_sent_id')} {app_number or order_id}\n"
            f"{_t(lang, 'order_sent_date')} {_fmt_dt(datetime.now())}\n"
        )
        
        if jm_notes:
            order_info += f"\n{_t(lang, 'order_sent_comment')}\n{_esc(jm_notes)}\n"

    # Remove the sent order from the list
    items = [x for x in items if (x.get("order_id") != order_id and x.get("staff_order_id") != order_id and x.get("connection_id") != order_id and x.get("staff_id") != order_id)]

    if not items:
        await state.clear()
        await cb.message.edit_reply_markup(reply_markup=None)
        return  # xabar chiqarilmaydi, pastda faqat bitta marta chiqadi

    if idx >= len(items):
        idx = len(items) - 1

    await state.update_data(items=items, idx=idx, lang=lang)
    # Remove inline keyboard and show success message with order info
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(f"{_t(lang, 'send_ok')}{order_info}", parse_mode="HTML")
    
    # Show the next item in inbox as new message
    # Render the card directly with answer (not edit)
    order = items[idx]
    order_id = order.get("order_id") or order.get("staff_order_id")
    
    # Use _render_card by creating a Message-like object
    # We'll manually call answer method
    kb = _kb(idx, len(items), conn_id=order_id, lang=lang)
    
    # Get all the data we need for rendering
    application_number = order.get("application_number") or order.get("staff_application_number")
    order_created = _fmt_dt(order.get("created_at"))
    
    # Get client information
    if order.get("staff_order_id"):
        client_name_raw = (order.get("client_name") or order.get("staff_client_full_name"))
        client_phone_raw = order.get("client_phone_number") or order.get("staff_client_phone") or order.get("staff_phone") or order.get("phone")
    else:
        client_name_raw = order.get("client_full_name") or order.get("user_name")
        client_phone_raw = order.get("client_phone")
    
    # Get location information
    if order.get("staff_order_id"):
        region_raw = order.get("staff_region")
        address_raw = order.get("staff_address")
    else:
        region_raw = order.get("order_region")
        address_raw = order.get("order_address")
    
    # Get notes - check both connection and staff orders
    jm_notes_raw = order.get("order_jm_notes") or order.get("jm_notes")
    
    # Get tariff
    tariff_name = order.get("tariff_name")
    
    # Escape values
    order_id_txt = _esc(application_number) if application_number else _esc(order_id)
    client_name = _esc(client_name_raw)
    client_phone = _esc(client_phone_raw)
    region = _get_region_display_name(region_raw, lang)
    address = _esc(address_raw)
    
    # Build notes block
    notes_block = ""
    if jm_notes_raw:
        notes_block = f"\n\n{_t(lang,'card_notes_title')}\n" + _esc(jm_notes_raw)
    
    # Build text
    text = (
        f"{_t(lang, 'card_title')}\n\n"
        f"{_t(lang,'card_id')} {order_id_txt}\n"
        f"{_t(lang,'card_date')} {order_created}\n"
        f"{_t(lang,'card_client')} {client_name}\n"
        f"{_t(lang,'card_phone')} {client_phone}\n"
        f"{_t(lang,'card_region')} {region}\n"
        f"{_t(lang,'card_address')} {address}\n"
        f"🆔 <b>{_t(lang,'abonent_id_label')}:</b> {order_id_txt}\n"
        f"📋 <b>{_t(lang,'order_type_label')}:</b> connection\n"
        f"🏢 <b>{_t(lang,'business_type_label')}:</b> B2C\n"
        f"🕒 <b>{_t(lang,'created_label')}:</b> {order_created}\n"
        f"💳 <b>Tarif:</b> {_esc(tariff_name) if tariff_name else '-'}\n"
        f"{notes_block}\n\n"
        f"{_t(lang,'card_pager').format(idx=idx+1, total=len(items))}"
    )
    
    # Send as new message
    await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")

# =========================
# Notes flow
# =========================
@router.callback_query(F.data.startswith("jm_note_start:"))
async def jm_note_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    lang = data.get("lang", "uz")
    order_id = int(cb.data.split(":")[1])

    # oldingi matn bo'lsa ko'rsatamiz (state yoki items'dan)
    pending = data.get("pending_note")
    if not pending:
        items = data.get("items", [])
        idx   = data.get("idx", 0)
        if 0 <= idx < len(items):
            current_item = items[idx]
            # Check if this is the right order (handle both connection_id and staff_id)
            if (current_item.get("connection_id") == order_id or current_item.get("staff_id") == order_id):
                pending = current_item.get("order_jm_notes") or current_item.get("jm_notes")

    await state.update_data(note_order_id=order_id, pending_note=(pending or ""))

    prompt = _t(lang, "note_prompt")
    if pending:
        prompt += "\n\n" + _t(lang, "note_current") + "\n" + html.escape(pending)
    await cb.message.answer(prompt, parse_mode="HTML")
    await state.set_state(JMNoteStates.waiting_text)

@router.message(JMNoteStates.waiting_text)
async def jm_note_got_text(msg: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    note = (msg.text or "").strip()
    if len(note) < 3:
        return await msg.answer(_t(lang, "note_too_short"))

    await state.update_data(pending_note=note)
    preview = _t(lang, "note_preview_title") + "\n" + html.escape(note)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=_t(lang, "note_confirm"), callback_data="jm_note_confirm"),
        InlineKeyboardButton(text=_t(lang, "note_edit"),    callback_data="jm_note_edit_again"),
    ]])
    await msg.answer(preview, parse_mode="HTML", reply_markup=kb)
    await state.set_state(JMNoteStates.confirming)

@router.callback_query(JMNoteStates.confirming, F.data == "jm_note_edit_again")
async def jm_note_edit_again(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    lang = data.get("lang", "uz")
    current = data.get("pending_note") or ""
    prompt = _t(lang, "note_edit_prompt") + "\n" + html.escape(current)
    await cb.message.answer(prompt, parse_mode="HTML")
    await state.set_state(JMNoteStates.waiting_text)

@router.callback_query(JMNoteStates.confirming, F.data == "jm_note_confirm")
async def jm_note_confirm(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data  = await state.get_data()
    lang  = data.get("lang", "uz")
    note  = (data.get("pending_note") or "").strip()
    order_id = int(data.get("note_order_id") or 0)

    if not note or not order_id:
        return await cb.answer(_t(lang, "error_generic"), show_alert=True)

    # JM foydalanuvchini tekshiramiz
    jm_user = await get_user_by_telegram_id(cb.from_user.id)
    if not jm_user:
        return await cb.answer(_t("ru", "user_not_found"), show_alert=True)

    ok = await set_jm_notes(order_id=order_id, notes=note)
    if not ok:
        return await cb.answer(_t(lang, "note_save_fail"), show_alert=True)

    # Lokal ro'yxatni ham yangilab qo'yamiz (kartochka qayta chizilganda ko'rinsin)
    items = data.get("items", [])
    idx   = data.get("idx", 0)
    if 0 <= idx < len(items):
        current_item = items[idx]
        # Check if this is the right order (handle both connection_id and staff_id)
        if (current_item.get("connection_id") == order_id or current_item.get("staff_id") == order_id):
            items[idx]["jm_notes"] = note
            items[idx]["order_jm_notes"] = note
            await state.update_data(items=items)

    await cb.message.answer(_t(lang, "note_saved"))
    # Viewing holatini qayta tiklaymiz (state ni to'liq tozalamasdan)
    await state.update_data(items=items, idx=idx, lang=lang)
    await _render_card(target=cb, items=items, idx=idx, lang=lang)

@router.callback_query(F.data == "jm_note_back")
async def jm_note_back(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    items = data.get("items", [])
    idx   = data.get("idx", 0)
    lang  = data.get("lang", "uz")
    if not items:
        return await cb.message.answer(_t(lang, "inbox_empty"))
    await _render_card(target=cb, items=items, idx=idx, lang=lang)
