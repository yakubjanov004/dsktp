from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from datetime import datetime
import html
import logging

from database.manager.queries import (
    get_user_by_telegram_id,
    get_users_by_role,
    fetch_manager_inbox,
    assign_to_junior_manager,
    count_manager_inbox,
    get_juniors_with_load_via_history,
)
from filters.role_filter import RoleFilter

router = Router()
router.message.filter(RoleFilter("manager"))  # 🔒 faqat Manager uchun

logger = logging.getLogger(__name__)

# ==========================
# 🔧 UTIL
# ==========================
def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")

def esc(v) -> str:
    if v is None:
        return "-"
    return html.escape(str(v), quote=False)

# ==========================
# 🧩 VIEW + KEYBOARDS
# ==========================
def short_view_text(item: dict, index: int, total: int, lang: str) -> str:
    """Bitta arizaning qisqa ko'rinishini tayyorlaydi."""
    application_number = item.get("application_number")
    if application_number:
        short_id = application_number
    else:
        # Fallback: agar application_number yo'q bo'lsa
        full_id = str(item["id"])
        short_id = f"conn-{full_id.zfill(3)}"

    created = item["created_at"]
    created_dt = datetime.fromisoformat(created) if isinstance(created, str) else created

    tariff = esc(item.get("tariff", "-"))
    client_name = esc(item.get("client_name", "-"))
    client_phone = esc(item.get("client_phone", "-"))
    address = esc(item.get("address", "-"))
    short_id_safe = esc(short_id)

    if lang == "ru":
        base = (
            f"🔌 <b>Входящие менеджера</b>\n"
            f"🆔 <b>ID:</b> {short_id_safe}\n"
            f"📊 <b>Тариф:</b> {tariff}\n"
            f"👤 <b>Клиент:</b> {client_name}\n"
            f"📞 <b>Телефон:</b> {client_phone}\n"
            f"📍 <b>Адрес:</b> {address}\n"
            f"📅 <b>Создано:</b> {fmt_dt(created_dt)}"
        )
    else:
        base = (
            f"🔌 <b>Manager Inbox</b>\n"
            f"🆔 <b>ID:</b> {short_id_safe}\n"
            f"📊 <b>Tarif:</b> {tariff}\n"
            f"👤 <b>Mijoz:</b> {client_name}\n"
            f"📞 <b>Telefon:</b> {client_phone}\n"
            f"📍 <b>Manzil:</b> {address}\n"
            f"📅 <b>Yaratilgan:</b> {fmt_dt(created_dt)}"
        )


    # Footer
    if lang == "ru":
        base += f"\n\n📊 <b>{index + 1}/{total}</b>"
    else:
        base += f"\n\n📊 <b>{index + 1}/{total}</b>"

    return base

def nav_keyboard(lang: str, current_idx: int = 0, total: int = 1, mode: str = "connection") -> InlineKeyboardMarkup:
    """Navigation tugmalari - faqat client arizalari uchun."""
    buttons = []
    
    # Orqaga/Oldinga tugmalari
    nav_buttons = []
    if current_idx > 0:  # Birinchi arizada emas
        if lang == "ru":
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="prev_item"))
        else:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="prev_item"))
    
    if current_idx < total - 1:  # Oxirgi arizada emas
        if lang == "ru":
            nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data="next_item"))
        else:
            nav_buttons.append(InlineKeyboardButton(text="➡️ Oldinga", callback_data="next_item"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Client arizalari uchun - Junior managerga yuborish
    if lang == "ru":
        buttons.append([InlineKeyboardButton(text="🧑‍💼 Отправить младшему менеджеру", callback_data="assign_open")])
    else:
        buttons.append([InlineKeyboardButton(text="🧑‍💼 Kichik menejerga yuborish", callback_data="assign_open")])
    
    # Yopish tugmasi
    if lang == "ru":
        buttons.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close_inbox")])
    else:
        buttons.append([InlineKeyboardButton(text="❌ Yopish", callback_data="close_inbox")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def category_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Kategoriya tanlash tugmalari - faqat client arizalari."""
    if lang == "ru":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👤 Клиентские заявки", callback_data="cat_connection")],
            ]
        )
    else:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👤 Mijoz arizalari", callback_data="cat_connection")],
            ]
        )

def jm_list_keyboard(juniors: list, lang: str) -> InlineKeyboardMarkup:
    """Junior managerlar ro'yxati."""
    buttons = []
    for jm in juniors:
        name = esc(jm.get("full_name", "N/A"))
        load = jm.get("load_count", 0)
        if lang == "ru":
            text = f"👤 {name} ({load})"
        else:
            text = f"👤 {name} ({load}ta)"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"assign_jm_{jm['id']}")])
    
    if lang == "ru":
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="assign_back")])
    else:
        buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="assign_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==========================
# 🎯 HANDLERS
# ==========================

@router.message(F.text.in_(["📥 Inbox", "📥 Входящие"]))
async def open_inbox(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user.get("role") not in ("manager", "controller"):
        return

    lang = user.get("language", "uz")
    if lang not in ["uz", "ru"]:
        lang = "uz"

    await state.update_data(lang=lang, inbox=[], idx=0)

    inbox_items = await fetch_manager_inbox()
    total = await count_manager_inbox()
    await state.update_data(lang=lang, inbox=inbox_items, idx=0)
    if not inbox_items:
        text = "📭 Нет клиентских заявок" if lang == "ru" else "📭 Mijoz arizalari yo'q"
        await message.answer(text)
        return
    text = short_view_text(inbox_items[0], 0, total, lang)
    await message.answer(text, reply_markup=nav_keyboard(lang, 0, total, "connection"), parse_mode="HTML")
    

@router.callback_query(F.data == "cat_connection")
async def cat_connection_flow(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    await callback.message.edit_reply_markup()
    
    # Client arizalarini olamiz
    inbox_items = await fetch_manager_inbox()
    total = await count_manager_inbox()
    
    if not inbox_items:
        if lang == "ru":
            text = "📭 Нет клиентских заявок"
        else:
            text = "📭 Mijoz arizalari yo'q"
        await callback.message.answer(text)
        return
    
    await state.update_data(inbox=inbox_items, idx=0)
    
    # Birinchi arizani ko'rsatamiz
    text = short_view_text(inbox_items[0], 0, total, lang)
    await callback.message.answer(text, reply_markup=nav_keyboard(lang, 0, total, "connection"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "prev_item")
async def prev_item(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    inbox = data.get("inbox", [])
    idx = data.get("idx", 0)
    lang = data.get("lang", "uz")
    
    if not inbox:
        await callback.answer("❌ Нет данных" if lang == "ru" else "❌ Ma'lumot yo'q")
        return
    
    new_idx = (idx - 1) % len(inbox)
    await state.update_data(idx=new_idx)
    
    text = short_view_text(inbox[new_idx], new_idx, len(inbox), lang)
    await callback.message.edit_text(text, reply_markup=nav_keyboard(lang, new_idx, len(inbox), "connection"), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "next_item")
async def next_item(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    inbox = data.get("inbox", [])
    idx = data.get("idx", 0)
    lang = data.get("lang", "uz")
    
    if not inbox:
        await callback.answer("❌ Нет данных" if lang == "ru" else "❌ Ma'lumot yo'q")
        return
    
    new_idx = (idx + 1) % len(inbox)
    await state.update_data(idx=new_idx)
    
    text = short_view_text(inbox[new_idx], new_idx, len(inbox), lang)
    await callback.message.edit_text(text, reply_markup=nav_keyboard(lang, new_idx, len(inbox), "connection"), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "assign_open")
async def assign_open(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    inbox = data.get("inbox", [])
    idx = data.get("idx", 0)
    lang = data.get("lang", "uz")
    
    if not inbox or idx >= len(inbox):
        await callback.answer("❌ Нет данных" if lang == "ru" else "❌ Ma'lumot yo'q")
        return
    
    current_item = inbox[idx]
    
    # Eski message'ni o'chirib tashlaymiz
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    # Client arizasi -> Junior Manager
    juniors = await get_juniors_with_load_via_history()
    if not juniors:
        if lang == "ru":
            text = "❌ Нет доступных младших менеджеров"
        else:
            text = "❌ Mavjud junior manager yo'q"
        await callback.message.answer(text)
        return
    
    if lang == "ru":
        text = "👤 Выберите младшего менеджера:"
    else:
        text = "👤 Junior managerni tanlang:"
    
    await callback.message.answer(text, reply_markup=jm_list_keyboard(juniors, lang))
    await callback.answer()



@router.callback_query(F.data == "close_inbox")
async def close_inbox(callback: CallbackQuery, state: FSMContext):
    """Inbox yopish."""
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    # State ni tozalaymiz
    await state.clear()
    
    # Xabarni o'chirib tashlaymiz
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    if lang == "ru":
        text = "✅ Inbox закрыт"
    else:
        text = "✅ Inbox yopildi"
    
    await callback.answer(text)

@router.callback_query(F.data == "assign_back")
async def assign_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    inbox = data.get("inbox", [])
    idx = data.get("idx", 0)
    lang = data.get("lang", "uz")
    
    if not inbox or idx >= len(inbox):
        await callback.answer("❌ Нет данных" if lang == "ru" else "❌ Ma'lumot yo'q")
        return
    
    # Eski message'ni o'chirib tashlaymiz
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    # Yangi message yuboramiz
    text = short_view_text(inbox[idx], idx, len(inbox), lang)
    await callback.message.answer(text, reply_markup=nav_keyboard(lang, idx, len(inbox), "connection"), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("assign_jm_"))
async def assign_pick(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    inbox = data.get("inbox", [])
    idx = data.get("idx", 0)
    lang = data.get("lang", "uz")
    
    if not inbox or idx >= len(inbox):
        await callback.answer("❌ Нет данных" if lang == "ru" else "❌ Ma'lumot yo'q")
        return
    
    current_item = inbox[idx]
    jm_id = int(callback.data.split("_")[-1])
    
    try:
        # Manager'ning database ID'sini olamiz
        manager_user = await get_user_by_telegram_id(callback.from_user.id)
        if not manager_user:
            await callback.answer("❌ Manager topilmadi!" if lang == "uz" else "❌ Manager не найден!", show_alert=True)
            return
        
        manager_db_id = manager_user["id"]
        
        # Client ariza -> Junior Manager (notification info qaytaradi)
        recipient_info = await assign_to_junior_manager(current_item["id"], jm_id, manager_db_id)
        
        # Junior manager nomini olamiz
        jm_name = recipient_info.get("jm_name", "Noma'lum")
        app_number = recipient_info.get("application_number", "N/A")
        
        if lang == "ru":
            text = f"✅ Заявка {app_number} назначена младшему менеджеру {jm_name}"
        else:
            text = f"✅ Ariza {app_number} junior manager {jm_name}ga tayinlandi"
        
        # Inline klaviatura o'chirib, xabarni edit qilamiz
        await callback.message.edit_text(text, reply_markup=None)
        await callback.answer()
        
        # Junior Manager'ga notification yuboramiz
        try:
            from loader import bot
            
            # Notification matnini tayyorlash
            app_num = recipient_info["application_number"]
            current_load = recipient_info["current_load"]
            recipient_lang = recipient_info["language"]
            
            # Notification xabari
            if recipient_lang == "ru":
                notification = f"📬 <b>Новая заявка подключения</b>\n\n🆔 {app_num}\n\n📊 У вас теперь <b>{current_load}</b> активных заявок"
            else:
                notification = f"📬 <b>Yangi ulanish arizasi</b>\n\n🆔 {app_num}\n\n📊 Sizda yana <b>{current_load}ta</b> ariza bor"
            
            # Notification yuborish
            await bot.send_message(
                chat_id=recipient_info["telegram_id"],
                text=notification,
                parse_mode="HTML"
            )
            logger.info(f"Notification sent to junior manager {jm_id} for order {app_num}")
        except Exception as notif_error:
            logger.error(f"Failed to send notification: {notif_error}")
        
        # Inboxni yangilaymiz
        inbox_items = await fetch_manager_inbox()
        
        if not inbox_items:
            if lang == "ru":
                text = "📭 Нет заявок"
            else:
                text = "📭 Arizalar yo'q"
            await callback.message.answer(text)
            return
        
        new_idx = min(idx, len(inbox_items) - 1)
        await state.update_data(inbox=inbox_items, idx=new_idx)
        
        text = short_view_text(inbox_items[new_idx], new_idx, len(inbox_items), lang)
        await callback.message.answer(text, reply_markup=nav_keyboard(lang, new_idx, len(inbox_items), "connection"), parse_mode="HTML")
        
    except Exception as e:
        if lang == "ru":
            text = f"❌ Ошибка: {str(e)}"
        else:
            text = f"❌ Xatolik: {str(e)}"
        await callback.message.answer(text)
        await callback.answer()
