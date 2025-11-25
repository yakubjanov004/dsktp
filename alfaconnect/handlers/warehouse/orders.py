from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
import html
import logging

from states.warehouse_states import MaterialRequestsStates
from filters.role_filter import RoleFilter
from database.basic.user import find_user_by_telegram_id
from database.warehouse.inbox import (
    fetch_material_requests_by_connection_orders,
    fetch_material_requests_by_technician_orders,
    fetch_material_requests_by_staff_orders,
    count_material_requests_by_connection_orders,
    count_material_requests_by_technician_orders,
    count_material_requests_by_staff_orders,
    get_all_material_requests_count,
)
from keyboards.warehouse_buttons import (
    get_warehouse_material_requests_keyboard,
    get_warehouse_material_requests_navigation_keyboard,
    get_warehouse_main_menu
)

router = Router()
router.message.filter(RoleFilter("warehouse"))
router.callback_query.filter(RoleFilter("warehouse"))

def fmt_dt(dt):
    """Format datetime for display"""
    if dt:
        return dt.strftime("%d.%m.%Y %H:%M")
    return "N/A"

def esc(text):
    """Escape HTML characters"""
    if text is None:
        return "N/A"
    return html.escape(str(text))

def format_material_request(material_request, index, total_count):
    """Format material request for display"""
    order_id = material_request.get('order_id', 'N/A')
    order_type = material_request.get('order_type', 'N/A')
    material_name = esc(material_request.get('material_name', 'N/A'))
    quantity = material_request.get('quantity', 0)
    client_name = esc(material_request.get('client_name', 'N/A'))
    client_phone = esc(material_request.get('client_phone', 'N/A'))
    address = esc(material_request.get('address', 'N/A'))
    created_at = fmt_dt(material_request.get('order_created_at'))
    
    application_number = material_request.get('application_number', 'N/A')
    if application_number != 'N/A':
        order_id = application_number
    
    order_type_text = {
        'connection': '🔗 Ulanish arizasi',
        'technician': '🔧 Texnik xizmat',
        'staff': '👥 Xodim arizasi'
    }.get(order_type, order_type)
    
    text = (
        f"📋 <b>Material so'rovi #{index + 1}/{total_count}</b>\n\n"
        f"🆔 <b>Ariza ID:</b> {order_id}\n"
        f"📝 <b>Ariza turi:</b> {order_type_text}\n"
        f"📦 <b>Material:</b> {material_name}\n"
        f"📊 <b>Miqdor:</b> {quantity}\n\n"
        f"👤 <b>Mijoz:</b> {client_name}\n"
        f"📞 <b>Telefon:</b> {client_phone}\n"
        f"📍 <b>Manzil:</b> {address}\n"
        f"📅 <b>Sana:</b> {created_at}"
    )
    
    return text

@router.message(F.text.in_(["📋 Buyurtmalar", "📋 Заказы"]))
async def material_requests_handler(message: Message, state: FSMContext):
    """Material requests handler - shows order type selection for materials"""
    user = await find_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi!")
        return
    
    lang = user.get("language", "uz")
    await state.set_state(MaterialRequestsStates.main_menu)
    
    # Get counts for each material request type
    counts = await get_all_material_requests_count()
    
    if lang == "ru":
        text = (
            f"📋 <b>Запросы материалов</b>\n\n"
            f"Информация по установленным материалам:\n\n"
            f"🔗 <b>Материалы заявок на подключение:</b> {counts['connection_orders']}\n"
            f"🔧 <b>Материалы технического обслуживания:</b> {counts['technician_orders']}\n"
            f"👥 <b>Материалы заявок сотрудников:</b> {counts['staff_orders']}\n\n"
            f"📊 <b>Всего:</b> {counts['total']}\n\n"
            f"Выберите одну из кнопок ниже:"
        )
    else:
        text = (
            f"📋 <b>Material so'rovlari</b>\n\n"
            f"O'rnatilgan materiallar bo'yicha ma'lumot:\n\n"
            f"🔗 <b>Ulanish arizalari materiallari:</b> {counts['connection_orders']}\n"
            f"🔧 <b>Texnik xizmat materiallari:</b> {counts['technician_orders']}\n"
            f"👥 <b>Xodim arizalari materiallari:</b> {counts['staff_orders']}\n\n"
            f"📊 <b>Jami:</b> {counts['total']}\n\n"
            f"Quyidagi tugmalardan birini tanlang:"
        )
    
    keyboard = get_warehouse_material_requests_keyboard(lang)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

# Connection orders material requests
@router.callback_query(F.data == "warehouse_material_requests_connection")
async def show_material_requests_connection(callback: CallbackQuery, state: FSMContext):
    """Show material requests for connection orders"""
    await state.set_state(MaterialRequestsStates.connection_orders)
    await state.update_data(current_index=0)
    
    material_requests = await fetch_material_requests_by_connection_orders(limit=1, offset=0)
    total_count = await count_material_requests_by_connection_orders()
    
    if not material_requests:
        await callback.message.edit_text(
            "📋 Ulanish arizalari uchun material so'rovlari topilmadi.",
            reply_markup=get_warehouse_material_requests_keyboard("uz")
        )
        await callback.answer()
        return
    
    text = format_material_request(material_requests[0], 0, total_count)
    keyboard = get_warehouse_material_requests_navigation_keyboard(0, total_count, "material_requests_connection", material_requests[0].get('application_number', ''))
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# Technician orders material requests
@router.callback_query(F.data == "warehouse_material_requests_technician")
async def show_material_requests_technician(callback: CallbackQuery, state: FSMContext):
    """Show material requests for technician orders"""
    await state.set_state(MaterialRequestsStates.technician_orders)
    await state.update_data(current_index=0)
    
    material_requests = await fetch_material_requests_by_technician_orders(limit=1, offset=0)
    total_count = await count_material_requests_by_technician_orders()
    
    if not material_requests:
        await callback.message.edit_text(
            "📋 Texnik xizmat uchun material so'rovlari topilmadi.",
            reply_markup=get_warehouse_material_requests_keyboard("uz")
        )
        await callback.answer()
        return
    
    text = format_material_request(material_requests[0], 0, total_count)
    keyboard = get_warehouse_material_requests_navigation_keyboard(0, total_count, "material_requests_technician", material_requests[0].get('application_number', ''))
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# Staff orders material requests
@router.callback_query(F.data == "warehouse_material_requests_staff")
async def show_material_requests_staff(callback: CallbackQuery, state: FSMContext):
    """Show material requests for staff orders"""
    await state.set_state(MaterialRequestsStates.staff_orders)
    await state.update_data(current_index=0)
    
    material_requests = await fetch_material_requests_by_staff_orders(limit=1, offset=0)
    total_count = await count_material_requests_by_staff_orders()
    
    if not material_requests:
        await callback.message.edit_text(
            "📋 Xodim arizalari uchun material so'rovlari topilmadi.",
            reply_markup=get_warehouse_material_requests_keyboard("uz")
        )
        await callback.answer()
        return
    
    text = format_material_request(material_requests[0], 0, total_count)
    keyboard = get_warehouse_material_requests_navigation_keyboard(0, total_count, "material_requests_staff", material_requests[0].get('application_number', ''))
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# Navigation handlers for material requests
@router.callback_query(F.data.startswith("warehouse_prev_material_requests_"))
async def navigate_material_requests_prev(callback: CallbackQuery, state: FSMContext):
    """Navigate to previous material request"""
    parts = callback.data.split("_")
    # For material_requests_connection: parts = ['warehouse', 'prev', 'material', 'requests', 'connection', 'index']
    request_type = "_".join(parts[2:5])  # material_requests_connection/technician/staff
    new_index = int(parts[5])
    
    await state.update_data(current_index=new_index)
    
    if request_type == "material_requests_connection":
        material_requests = await fetch_material_requests_by_connection_orders(limit=1, offset=new_index)
        total_count = await count_material_requests_by_connection_orders()
    elif request_type == "material_requests_technician":
        material_requests = await fetch_material_requests_by_technician_orders(limit=1, offset=new_index)
        total_count = await count_material_requests_by_technician_orders()
    elif request_type == "material_requests_staff":
        material_requests = await fetch_material_requests_by_staff_orders(limit=1, offset=new_index)
        total_count = await count_material_requests_by_staff_orders()
    else:
        await callback.answer("❌ Noto'g'ri so'rov turi!")
        return
    
    if material_requests:
        text = format_material_request(material_requests[0], new_index, total_count)
        keyboard = get_warehouse_material_requests_navigation_keyboard(new_index, total_count, request_type, material_requests[0].get('application_number', ''))
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()

@router.callback_query(F.data.startswith("warehouse_next_material_requests_"))
async def navigate_material_requests_next(callback: CallbackQuery, state: FSMContext):
    """Navigate to next material request"""
    parts = callback.data.split("_")
    # For material_requests_connection: parts = ['warehouse', 'next', 'material', 'requests', 'connection', 'index']
    request_type = "_".join(parts[2:5])  # material_requests_connection/technician/staff
    new_index = int(parts[5])
    
    await state.update_data(current_index=new_index)
    
    if request_type == "material_requests_connection":
        material_requests = await fetch_material_requests_by_connection_orders(limit=1, offset=new_index)
        total_count = await count_material_requests_by_connection_orders()
    elif request_type == "material_requests_technician":
        material_requests = await fetch_material_requests_by_technician_orders(limit=1, offset=new_index)
        total_count = await count_material_requests_by_technician_orders()
    elif request_type == "material_requests_staff":
        material_requests = await fetch_material_requests_by_staff_orders(limit=1, offset=new_index)
        total_count = await count_material_requests_by_staff_orders()
    else:
        await callback.answer("❌ Noto'g'ri so'rov turi!")
        return
    
    if material_requests:
        text = format_material_request(material_requests[0], new_index, total_count)
        keyboard = get_warehouse_material_requests_navigation_keyboard(new_index, total_count, request_type, material_requests[0].get('application_number', ''))
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()

# Back to material requests categories
@router.callback_query(F.data == "warehouse_back_to_categories")
async def back_to_material_requests_categories(callback: CallbackQuery, state: FSMContext):
    """Back to material requests categories"""
    current_state = await state.get_state()
    
    # Check if we're in material requests states
    if current_state and "MaterialRequestsStates" in str(current_state):
        await state.set_state(MaterialRequestsStates.main_menu)
        
        # Get counts for each material request type
        counts = await get_all_material_requests_count()
        
        text = (
            f"📋 <b>Material so'rovlari</b>\n\n"
            f"O'rnatilgan materiallar bo'yicha ma'lumot:\n\n"
            f"🔗 <b>Ulanish arizalari materiallari:</b> {counts['connection_orders']}\n"
            f"🔧 <b>Texnik xizmat materiallari:</b> {counts['technician_orders']}\n"
            f"👥 <b>Xodim arizalari materiallari:</b> {counts['staff_orders']}\n\n"
            f"📊 <b>Jami:</b> {counts['total']}\n\n"
            f"Quyidagi tugmalardan birini tanlang:"
        )
        
        keyboard = get_warehouse_material_requests_keyboard("uz")
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()

# Material confirmation handlers
@router.callback_query(F.data.startswith("warehouse_confirm_material_"))
async def confirm_material_request(callback: CallbackQuery, state: FSMContext):
    """Confirm material request and transfer materials to technician"""
    user = await find_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return
    
    # Parse callback data: warehouse_confirm_material_{order_type}_{order_id}
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("❌ Noto'g'ri format!", show_alert=True)
        return
    
    order_type = parts[3]  # material_requests_connection/technician/staff
    order_id = int(parts[4])
    
    try:
        # Import confirmation functions
        from database.warehouse.inbox import (
            confirm_materials_and_update_status_for_connection,
            confirm_materials_and_update_status_for_technician,
            confirm_materials_and_update_status_for_staff
        )
        
        # Call appropriate confirmation function
        if order_type == "material_requests_connection":
            success = await confirm_materials_and_update_status_for_connection(order_id, user["id"])
        elif order_type == "material_requests_technician":
            success = await confirm_materials_and_update_status_for_technician(order_id, user["id"])
        elif order_type == "material_requests_staff":
            success = await confirm_materials_and_update_status_for_staff(order_id, user["id"])
        else:
            await callback.answer("❌ Noto'g'ri ariza turi!", show_alert=True)
            return
        
        if success:
            await callback.message.edit_text(
                "✅ <b>Materiallar tasdiqlandi!</b>\n\n"
                f"📦 Materiallar texnikka o'tkazildi\n"
                f"🔄 Ariza holati yangilandi\n"
                f"📋 Ariza ID: {order_id}",
                parse_mode="HTML"
            )
            await callback.answer("✅ Muvaffaqiyatli tasdiqlandi!")
        else:
            await callback.answer("❌ Tasdiqlashda xatolik!", show_alert=True)
            
    except Exception as e:
        await callback.answer(f"❌ Xatolik: {str(e)}", show_alert=True)

# Back to main warehouse menu
@router.callback_query(F.data == "warehouse_material_requests_back")
async def material_requests_back(callback: CallbackQuery, state: FSMContext):
    """Back to main warehouse menu from material requests"""
    await callback.message.delete()
    await state.clear()
    
    await callback.message.answer(
        "🏠 Asosiy menyu:",
        reply_markup=get_warehouse_main_menu("uz")
    )
    await callback.answer()
