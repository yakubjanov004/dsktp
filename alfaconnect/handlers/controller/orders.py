# handlers/controller/applications.py
# Controller uchun "📋 Arizalarni ko'rish" — INLINE menyu va statistika.

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from filters.role_filter import RoleFilter
import os
import logging

from database.controller.statistics import (
    get_controller_statistics,
    ctrl_total_tech_orders_count,
    ctrl_new_in_controller_count,
    ctrl_in_progress_count,
    ctrl_completed_today_count,
    ctrl_cancelled_count,
    ctrl_get_new_orders,
    ctrl_get_in_progress_orders,
    ctrl_get_completed_today_orders,
    ctrl_get_cancelled_orders,
    ctrl_get_order_media,
)
from loader import bot

router = Router()
router.message.filter(RoleFilter("controller"))
router.callback_query.filter(RoleFilter("controller"))

# ---------- UI ----------
def _ctrl_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🆕 Yangi buyurtmalar", callback_data="ctrl:new")],
        [InlineKeyboardButton(text="⏳ Jarayondagilar", callback_data="ctrl:progress")],
        [InlineKeyboardButton(text="✅ Bugun bajarilgan", callback_data="ctrl:done_today")],
        [InlineKeyboardButton(text="❌ Bekor qilinganlar", callback_data="ctrl:cancelled")],
        [InlineKeyboardButton(text="♻️ Yangilash", callback_data="ctrl:refresh")],
        [InlineKeyboardButton(text="❌ Yopish", callback_data="ctrl:close")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _card_text(total:int, new_cnt:int, in_prog:int, done_today:int, cancelled:int) -> str:
    return (
        "🗂 <b>Buyurtmalar nazorati</b>\n\n"
        "📊 <b>Statistika:</b>\n"
        f"• Jami: <b>{total}</b>\n"
        f"• Yangi: <b>{new_cnt}</b>\n"
        f"• Jarayonda: <b>{in_prog}</b>\n"
        f"• Bugun bajarilgan: <b>{done_today}</b>\n"
        f"• Bekor qilinganlar: <b>{cancelled}</b>\n\n"
        "Quyidagini tanlang:"
    )

async def _load_stats():
    total = await ctrl_total_tech_orders_count()
    new_cnt = await ctrl_new_in_controller_count()
    in_prog = await ctrl_in_progress_count()
    done_today = await ctrl_completed_today_count()
    cancelled = await ctrl_cancelled_count()
    return total, new_cnt, in_prog, done_today, cancelled

async def _safe_edit(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.answer(text, reply_markup=kb, parse_mode="HTML")

def _format_order_item(order: dict, index: int, media_files: list = None) -> str:
    """Ariza elementini to'liq formatlash."""
    app_num = order.get('application_number', f"#{order.get('id', 'N/A')}")
    client_name = order.get('client_name', 'N/A')
    client_phone = order.get('client_phone', 'N/A')
    address = order.get('address', 'N/A')
    region = order.get('region', 'N/A')
    order_type = order.get('type_of_zayavka', 'N/A')
    business_type = order.get('business_type', 'N/A')
    description = order.get('description', 'N/A')
    abonent_id = order.get('abonent_id', 'N/A')
    tariff = order.get('tariff', 'N/A')
    status = order.get('status', 'N/A')
    created_at = order.get('created_at', 'N/A')
    updated_at = order.get('updated_at', 'N/A')
    
    # Vaqtni formatlash
    if created_at and hasattr(created_at, 'strftime'):
        created_str = created_at.strftime("%d.%m.%Y %H:%M")
    else:
        created_str = str(created_at)
        
    if updated_at and hasattr(updated_at, 'strftime'):
        updated_str = updated_at.strftime("%d.%m.%Y %H:%M")
    else:
        updated_str = str(updated_at)
    
    # Statusni o'zbek tiliga tarjima qilamiz
    status_uz = {
        'in_controller': 'Controllerda',
        'in_technician': 'Texnikda',
        'between_controller_technician': 'Controller-Texnik orasida',
        'in_manager': 'Menedjerda',
        'in_junior_manager': 'Kichik menedjerda',
        'completed': 'Bajarilgan',
        'cancelled': 'Bekor qilingan'
    }.get(status, status)
    
    text = f"<b>📋 ARIZA BATAFSIL MA'LUMOTLARI</b>\n"
    text += f"{'=' * 40}\n\n"
    text += f"<b>📄 Arizalar raqami:</b> {app_num}\n"
    text += f"<b>👤 Mijoz:</b> {client_name}\n"
    text += f"<b>📞 Telefon:</b> {client_phone}\n"
    text += f"<b>📍 Manzil:</b> {address}\n"
    text += f"<b>🌍 Hudud:</b> {region}\n"
    text += f"<b>🆔 Abonent ID:</b> {abonent_id}\n"
    text += f"<b>📋 Ariza turi:</b> {order_type}\n"
    text += f"<b>🏢 Business turi:</b> {business_type}\n"
    text += f"<b>📊 Holat:</b> {status_uz}\n"
    text += f"<b>📝 Tavsif:</b> {description}\n"
    text += f"<b>🕐 Yaratilgan:</b> {created_str}\n"
    text += f"<b>🔄 Yangilangan:</b> {updated_str}\n"
    
    if media_files:
        text += f"\n<b>📷 Media fayllar:</b> {len(media_files)} ta\n"
        for i, media in enumerate(media_files[:3], 1):  # Faqat birinchi 3 tasini ko'rsatamiz
            file_name = media.get('original_name', f'Fayl {i}')
            file_size = media.get('file_size', 0)
            if file_size:
                size_mb = file_size / (1024 * 1024)
                text += f"  • {file_name} ({size_mb:.1f} MB)\n"
            else:
                text += f"  • {file_name}\n"
        if len(media_files) > 3:
            text += f"  • ... va yana {len(media_files) - 3} ta\n"
    
    return text

def _create_pagination_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Paginatsiya tugmalarini yaratish."""
    keyboard = []
    
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"ctrl:page:{page-1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ctrl:current"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"ctrl:page:{page+1}"))
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="ctrl:back")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None

async def _format_orders_list(orders: list, title: str, page: int = 1, per_page: int = 1, call: CallbackQuery = None) -> tuple:
    """Arizalar ro'yxatini paginatsiya bilan formatlash."""
    if not orders:
        empty_text = f"{title}\n\n❌ Ma'lumot topilmadi."
        if call:
            try:
                # Eski xabarni o'chiramiz
                await call.message.delete()
            except:
                pass
            
            # Bo'sh xabar yuboramiz
            await call.message.answer(empty_text, parse_mode="HTML")
        return empty_text, None
    
    total_pages = (len(orders) + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_orders = orders[start_idx:end_idx]
    
    # Agar call bo'lsa, eski xabarni o'chiramiz
    if call:
        try:
            await call.message.delete()
        except:
            pass
    
    text = f"{title}\n"
    text += f"📄 Sahifa: {page}/{total_pages} | Jami: {len(orders)} ta\n\n"
    
    # Har bir ariza uchun media fayllarni olamiz va to'liq ma'lumotlarni ko'rsatamiz
    for i, order in enumerate(page_orders, start_idx + 1):
        order_id = order.get('id')
        order_type = order.get('type_of_zayavka', 'unknown')
        
        # Media fayllarni olamiz
        media_files = await ctrl_get_order_media(order_id, order_type)
        
        # To'liq ma'lumotlarni ko'rsatamiz (rasm ma'lumotini olib tashlaymiz)
        order_text = _format_order_item(order, i, media_files=None)  # Media ma'lumotini olib tashlaymiz
        
        # Paginatsiya tugmalarini yaratamiz
        reply_markup = _create_pagination_keyboard(page, total_pages)
        
        # Agar call bo'lsa, xabar yuboramiz
        if call:
            # Avval rasm bor yoki yo'qligini tekshiramiz
            media_sent = False
            
            if media_files:
                # Barcha media fayllarni tekshiramiz va birinchisini yuboramiz
                for media in media_files:
                    file_path = media.get('file_path')
                    file_type = media.get('file_type', 'photo')
                    original_name = media.get('original_name', 'Media fayl')
                    
                    try:
                        # Technician orders uchun file_path Telegram file_id bo'ladi
                        if file_path:
                            if file_type in ['photo', 'image']:
                                await bot.send_photo(
                                    chat_id=call.message.chat.id,
                                    photo=file_path,  # Telegram file_id
                                    caption=order_text,
                                    parse_mode='HTML',
                                    reply_markup=reply_markup
                                )
                            elif file_type in ['video']:
                                await bot.send_video(
                                    chat_id=call.message.chat.id,
                                    video=file_path,  # Telegram file_id
                                    caption=order_text,
                                    parse_mode='HTML',
                                    reply_markup=reply_markup
                                )
                            else:
                                await bot.send_document(
                                    chat_id=call.message.chat.id,
                                    document=file_path,  # Telegram file_id
                                    caption=order_text,
                                    parse_mode='HTML',
                                    reply_markup=reply_markup
                                )
                            media_sent = True
                            break  # Faqat birinchi media faylni yuboramiz
                    except Exception as e:
                        # Agar rasm yuborishda xatolik bo'lsa, keyingi faylni sinab ko'ramiz
                        print(f"Media yuborishda xatolik: {e}")
                        continue
            
            # Agar hech qanday media fayl yuborilmagan bo'lsa, faqat matn yuboramiz
            if not media_sent:
                await bot.send_message(
                    chat_id=call.message.chat.id,
                    text=order_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
        else:
            # Agar call bo'lmasa, faqat matn qo'shamiz
            text += order_text + "\n"
    
    # Agar call bo'lsa, faqat bitta xabar yuboriladi, qo'shimcha xabar kerak emas
    if call:
        return None, None
    
    # Agar call bo'lmasa, faqat matn qaytaramiz
    return text, _create_pagination_keyboard(page, total_pages)

def _format_order_detail(order: dict, media_files: list = None) -> str:
    """Ariza batafsil ma'lumotlarini formatlash."""
    app_num = order.get('application_number', f"#{order.get('id', 'N/A')}")
    client_name = order.get('client_name', 'N/A')
    client_phone = order.get('client_phone', 'N/A')
    address = order.get('address', 'N/A')
    region = order.get('region', 'N/A')
    order_type = order.get('type_of_zayavka', 'N/A')
    business_type = order.get('business_type', 'N/A')
    description = order.get('description', 'N/A')
    abonent_id = order.get('abonent_id', 'N/A')
    tariff = order.get('tariff', 'N/A')
    status = order.get('status', 'N/A')
    created_at = order.get('created_at', 'N/A')
    updated_at = order.get('updated_at', 'N/A')
    media = order.get('media', 'N/A')
    
    # Vaqtni formatlash
    if created_at and hasattr(created_at, 'strftime'):
        created_str = created_at.strftime("%d.%m.%Y %H:%M")
    else:
        created_str = str(created_at)
        
    if updated_at and hasattr(updated_at, 'strftime'):
        updated_str = updated_at.strftime("%d.%m.%Y %H:%M")
    else:
        updated_str = str(updated_at)
    
    # Statusni o'zbek tiliga tarjima qilamiz
    status_uz = {
        'in_controller': 'Controllerda',
        'in_technician': 'Texnikda',
        'between_controller_technician': 'Controller-Texnik orasida',
        'in_manager': 'Menedjerda',
        'in_junior_manager': 'Kichik menedjerda',
        'completed': 'Bajarilgan',
        'cancelled': 'Bekor qilingan'
    }.get(status, status)
    
    text = f"<b>📋 ARIZA BATAFSIL MA'LUMOTLARI</b>\n"
    text += f"{'=' * 40}\n\n"
    text += f"<b>📄 Arizalar raqami:</b> {app_num}\n"
    text += f"<b>👤 Mijoz:</b> {client_name}\n"
    text += f"<b>📞 Telefon:</b> {client_phone}\n"
    text += f"<b>📍 Manzil:</b> {address}\n"
    text += f"<b>🌍 Hudud:</b> {region}\n"
    text += f"<b>🆔 Abonent ID:</b> {abonent_id}\n"
    text += f"<b>📋 Ariza turi:</b> {order_type}\n"
    text += f"<b>🏢 Business turi:</b> {business_type}\n"
    text += f"<b>📊 Holat:</b> {status_uz}\n"
    text += f"<b>📝 Tavsif:</b> {description}\n"
    text += f"<b>🕐 Yaratilgan:</b> {created_str}\n"
    text += f"<b>🔄 Yangilangan:</b> {updated_str}\n"
    
    if media_files:
        text += f"\n<b>📷 Media fayllar:</b> {len(media_files)} ta\n"
        for i, media in enumerate(media_files[:3], 1):  # Faqat birinchi 3 tasini ko'rsatamiz
            file_name = media.get('original_name', f'Fayl {i}')
            file_size = media.get('file_size', 0)
            if file_size:
                size_mb = file_size / (1024 * 1024)
                text += f"  • {file_name} ({size_mb:.1f} MB)\n"
            else:
                text += f"  • {file_name}\n"
        if len(media_files) > 3:
            text += f"  • ... va yana {len(media_files) - 3} ta\n"
    
    return text

def _create_order_detail_keyboard(order: dict, all_orders: list, media_files: list = None) -> InlineKeyboardMarkup:
    """Ariza batafsil ko'rish uchun keyboard yaratish."""
    keyboard = []
    
    # Oldingi va keyingi ariza tugmalari
    current_order_id = order.get('id')
    current_order_type = order.get('type_of_zayavka')
    
    # Joriy arizaning indeksini topamiz
    current_index = -1
    for i, o in enumerate(all_orders):
        if o.get('id') == current_order_id and o.get('type_of_zayavka') == current_order_type:
            current_index = i
            break
    
    nav_buttons = []
    
    # Oldingi ariza
    if current_index > 0:
        prev_order = all_orders[current_index - 1]
        prev_id = prev_order.get('id')
        prev_type = prev_order.get('type_of_zayavka')
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Oldingi",
            callback_data=f"ctrl:detail:{prev_type}:{prev_id}"
        ))
    
    # Keyingi ariza
    if current_index < len(all_orders) - 1:
        next_order = all_orders[current_index + 1]
        next_id = next_order.get('id')
        next_type = next_order.get('type_of_zayavka')
        nav_buttons.append(InlineKeyboardButton(
            text="Keyingi ➡️",
            callback_data=f"ctrl:detail:{next_type}:{next_id}"
        ))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Media fayllarni ko'rish tugmasi
    if media_files:
        keyboard.append([InlineKeyboardButton(
            text=f"📷 Media fayllar ({len(media_files)})",
            callback_data=f"ctrl:media:{order.get('type_of_zayavka')}:{order.get('id')}"
        )])
    
    # Orqaga tugmasi
    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="ctrl:back")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def _back_button() -> InlineKeyboardMarkup:
    """Orqaga tugmasi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="ctrl:back")]
    ])

# ---------- Kirish (reply tugmadan) ----------
@router.message(F.text.in_(["📋 Arizalarni ko'rish", "📋 Просмотр заявок"]))
async def orders_handler(message: Message, state: FSMContext):
    """
    Controller menyusidagi "📋 Arizalarni ko'rish" bosilganda — statistik kartochka va inline menyu.
    """
    total, new_cnt, in_prog, done_today, cancelled = await _load_stats()
    await message.answer(
        _card_text(total, new_cnt, in_prog, done_today, cancelled),
        reply_markup=_ctrl_menu_kb()
    )

# ---------- Tugmalar (haqiqiy ma'lumotlar bilan paginatsiya) ----------
@router.callback_query(F.data == "ctrl:new")
async def ctrl_new(call: CallbackQuery, state: FSMContext):
    await call.answer("Yuklanmoqda...")
    try:
        orders = await ctrl_get_new_orders(limit=100)  # Ko'proq ma'lumot olamiz
        title = "🆕 <b>Yangi buyurtmalar</b>"
        # FSM state ga saqlaymiz
        await state.update_data(current_orders=orders, current_title=title)
        text, keyboard = await _format_orders_list(orders, title, page=1, call=call)
        # Agar call bo'lsa, _format_orders_list o'zi xabar yuboradi, qo'shimcha yubormaymiz
        # Agar bo'sh bo'lsa ham, _format_orders_list o'zi xabar yuboradi
        if not call and text:
            await _safe_edit(call, text, keyboard or _back_button())
    except Exception as e:
        await _safe_edit(call, f"🆕 <b>Yangi buyurtmalar</b>\n\n❌ Xatolik: {str(e)}", _back_button())

@router.callback_query(F.data == "ctrl:progress")
async def ctrl_progress(call: CallbackQuery, state: FSMContext):
    await call.answer("Yuklanmoqda...")
    try:
        orders = await ctrl_get_in_progress_orders(limit=100)
        title = "⏳ <b>Jarayondagilar</b>"
        # FSM state ga saqlaymiz
        await state.update_data(current_orders=orders, current_title=title)
        text, keyboard = await _format_orders_list(orders, title, page=1, call=call)
        # Agar call bo'lsa, _format_orders_list o'zi xabar yuboradi, qo'shimcha yubormaymiz
        # Agar bo'sh bo'lsa ham, _format_orders_list o'zi xabar yuboradi
        if not call and text:
            await _safe_edit(call, text, keyboard or _back_button())
    except Exception as e:
        await _safe_edit(call, f"⏳ <b>Jarayondagilar</b>\n\n❌ Xatolik: {str(e)}", _back_button())

@router.callback_query(F.data == "ctrl:done_today")
async def ctrl_done_today(call: CallbackQuery, state: FSMContext):
    await call.answer("Yuklanmoqda...")
    try:
        orders = await ctrl_get_completed_today_orders(limit=100)
        title = "✅ <b>Bugun bajarilgan</b>"
        # FSM state ga saqlaymiz
        await state.update_data(current_orders=orders, current_title=title)
        text, keyboard = await _format_orders_list(orders, title, page=1, call=call)
        # Agar call bo'lsa, _format_orders_list o'zi xabar yuboradi, qo'shimcha yubormaymiz
        # Agar bo'sh bo'lsa ham, _format_orders_list o'zi xabar yuboradi
        if not call and text:
            await _safe_edit(call, text, keyboard or _back_button())
    except Exception as e:
        await _safe_edit(call, f"✅ <b>Bugun bajarilgan</b>\n\n❌ Xatolik: {str(e)}", _back_button())

@router.callback_query(F.data == "ctrl:cancelled")
async def ctrl_cancelled(call: CallbackQuery, state: FSMContext):
    await call.answer("Yuklanmoqda...")
    try:
        orders = await ctrl_get_cancelled_orders(limit=100)
        title = "❌ <b>Bekor qilinganlar</b>"
        # FSM state ga saqlaymiz
        await state.update_data(current_orders=orders, current_title=title)
        text, keyboard = await _format_orders_list(orders, title, page=1, call=call)
        # Agar call bo'lsa, _format_orders_list o'zi xabar yuboradi, qo'shimcha yubormaymiz
        # Agar bo'sh bo'lsa ham, _format_orders_list o'zi xabar yuboradi
        if not call and text:
            await _safe_edit(call, text, keyboard or _back_button())
    except Exception as e:
        await _safe_edit(call, f"❌ <b>Bekor qilinganlar</b>\n\n❌ Xatolik: {str(e)}", _back_button())

@router.callback_query(F.data == "ctrl:refresh")
async def ctrl_refresh(call: CallbackQuery, state: FSMContext):
    await call.answer("Yangilanmoqda…")
    try:
        # Eski xabarni o'chiramiz
        await call.message.delete()
    except:
        pass
    
    total, new_cnt, in_prog, done_today, cancelled = await _load_stats()
    await call.message.answer(_card_text(total, new_cnt, in_prog, done_today, cancelled),
                              reply_markup=_ctrl_menu_kb(), parse_mode="HTML")

@router.callback_query(F.data == "ctrl:back")
async def ctrl_back(call: CallbackQuery, state: FSMContext):
    """Orqaga - asosiy menyuga qaytish."""
    await call.answer()
    try:
        # Eski xabarni o'chiramiz
        await call.message.delete()
    except:
        pass
    
    total, new_cnt, in_prog, done_today, cancelled = await _load_stats()
    await call.message.answer(_card_text(total, new_cnt, in_prog, done_today, cancelled),
                              reply_markup=_ctrl_menu_kb(), parse_mode="HTML")

@router.callback_query(F.data.startswith("ctrl:page:"))
async def ctrl_page(call: CallbackQuery, state: FSMContext):
    """Paginatsiya - sahifa o'zgartirish."""
    try:
        page = int(call.data.split(":")[2])
        # FSM state dan ma'lumotlarni olamiz
        data = await state.get_data()
        orders = data.get('current_orders', [])
        title = data.get('current_title', 'Arizalar')
        
        if orders:
            text, keyboard = await _format_orders_list(orders, title, page=page, call=call)
            # Agar call bo'lsa, _format_orders_list o'zi xabar yuboradi, qo'shimcha yubormaymiz
            # Agar bo'sh bo'lsa ham, _format_orders_list o'zi xabar yuboradi
            if not call and text:
                await _safe_edit(call, text, keyboard or _back_button())
        else:
            # Agar orders bo'sh bo'lsa, bo'sh xabar yuboramiz
            empty_text = f"{title}\n\n❌ Ma'lumot topilmadi."
            try:
                await call.message.delete()
            except:
                pass
            await call.message.answer(empty_text, parse_mode="HTML")
    except Exception as e:
        await call.answer(f"Xatolik: {str(e)}")

@router.callback_query(F.data == "ctrl:current")
async def ctrl_current_page(call: CallbackQuery, state: FSMContext):
    """Joriy sahifa - hech narsa qilmaymiz."""
    await call.answer()

@router.callback_query(F.data.startswith("ctrl:detail:"))
async def ctrl_order_detail(call: CallbackQuery, state: FSMContext):
    """Ariza batafsil ko'rish."""
    await call.answer("Yuklanmoqda...")
    try:
        # Callback data dan ma'lumotlarni olamiz: ctrl:detail:technician:123
        parts = call.data.split(":")
        order_type = parts[2]
        order_id = int(parts[3])
        
        # FSM state dan ma'lumotlarni olamiz
        data = await state.get_data()
        orders = data.get('current_orders', [])
        
        # Ariza topamiz
        order = None
        for o in orders:
            if o.get('id') == order_id and o.get('type_of_zayavka') == order_type:
                order = o
                break
        
        if not order:
            await call.answer("Ariza topilmadi")
            return
        
        # Media fayllarni olamiz
        media_files = await ctrl_get_order_media(order_id, order_type)
        
        # Ariza batafsil ma'lumotlarini formatlaymiz
        text = _format_order_detail(order, media_files)
        
        # Keyboard yaratamiz
        keyboard = _create_order_detail_keyboard(order, orders, media_files)
        
        await _safe_edit(call, text, keyboard)
        
    except Exception as e:
        await call.answer(f"Xatolik: {str(e)}")

@router.callback_query(F.data.startswith("ctrl:media:"))
async def ctrl_show_media(call: CallbackQuery, state: FSMContext):
    """Media fayllarni ko'rsatish."""
    await call.answer("Yuklanmoqda...")
    try:
        # Callback data dan ma'lumotlarni olamiz: ctrl:media:technician:123
        parts = call.data.split(":")
        order_type = parts[2]
        order_id = int(parts[3])
        
        # Media fayllarni olamiz
        media_files = await ctrl_get_order_media(order_id, order_type)
        
        if not media_files:
            await call.answer("Media fayllar topilmadi")
            return
        
        # Media fayllarni yuboramiz
        for media in media_files:
            file_path = media.get('file_path')
            file_type = media.get('file_type', 'photo')
            original_name = media.get('original_name', 'Media fayl')
            
            try:
                # Fayl mavjudligini tekshiramiz
                if not file_path or not os.path.exists(file_path):
                    await call.message.answer(f"❌ Fayl topilmadi: {original_name}")
                    continue
                
                # FSInputFile dan foydalanamiz
                file_input = FSInputFile(file_path, filename=original_name)
                
                if file_type in ['photo', 'image']:
                    await call.message.answer_photo(
                        photo=file_input,
                        caption=f"📷 {original_name}"
                    )
                elif file_type in ['video']:
                    await call.message.answer_video(
                        video=file_input,
                        caption=f"🎥 {original_name}"
                    )
                elif file_type in ['document']:
                    await call.message.answer_document(
                        document=file_input,
                        caption=f"📄 {original_name}"
                    )
                else:
                    await call.message.answer_document(
                        document=file_input,
                        caption=f"📎 {original_name}"
                    )
            except Exception as e:
                await call.message.answer(f"❌ Fayl yuklanmadi: {original_name}\nXatolik: {str(e)}")
        
        await call.answer(f"✅ {len(media_files)} ta media fayl yuborildi")
        
    except Exception as e:
        await call.answer(f"Xatolik: {str(e)}")

@router.callback_query(F.data == "ctrl:close")
async def ctrl_close(call: CallbackQuery, state: FSMContext):
    """Menyuni yopish."""
    await call.answer("Menyu yopildi")
    await call.message.delete()
