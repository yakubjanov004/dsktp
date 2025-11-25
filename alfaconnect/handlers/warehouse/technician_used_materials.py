# handlers/warehouse/technician_used_materials.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
import logging

from filters.role_filter import RoleFilter
from database.basic.user import find_user_by_telegram_id
from database.warehouse.material_issued_queries import (
    fetch_technician_used_materials,
    fetch_materials_for_application,
    count_technician_used_materials,
    fetch_technician_used_materials_by_type,
    count_technician_used_materials_by_type
)
from keyboards.warehouse_buttons import get_warehouse_main_menu
from database.basic.language import get_user_language

router = Router()
logger = logging.getLogger(__name__)
router.message.filter(RoleFilter("warehouse"))
router.callback_query.filter(RoleFilter("warehouse"))

def fmt_dt(dt) -> str:
    """Format datetime for display"""
    if dt:
        return dt.strftime("%d.%m.%Y %H:%M")
    return "N/A"

def esc(text) -> str:
    """Escape HTML characters"""
    if not text:
        return "-"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

@router.message(F.text.in_(["📋 Texnik ishlatgan materiallar", "📋 Материалы использованные техником"]))
async def technician_used_materials_menu(message: Message, state: FSMContext):
    """Texniklar ishlatgan materiallar menyusi - avval ariza turini tanlash"""
    lang = await get_user_language(message.from_user.id) or "uz"
    
    text = (
        "📋 <b>Texniklar ishlatgan materiallar</b>\n\n"
        "Qaysi turdagi arizalarni ko'rmoqchisiz?"
        if lang == "uz" else
        "📋 <b>Материалы использованные техником</b>\n\n"
        "Какие типы заявок вы хотите посмотреть?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Ulanish arizalari" if lang == "uz" else "🔗 Заявки на подключение", callback_data="used_mat_type_connection")],
        [InlineKeyboardButton(text="🔧 Texnik xizmat arizalari" if lang == "uz" else "🔧 Заявки на техническое обслуживание", callback_data="used_mat_type_technician")],
        [InlineKeyboardButton(text="👥 Xodim arizalari" if lang == "uz" else "👥 Заявки сотрудников", callback_data="used_mat_type_staff")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("used_mat_type_"))
async def show_materials_by_type(callback: CallbackQuery, state: FSMContext):
    """Ariza turiga qarab materiallarni ko'rsatish"""
    await callback.answer()
    lang = await get_user_language(callback.from_user.id) or "uz"
    
    request_type = callback.data.replace("used_mat_type_", "")
    await state.update_data(selected_type=request_type, current_index=0)
    
    materials = await fetch_technician_used_materials_by_type(request_type, limit=1, offset=0)
    total_count = await count_technician_used_materials_by_type(request_type)
    
    type_texts = {
        "connection": "Ulanish arizalari" if lang == "uz" else "Заявки на подключение",
        "technician": "Texnik xizmat arizalari" if lang == "uz" else "Заявки на техническое обслуживание", 
        "staff": "Xodim arizalari" if lang == "uz" else "Заявки сотрудников"
    }
    type_text = type_texts.get(request_type, request_type)
    
    if not materials:
        if lang == "ru":
            text = (
                f"📋 <b>{type_text}</b>\n\n❌ В настоящее время нет заявок этого типа."
            )
        else:
            text = (
                f"📋 <b>{type_text}</b>\n\n❌ Hozirda bu turdagi arizalar yo'q."
            )
        await callback.message.edit_text(text, parse_mode="HTML")
        return
    
    material = materials[0]
    text = format_used_material(material, 0, total_count, lang)
    keyboard = get_used_materials_navigation_keyboard(0, total_count, material.get('application_number', ''), material.get('request_type', ''), lang)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

def format_used_material(material: dict, index: int, total: int, lang: str) -> str:
    """Format used material for display"""
    app_num = esc(material.get('application_number', ''))
    request_type = material.get('request_type', '')
    technician_name = esc(material.get('technician_name', ''))
    materials_count = material.get('materials_count', 0)
    total_cost = material.get('total_cost', 0)
    issued_at = fmt_dt(material.get('issued_at'))
    
    # Request type translation
    type_text = {
        'connection': 'Ulanish' if lang == "uz" else 'Подключение',
        'technician': 'Texnik xizmat' if lang == "uz" else 'Техническое обслуживание',
        'staff': 'Xodim arizasi' if lang == "uz" else 'Заявка сотрудника'
    }.get(request_type, request_type)
    
    if lang == "ru":
        text = (
            f"📋 <b>Материалы использованные техником</b>\n\n"
            f"<b>Заявка {app_num}</b>\n"
            f"📝 Тип: {type_text}\n"
            f"👨‍🔧 Техник: {technician_name}\n"
            f"📦 Материалов: {materials_count}\n"
            f"💰 Общая стоимость: {total_cost:,.0f} сум\n"
            f"📅 Использовано: {issued_at}\n"
            f"\n🗂️ <i>Заявка {index + 1} / {total}</i>"
        )
    else:
        text = (
            f"📋 <b>Texniklar ishlatgan materiallar</b>\n\n"
            f"<b>Ariza {app_num}</b>\n"
            f"📝 Turi: {type_text}\n"
            f"👨‍🔧 Texnik: {technician_name}\n"
            f"📦 Materiallar: {materials_count}\n"
            f"💰 Umumiy narx: {total_cost:,.0f} so'm\n"
            f"📅 Ishlatilgan: {issued_at}\n"
            f"\n🗂️ <i>Ariza {index + 1} / {total}</i>"
        )
    
    return text

def get_used_materials_navigation_keyboard(index: int, total: int, application_number: str, request_type: str, lang: str = "uz") -> InlineKeyboardMarkup:
    """Get navigation keyboard for used materials"""
    keyboard = []
    
    # Navigation buttons
    nav_buttons = []
    if index > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"used_mat_prev_{index}"))
    if index < total - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"used_mat_next_{index}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # View details button
    keyboard.append([
        InlineKeyboardButton(
            text="📋 Tafsilotlarni ko'rish" if lang == "uz" else "📋 Посмотреть детали",
            callback_data=f"used_mat_details_{application_number}_{request_type}"
        )
    ])
    
    # Back button
    keyboard.append([
        InlineKeyboardButton(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад", callback_data="warehouse_back_to_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.callback_query(F.data.startswith("used_mat_prev_"))
async def prev_used_material(callback: CallbackQuery, state: FSMContext):
    """Previous used material"""
    await callback.answer()
    data = await state.get_data()
    index = int(callback.data.replace("used_mat_prev_", "")) - 1
    
    selected_type = data.get('selected_type', 'connection')
    
    materials = await fetch_technician_used_materials_by_type(selected_type, limit=1, offset=index)
    total_count = await count_technician_used_materials_by_type(selected_type)
    
    if materials:
        material = materials[0]
        lang = await get_user_language(callback.from_user.id) or "uz"
        text = format_used_material(material, index, total_count, lang)
        keyboard = get_used_materials_navigation_keyboard(index, total_count, material.get('application_number', ''), material.get('request_type', ''), lang)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.update_data(current_index=index)

@router.callback_query(F.data.startswith("used_mat_next_"))
async def next_used_material(callback: CallbackQuery, state: FSMContext):
    """Next used material"""
    await callback.answer()
    data = await state.get_data()
    index = int(callback.data.replace("used_mat_next_", "")) + 1
    
    selected_type = data.get('selected_type', 'connection')
    
    materials = await fetch_technician_used_materials_by_type(selected_type, limit=1, offset=index)
    total_count = await count_technician_used_materials_by_type(selected_type)
    
    if materials:
        material = materials[0]
        lang = await get_user_language(callback.from_user.id) or "uz"
        text = format_used_material(material, index, total_count, lang)
        keyboard = get_used_materials_navigation_keyboard(index, total_count, material.get('application_number', ''), material.get('request_type', ''), lang)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.update_data(current_index=index)

@router.callback_query(F.data.startswith("used_mat_details_"))
async def show_material_details(callback: CallbackQuery, state: FSMContext):
    """Show detailed materials for specific application"""
    await callback.answer()
    
    # Parse callback data: used_mat_details_{application_number}_{request_type}
    parts = callback.data.replace("used_mat_details_", "").split("_", 1)
    if len(parts) != 2:
        return
    
    application_number = parts[0]
    request_type = parts[1]
    
    materials = await fetch_materials_for_application(application_number, request_type)
    lang = await get_user_language(callback.from_user.id) or "uz"
    
    if not materials:
        if lang == "ru":
            text = "❌ Материалы не найдены"
        else:
            text = "❌ Materiallar topilmadi"
        await callback.message.edit_text(text)
        return
    
    # Format materials list
    if lang == "ru":
        text = f"📋 <b>Детали материалов для заявки {application_number}</b>\n\n"
    else:
        text = f"📋 <b>Ariza {application_number} uchun materiallar tafsilotlari</b>\n\n"
    
    total_cost = 0
    for i, mat in enumerate(materials, 1):
        material_name = esc(mat.get('material_name', ''))
        quantity = mat.get('quantity', 0)
        price = mat.get('price', 0)
        total_price = mat.get('total_price', 0)
        technician_name = esc(mat.get('technician_name', ''))
        
        total_cost += total_price
        
        if lang == "ru":
            text += (
                f"{i}. <b>{material_name}</b>\n"
                f"   📦 Количество: {quantity}\n"
                f"   💰 Цена: {price:,.0f} сум\n"
                f"   💵 Сумма: {total_price:,.0f} сум\n"
                f"   👨‍🔧 Техник: {technician_name}\n\n"
            )
        else:
            text += (
                f"{i}. <b>{material_name}</b>\n"
                f"   📦 Miqdor: {quantity}\n"
                f"   💰 Narx: {price:,.0f} so'm\n"
                f"   💵 Summa: {total_price:,.0f} so'm\n"
                f"   👨‍🔧 Texnik: {technician_name}\n\n"
            )
    
    if lang == "ru":
        text += f"💰 <b>Общая стоимость: {total_cost:,.0f} сум</b>"
    else:
        text += f"💰 <b>Umumiy narx: {total_cost:,.0f} so'm</b>"
    
    # Back button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад", callback_data="used_mat_back_to_list")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "used_mat_back_to_list")
async def back_to_used_materials_list(callback: CallbackQuery, state: FSMContext):
    """Back to used materials list"""
    await callback.answer()
    data = await state.get_data()
    index = data.get('current_index', 0)
    selected_type = data.get('selected_type', 'connection')
    
    materials = await fetch_technician_used_materials_by_type(selected_type, limit=1, offset=index)
    total_count = await count_technician_used_materials_by_type(selected_type)
    
    if materials:
        material = materials[0]
        lang = await get_user_language(callback.from_user.id) or "uz"
        text = format_used_material(material, index, total_count, lang)
        keyboard = get_used_materials_navigation_keyboard(index, total_count, material.get('application_number', ''), material.get('request_type', ''), lang)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "warehouse_back_to_main")
async def back_to_warehouse_main(callback: CallbackQuery, state: FSMContext):
    """Back to warehouse main menu - 3 talik menyuga qaytarish"""
    await callback.answer()
    lang = await get_user_language(callback.from_user.id) or "uz"
    
    text = (
        "📋 <b>Texniklar ishlatgan materiallar</b>\n\n"
        "Qaysi turdagi arizalarni ko'rmoqchisiz?"
        if lang == "uz" else
        "📋 <b>Материалы использованные техником</b>\n\n"
        "Какие типы заявок вы хотите посмотреть?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Ulanish arizalari" if lang == "uz" else "🔗 Заявки на подключение", callback_data="used_mat_type_connection")],
        [InlineKeyboardButton(text="🔧 Texnik xizmat arizalari" if lang == "uz" else "🔧 Заявки на техническое обслуживание", callback_data="used_mat_type_technician")],
        [InlineKeyboardButton(text="👥 Xodim arizalari" if lang == "uz" else "👥 Заявки сотрудников", callback_data="used_mat_type_staff")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
