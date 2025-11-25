# handlers/call_center/inbox.py
from typing import Dict, Any, List, Optional
import html
from datetime import datetime
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.exceptions import TelegramBadRequest
from filters.role_filter import RoleFilter

from database.call_center.inbox import (
    get_operator_orders,
    get_operator_orders_count,
    update_order_status,
    add_operator_comment,
    get_order_by_id,
    get_user_id_by_telegram_id,
    get_user_by_telegram_id,
    get_any_controller_id,
    log_connection_from_operator,
    log_connection_completed_from_operator,
)

logger = logging.getLogger(__name__)

# === Router ===
router = Router()
router.message.filter(RoleFilter("callcenter_operator"))
router.callback_query.filter(RoleFilter("callcenter_operator"))

# === States ===
class InboxStates:
    browsing = "inbox_browsing"
    adding_comment = "inbox_comment"

# =========================================================
# HELPER FUNCTIONS
# =========================================================

def esc(text: str) -> str:
    """Escape HTML characters"""
    if text is None:
        return "-"
    return html.escape(str(text))

def fmt_dt(dt) -> str:
    """Format datetime for display"""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return esc(dt)
    if isinstance(dt, datetime):
        return dt.strftime("%d.%m.%Y %H:%M")
    return "-"

def region_title_from_id(rid) -> str:
    """Region ID dan region nomini olish"""
    REGION_TITLES = {
        1: "Toshkent shahri", 2: "Toshkent viloyati", 3: "Andijon", 4: "Farg'ona",
        5: "Namangan", 6: "Sirdaryo", 7: "Jizzax", 8: "Samarqand", 9: "Buxoro",
        10: "Navoiy", 11: "Qashqadaryo", 12: "Surxondaryo", 13: "Xorazm", 14: "Qoraqalpog'iston"
    }
    
    # String region kodlarini ID'ga aylantirish
    REGION_CODE_TO_ID = {
        "toshkent_city": 1, "toshkent_region": 2, "andijon": 3, "fergana": 4, "namangan": 5,
        "sirdaryo": 6, "jizzax": 7, "samarkand": 8, "bukhara": 9, "navoi": 10,
        "kashkadarya": 11, "surkhandarya": 12, "khorezm": 13, "karakalpakstan": 14,
    }
    
    if rid is None:
        return "-"
    
    # Agar string bo'lsa, uni ID'ga aylantirish
    if isinstance(rid, str):
        region_id = REGION_CODE_TO_ID.get(rid.lower())
        if region_id is None:
            return rid  # Agar topilmasa, asl qiymatni qaytarish
        return REGION_TITLES.get(region_id, rid)
    
    # Integer ID'ni tekshirish
    try:
        region_id = int(rid)
        return REGION_TITLES.get(region_id, str(rid))
    except (ValueError, TypeError):
        return str(rid)

# =========================================================
# ORDER TEXT FORMATTING
# =========================================================

def get_order_text(order: dict, lang: str = "uz", idx: int | None = None, total: int | None = None) -> str:
    """Ariza matnini formatlash - to'liq ma'lumotlar bilan application_number"""
    comments = esc(order.get("comments") or order.get("description_operator") or "")
    client_name = esc(order.get("client_name") or "-")
    client_phone = esc(order.get("client_phone") or "-")
    abonent_id = esc(order.get("abonent_id") or "-")
    region_text = region_title_from_id(order.get("region"))
    address = esc(order.get("address") or "-")
    description = esc(order.get("description") or "-")
    application_number = esc(order.get("application_number") or f"#{order.get('id', 'N/A')}")
    media_text = "📷 <b>Rasm:</b> Mavjud" if order.get("media") else ""
    
    if lang == "uz":
        base = (
            f"🆔 <b>Ariza raqami:</b> {application_number}\n"
            f"👤 <b>Mijoz:</b> {client_name}\n"
            f"📞 <b>Telefon:</b> {client_phone}\n"
            f"🆔 <b>Abonent ID:</b> {abonent_id}\n"
            f"📍 <b>Region:</b> {region_text}\n"
            f"🏠 <b>Manzil:</b> {address}\n"
            f"📝 <b>Tavsif:</b> {description}"
        )
        if media_text:
            base += f"\n{media_text}"
        if comments:
            base += f"\n💬 <b>Izohlar:</b> {comments}"
    else:
        base = (
            f"🆔 <b>Номер заявки:</b> {application_number}\n"
            f"👤 <b>Клиент:</b> {client_name}\n"
            f"📞 <b>Телефон:</b> {client_phone}\n"
            f"🆔 <b>ID абонента:</b> {abonent_id}\n"
            f"📍 <b>Регион:</b> {region_text}\n"
            f"🏠 <b>Адрес:</b> {address}\n"
            f"📝 <b>Описание:</b> {description}"
        )
        if media_text:
            base += f"\n📷 <b>Фото:</b> Есть"
        if comments:
            base += f"\n💬 <b>Комментарии:</b> {comments}"

    if idx is not None and total is not None:
        base += (
            f"\n\n🗂️ <i>Ariza {idx + 1} / {total}</i>"
            if lang == "uz"
            else f"\n\n🗂️ <i>Заявка {idx + 1} / {total}</i>"
        )
    
    base += f"\n📅 <b>Sana:</b> {fmt_dt(order.get('created_at'))}"
    
    return base

# =========================================================
# KEYBOARD FUNCTIONS
# =========================================================

def get_inbox_controls(order_id: int, lang: str = "uz", idx: int = 0, total: int = 1) -> InlineKeyboardMarkup:
    """Inbox control tugmalari"""
    buttons: List[List[InlineKeyboardButton]] = []

    # ⬅️/➡️ navigatsiya
    nav_row: List[InlineKeyboardButton] = []
    if total > 1:
        if idx > 0:
            nav_row.append(InlineKeyboardButton(
                text="⬅️ Oldingisi" if lang == "uz" else "⬅️ Предыдущая",
                callback_data=f"inbox_prev:{order_id}"
            ))
        if idx < total - 1:
            nav_row.append(InlineKeyboardButton(
                text="➡️ Keyingisi" if lang == "uz" else "➡️ Следующая",
                callback_data=f"inbox_next:{order_id}"
            ))
    if nav_row:
        buttons.append(nav_row)

    # ✍️ Izoh
    buttons.append([InlineKeyboardButton(
        text="✍️ Izoh qo'shish" if lang == "uz" else "✍️ Добавить комментарий",
        callback_data=f"inbox_comment:{order_id}"
    )])

    # 📤 Controllerga yuborish
    buttons.append([InlineKeyboardButton(
        text="📤 Controllerga yuborish" if lang == "uz" else "📤 Отправить контроллеру",
        callback_data=f"inbox_send_control:{order_id}"
    )])

    # ✅ Arizani yopish
    buttons.append([InlineKeyboardButton(
        text="✅ Arizani yopish" if lang == "uz" else "✅ Закрыть заявку",
        callback_data=f"inbox_close:{order_id}"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# =========================================================
# MAIN HANDLERS
# =========================================================

@router.message(F.text.in_(["📥 Inbox", "📥 Входящие"]))
async def inbox_start(message: Message, state: FSMContext):
    """CC inbox boshlash"""
    operator_id = message.from_user.id
    lang = "uz" if message.text == "📥 Inbox" else "ru"

    orders = await get_operator_orders(operator_id)

    if not orders:
        await message.answer("📭 Arizalar yo'q" if lang == "uz" else "📭 Заявок нет")
        return

    await state.update_data(orders=orders, index=0, lang=lang)
    order = orders[0]
    text = get_order_text(order, lang, idx=0, total=len(orders))
    await message.answer(
        text,
        reply_markup=get_inbox_controls(order["id"], lang, idx=0, total=len(orders)),
        parse_mode="HTML",
    )
    await state.set_state(InboxStates.browsing)

# =========================================================
# NAVIGATION HANDLERS
# =========================================================

@router.callback_query(F.data.startswith("inbox_prev"))
async def inbox_prev(cq: CallbackQuery, state: FSMContext):
    """Oldingi arizaga o'tish"""
    data = await state.get_data()
    orders: List[Dict[str, Any]] = data["orders"]
    index: int = data["index"]
    lang: str = data.get("lang", "uz")

    if index > 0:
        index -= 1
        await state.update_data(index=index)

    index = max(0, min(index, len(orders) - 1))
    order = orders[index]
    text = get_order_text(order, lang, idx=index, total=len(orders))
    
    try:
        await cq.message.edit_text(
            text,
            reply_markup=get_inbox_controls(order["id"], lang, idx=index, total=len(orders)),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        pass  # Message not changed
    await cq.answer()

@router.callback_query(F.data.startswith("inbox_next"))
async def inbox_next(cq: CallbackQuery, state: FSMContext):
    """Keyingi arizaga o'tish"""
    data = await state.get_data()
    orders: List[Dict[str, Any]] = data["orders"]
    index: int = data["index"]
    lang: str = data.get("lang", "uz")

    if index < len(orders) - 1:
        index += 1
        await state.update_data(index=index)

    index = max(0, min(index, len(orders) - 1))
    order = orders[index]
    text = get_order_text(order, lang, idx=index, total=len(orders))
    
    try:
        await cq.message.edit_text(
            text,
            reply_markup=get_inbox_controls(order["id"], lang, idx=index, total=len(orders)),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        pass  # Message not changed
    await cq.answer()

# =========================================================
# COMMENT HANDLERS
# =========================================================

@router.callback_query(F.data.startswith("inbox_comment"))
async def inbox_comment(cq: CallbackQuery, state: FSMContext):
    """Izoh qo'shish boshlash"""
    order_id = int(cq.data.split(":")[1])
    lang = (await state.get_data()).get("lang", "uz")

    await state.update_data(comment_order_id=order_id)
    await cq.message.answer(
        "✍️ Izohni yuboring:" if lang == "uz" else "✍️ Отправьте комментарий:"
    )
    await state.set_state(InboxStates.adding_comment)
    await cq.answer()

@router.message(StateFilter(InboxStates.adding_comment))
async def inbox_comment_text(message: Message, state: FSMContext):
    """Izoh matnini qabul qilish"""
    data = await state.get_data()
    order_id = data["comment_order_id"]
    lang = data.get("lang", "uz")

    text_comment = (message.text or "").strip()
    success = await add_operator_comment(order_id, text_comment)

    if success:
        # Lokal ro'yxatni yangilash
        orders, index = data["orders"], data["index"]
        for o in orders:
            if o["id"] == order_id:
                o["comments"] = text_comment
                o["description_operator"] = text_comment
                break
        await state.update_data(orders=orders)

        order = orders[index]
        text = get_order_text(order, lang, idx=index, total=len(orders))
        await message.answer("✅ Izoh qo'shildi" if lang == "uz" else "✅ Комментарий добавлен")
        await message.answer(
            text,
            reply_markup=get_inbox_controls(order_id, lang, idx=index, total=len(orders)),
            parse_mode="HTML",
        )
    else:
        await message.answer("❌ Izoh qo'shishda xatolik" if lang == "uz" else "❌ Ошибка добавления комментария")
    
    await state.set_state(InboxStates.browsing)

# =========================================================
# ACTION HANDLERS
# =========================================================

@router.callback_query(F.data.startswith("inbox_send_control"))
async def inbox_send_control(cq: CallbackQuery, state: FSMContext):
    """Arizani controllerga yuborish"""
    order_id = int(cq.data.split(":")[1])
    data = await state.get_data()
    lang: str = data.get("lang", "uz")
    orders = data.get("orders", [])
    index = data.get("index", 0)

    # Operatorning DB-dagi ID sini topamiz
    operator_db_id = await get_user_id_by_telegram_id(cq.from_user.id)
    if not operator_db_id:
        await cq.answer(
            "❌ Operator profili topilmadi (users.id). Avval tizimga ro'yxatdan o'tkazing."
            if lang == "uz" else
            "❌ Профиль оператора не найден (users.id). Сначала зарегистрируйте в системе.",
            show_alert=True,
        )
        return

    # Controller topamiz
    controller_id = await get_any_controller_id()
    if not controller_id:
        await cq.answer(
            "❌ Controller topilmadi. Admin bilan bog'laning."
            if lang == "uz" else
            "❌ Не найден контроллер. Свяжитесь с админом.",
            show_alert=True,
        )
        return

    # Connection log yozamiz
    try:
        await log_connection_from_operator(
            sender_id=operator_db_id,
            recipient_id=controller_id,
            technician_order_id=order_id,
        )
    except Exception as e:
        await cq.answer(
            ("❌ Aloqa yozishda xatolik: " + str(e)) if lang == "uz"
            else ("❌ Ошибка записи соединения: " + str(e)),
            show_alert=True,
        )
        return

    # Statusni controllerga o'tkazamiz
    success = await update_order_status(order_id, status="in_controller")
    if not success:
        await cq.answer(
            "❌ Status yangilashda xatolik" if lang == "uz" else "❌ Ошибка обновления статуса",
            show_alert=True,
        )
        return

    # Controller'ga notification yuboramiz
    try:
        from loader import bot
        from utils.notification_service import send_role_notification
        
        # Controller'ning telegram_id ni olamiz
        controller_user = await get_user_by_telegram_id(controller_id)
        if controller_user and controller_user.get('telegram_id'):
            # Order ma'lumotlarini olamiz - application_number uchun
            order_info = await get_order_by_id(order_id)
            app_number = order_info.get('application_number') if order_info else f"#{order_id}"
            
            # Notification yuborish
            await send_role_notification(
                bot=bot,
                recipient_telegram_id=controller_user['telegram_id'],
                order_id=app_number,
                order_type="technician",
                current_load=1,  # Controller'ning hozirgi yuklamasi
                lang=controller_user.get('language', 'uz')
            )
            logger.info(f"Notification sent to controller {controller_id} for technician order {order_id} (app_number: {app_number})")
    except Exception as notif_error:
        logger.error(f"Failed to send notification to controller: {notif_error}")
        # Notification xatosi asosiy jarayonga ta'sir qilmaydi

    # Ro'yxatdan chiqarish va navbatdagi arizani ko'rsatish
    orders = [o for o in orders if o["id"] != order_id]
    if not orders:
        await cq.message.edit_text("📭 Boshqa ariza yo'q" if lang == "uz" else "📭 Заявок больше нет")
        await state.clear()
        await cq.answer()
        return

    new_index = min(index, len(orders) - 1)
    await state.update_data(orders=orders, index=new_index)
    new_order = orders[new_index]
    text = get_order_text(new_order, lang, idx=new_index, total=len(orders))
    
    try:
        await cq.message.edit_text(
            text,
            reply_markup=get_inbox_controls(new_order["id"], lang, idx=new_index, total=len(orders)),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        pass
    
    await cq.answer("📤 Controllerga yuborildi" if lang == "uz" else "📤 Отправлено контроллеру", show_alert=True)

@router.callback_query(F.data.startswith("inbox_close:"))
async def inbox_close(cq: CallbackQuery, state: FSMContext):
    """Arizani yopish - faqat note qo'shganidan so'ng yopiladi"""
    order_id = int(cq.data.split(":")[1])
    data = await state.get_data()
    lang: str = data.get("lang", "uz")
    orders = data.get("orders", [])
    index = data.get("index", 0)

    # Operator users.id
    operator_db_id = await get_user_id_by_telegram_id(cq.from_user.id)
    if not operator_db_id:
        await cq.answer(
            "❌ Operator profili topilmadi (users.id)." if lang == "uz"
            else "❌ Профиль оператора не найден (users.id).",
            show_alert=True,
        )
        return

    # Controller users.id
    controller_id = await get_any_controller_id()
    if not controller_id:
        await cq.answer(
            "❌ Controller topilmadi." if lang == "uz" else "❌ Контроллер не найден.",
            show_alert=True,
        )
        return

    # Note (description_operator) mavjudligini tekshiramiz - yopish uchun note kerak
    order = await get_order_by_id(order_id)
    if not order:
        await cq.answer(
            "❌ Ariza topilmadi." if lang == "uz" else "❌ Заявка не найдена.",
            show_alert=True,
        )
        return
    
    description_operator = order.get("description_operator") or order.get("comments") or ""
    if not description_operator or not description_operator.strip():
        await cq.answer(
            "⚠️ Ariza yopish uchun avval izoh (note) qo'shishingiz kerak!\n\n✍️ Izoh qo'shish tugmasini bosing."
            if lang == "uz" else
            "⚠️ Для закрытия заявки сначала необходимо добавить комментарий (note)!\n\n✍️ Нажмите кнопку Добавить комментарий.",
            show_alert=True,
        )
        return

    # technician_orders ni 'completed' qilamiz
    success = await update_order_status(order_id, status="completed")
    if not success:
        await cq.answer(
            "❌ Arizani yopishda xatolik" if lang == "uz"
            else "❌ Ошибка закрытия заявки",
            show_alert=True,
        )
        return

    # connections ga 'completed' log yozamiz
    try:
        await log_connection_completed_from_operator(
            sender_id=operator_db_id,
            recipient_id=controller_id,
            technician_order_id=order_id,
        )
    except Exception as e:
        await cq.answer(
            ("⚠️ Yopildi, lekin log yozilmadi: " + str(e)) if lang == "uz"
            else ("⚠️ Закрыто, но лог не записан: " + str(e)),
            show_alert=True,
        )

    # Clientga completion notification yuborish (rating bilan)
    try:
        from utils.completion_notification import send_completion_notification_to_client
        from loader import bot
        await send_completion_notification_to_client(bot, order_id, "technician")
    except Exception as e:
        print(f"Error sending completion notification: {e}")
        # Notification xatosi asosiy jarayonga ta'sir qilmaydi

    # Ro'yxatdan chiqaramiz
    orders = [o for o in orders if o["id"] != order_id]
    if not orders:
        await cq.message.edit_text("✅ Ariza yopildi.\n\n📭 Boshqa ariza yo'q" if lang == "uz"
                                   else "✅ Заявка закрыта.\n\n📭 Больше заявок нет")
        await state.clear()
        await cq.answer()
        return

    new_index = min(index, len(orders) - 1)
    await state.update_data(orders=orders, index=new_index)
    new_order = orders[new_index]
    text = get_order_text(new_order, lang, idx=new_index, total=len(orders))
    
    try:
        await cq.message.edit_text(
            "✅ Ariza yopildi.\n\n" + text if lang == "uz" else "✅ Заявка закрыта.\n\n" + text,
            reply_markup=get_inbox_controls(new_order["id"], lang, idx=new_index, total=len(orders)),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        pass
    
    await cq.answer("✅ Yopildi" if lang == "uz" else "✅ Закрыто", show_alert=True)
