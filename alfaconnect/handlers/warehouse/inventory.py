# handlers/inventory.py
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.fsm.state import StatesGroup, State
from decimal import Decimal, InvalidOperation
import logging

from filters.role_filter import RoleFilter
from keyboards.warehouse_buttons import (
    get_warehouse_main_menu,
    get_inventory_actions_keyboard,
)
from states.warehouse_states import WarehouseStates, AddMaterialStates, UpdateMaterialStates
from database.warehouse.materials import (
    create_material,
    search_materials,
    get_all_materials,
    get_material_by_id,
    update_material_quantity,
    update_material_name_description,
    get_low_stock_materials,
    get_out_of_stock_materials
)
from database.basic.language import get_user_language

router = Router()
router.message.filter(RoleFilter("warehouse"))

class SearchMaterialStates(StatesGroup):
    query = State()

def cancel_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    cancel_text = "❌ Отмена" if lang == "ru" else "❌ Bekor qilish"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=cancel_text)]],
        resize_keyboard=True
    )

def fmt_sum(val: Decimal | int | float | None) -> str:
    if val is None:
        return "0"
    return f"{Decimal(val):,.0f}".replace(",", " ")

# Inventarizatsiya menyusiga kirish
@router.message(F.text.in_(["📦 Inventarizatsiya", "📦 Инвентаризация"]))
async def inventory_handler(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    await state.set_state(WarehouseStates.inventory_menu)
    
    if lang == "ru":
        await message.answer("📦 Управление инвентаризацией", reply_markup=get_inventory_actions_keyboard("ru"))
    else:
        await message.answer("📦 Inventarizatsiya boshqaruvi", reply_markup=get_inventory_actions_keyboard("uz"))

# Orqaga (faqat inventarizatsiya holatida)
@router.message(StateFilter(WarehouseStates.inventory_menu), F.text.in_(["◀️ Orqaga", "🔙 Orqaga", "◀️ Назад", "Orqaga"]))
async def inventory_back(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    await state.clear()
    
    if lang == "ru":
        await message.answer("⬅️ Главное меню", reply_markup=get_warehouse_main_menu("ru"))
    else:
        await message.answer("⬅️ Asosiy menyu", reply_markup=get_warehouse_main_menu("uz"))

# ============== ➕ Mahsulot qo'shish oqimi ==============

@router.message(StateFilter(WarehouseStates.inventory_menu), F.text.in_(["➕ Mahsulot qo'shish", "➕ Добавить товар"]))
async def inv_add_start(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    
    if lang == "ru":
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🆕 Добавить новый товар")],
                [KeyboardButton(text="📦 Изменить количество товара")],
                [KeyboardButton(text="❌ Отмена")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            "➕ Добавление товара\n\n"
            "Выберите один из вариантов:",
            reply_markup=keyboard
        )
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🆕 Yangi mahsulot qo'shish")],
                [KeyboardButton(text="📦 Mavjud mahsulot sonini o'zgartirish")],
                [KeyboardButton(text="❌ Bekor qilish")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            "➕ Mahsulot qo'shish\n\n"
            "Quyidagilardan birini tanlang:",
            reply_markup=keyboard
        )

# Yangi mahsulot qo'shish
@router.message(StateFilter(WarehouseStates.inventory_menu), F.text.in_(["🆕 Yangi mahsulot qo'shish", "🆕 Добавить новый товар"]))
async def inv_add_new_start(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    await state.set_state(AddMaterialStates.name)
    
    if lang == "ru":
        await message.answer("🏷️ Введите название товара:", reply_markup=cancel_kb("ru"))
    else:
        await message.answer("🏷️ Mahsulot nomini kiriting:", reply_markup=cancel_kb())

# Mavjud mahsulot sonini o'zgartirish
@router.message(StateFilter(WarehouseStates.inventory_menu), F.text.in_(["📦 Mavjud mahsulot sonini o'zgartirish", "📦 Изменить количество товара"]))
async def inv_update_existing_start(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    await state.set_state(UpdateMaterialStates.search)
    
    if lang == "ru":
        await message.answer("🔎 Введите название товара, количество которого хотите изменить:", reply_markup=cancel_kb("ru"))
    else:
        await message.answer("🔎 Miqdorini o'zgartirmoqchi bo'lgan mahsulot nomini kiriting:", reply_markup=cancel_kb())

@router.message(StateFilter(AddMaterialStates.name))
async def inv_add_name(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    if message.text.strip().lower() in ("❌ bekor qilish", "bekor", "cancel", "❌ отмена", "отмена"):
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer("❌ Отменено.\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer("❌ Bekor qilindi.\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

    name = message.text.strip()
    if len(name) < 2:
        if lang == "ru":
            return await message.answer("❗ Название слишком короткое. Введите заново:")
        else:
            return await message.answer("❗ Nomi juda qisqa. Qaytadan kiriting:")

    await state.update_data(name=name)
    await state.set_state(AddMaterialStates.quantity)
    
    if lang == "ru":
        await message.answer("📦 Введите количество (целое число):")
    else:
        await message.answer("📦 Miqdorni kiriting (butun son):")

@router.message(StateFilter(AddMaterialStates.quantity))
async def inv_add_quantity(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    txt = message.text.strip()
    
    if txt.lower() in ("❌ bekor qilish", "bekor", "cancel", "❌ отмена", "отмена"):
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer("❌ Отменено.\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer("❌ Bekor qilindi.\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

    if not txt.isdigit():
        if lang == "ru":
            return await message.answer("❗ Введите только целое число. Попробуйте снова:")
        else:
            return await message.answer("❗ Faqat butun son kiriting. Qayta kiriting:")

    qty = int(txt)
    if qty < 0:
        if lang == "ru":
            return await message.answer("❗ Количество не может быть отрицательным. Попробуйте снова:")
        else:
            return await message.answer("❗ Miqdor manfiy bo'lishi mumkin emas. Qayta kiriting:")

    await state.update_data(quantity=qty)
    await state.set_state(AddMaterialStates.price)
    
    if lang == "ru":
        await message.answer("💰 Введите цену (сум) — целое число или в формате 100000.00:")
    else:
        await message.answer("💰 Narxni kiriting (so'm) — butun son yoki 100000.00 ko'rinishida:")

@router.message(StateFilter(AddMaterialStates.price))
async def inv_add_price(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    txt = message.text.strip()
    
    if txt.lower() in ("❌ bekor qilish", "bekor", "cancel", "❌ отмена", "отмена"):
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer("❌ Отменено.\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer("❌ Bekor qilindi.\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

    # vergul/bo'shliqni tozalash
    norm = txt.replace(" ", "").replace(",", ".")
    try:
        price = Decimal(norm)
        if price < 0:
            if lang == "ru":
                return await message.answer("❗ Цена не может быть отрицательной. Попробуйте снова:")
            else:
                return await message.answer("❗ Narx manfiy bo'lishi mumkin emas. Qayta kiriting:")
    except InvalidOperation:
        if lang == "ru":
            return await message.answer("❗ Неверный формат. Например: 500000 или 500000.00. Попробуйте снова:")
        else:
            return await message.answer("❗ Noto'g'ri format. Masalan: 500000 yoki 500000.00. Qayta kiriting:")

    await state.update_data(price=price)
    await state.set_state(AddMaterialStates.description)
    
    if lang == "ru":
        await message.answer("📝 Введите описание товара (необязательно, для пропуска напишите \"-\"):")
    else:
        await message.answer("📝 Mahsulot tavsifi kiriting (ixtiyoriy, o'tkazib yuborish uchun \"-\" yozing):")

@router.message(StateFilter(AddMaterialStates.description))
async def inv_add_description(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    txt = message.text.strip()
    
    if txt.lower() in ("❌ bekor qilish", "bekor", "cancel", "❌ отмена", "отмена"):
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer("❌ Отменено.\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer("❌ Bekor qilindi.\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

    description = None if txt in ("-", "") else txt
    await state.update_data(description=description)
    await state.set_state(AddMaterialStates.material_unit)
    
    if lang == "ru":
        await message.answer("📏 Введите единицу измерения (например: dona, metr, litr, kg). По умолчанию: dona")
    else:
        await message.answer("📏 O'lchov birligini kiriting (masalan: dona, metr, litr, kg). Standart: dona")

@router.message(StateFilter(AddMaterialStates.material_unit))
async def inv_add_material_unit(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    txt = message.text.strip()
    
    if txt.lower() in ("❌ bekor qilish", "bekor", "cancel", "❌ отмена", "отмена"):
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer("❌ Отменено.\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer("❌ Bekor qilindi.\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

    material_unit = txt if txt else "dona"

    data = await state.get_data()
    name = data["name"]
    qty = data["quantity"]
    price = data["price"]
    description = data.get("description")

    try:
        created = await create_material(
            name=name,
            quantity=qty,
            price=price,
            description=description,
            serial_number=None,  # hozircha kiritmaymiz
            material_unit=material_unit
        )
    except Exception as e:
        # DB xatosi
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer(f"❌ Ошибка: данные не записаны в базу.\nДетали: {e}\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer(f"❌ Xatolik: ma'lumot bazaga yozilmadi.\nDetails: {e}\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

    # Muvaffaqiyat
    await state.set_state(WarehouseStates.inventory_menu)
    if lang == "ru":
        await message.answer(
            "✅ Товар успешно добавлен!\n"
            f"🏷️ Название: <b>{created['name']}</b>\n"
            f"📦 Количество: <b>{created['quantity']}</b> {created.get('material_unit', 'dona')}\n"
            f"💰 Цена: <b>{fmt_sum(created['price'])} сум</b>",
            parse_mode="HTML",
            reply_markup=get_inventory_actions_keyboard("ru")
        )
        await message.answer("📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
    else:
        await message.answer(
            "✅ Mahsulot muvaffaqiyatli qo'shildi!\n"
            f"🏷️ Nom: <b>{created['name']}</b>\n"
            f"📦 Miqdor: <b>{created['quantity']}</b> {created.get('material_unit', 'dona')}\n"
            f"💰 Narx: <b>{fmt_sum(created['price'])} so'm</b>",
            parse_mode="HTML",
            reply_markup=get_inventory_actions_keyboard("uz")
        )
        await message.answer("📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

# ============== ✏️ Mahsulotni yangilash oqimi ==============

@router.message(StateFilter(WarehouseStates.inventory_menu), F.text.in_(["✏️ Mahsulotni yangilash", "✏️ Обновить товар"]))
async def inv_update_start(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    await state.set_state(UpdateMaterialStates.search)
    
    if lang == "ru":
        await message.answer("🔎 Введите название товара, который хотите обновить:", reply_markup=cancel_kb("ru"))
    else:
        await message.answer("🔎 Yangilamoqchi bo'lgan mahsulot nomini kiriting:", reply_markup=cancel_kb())

@router.message(StateFilter(UpdateMaterialStates.search))
async def inv_update_search(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    
    if message.text.strip().lower() in ("❌ bekor qilish", "bekor", "cancel", "❌ отмена", "отмена"):
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer("❌ Отменено.\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer("❌ Bekor qilindi.\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

    search_term = message.text.strip()
    if len(search_term) < 2:
        if lang == "ru":
            return await message.answer("❗ Поисковый запрос слишком короткий. Введите заново:")
        else:
            return await message.answer("❗ Qidiruv so'zi juda qisqa. Qaytadan kiriting:")

    try:
        materials = await search_materials(search_term)
        if not materials:
            if lang == "ru":
                return await message.answer("❌ Товары не найдены. Попробуйте другой поисковый запрос:")
            else:
                return await message.answer("❌ Hech qanday mahsulot topilmadi. Boshqa nom bilan qidiring:")

        # Mahsulotlar ro'yxatini ko'rsatish
        if lang == "ru":
            text = "📋 Найденные товары:\n\n"
        else:
            text = "📋 Topilgan mahsulotlar:\n\n"
        
        keyboard_buttons = []
        
        for i, material in enumerate(materials[:10], 1):  # faqat 10 tasini ko'rsatamiz
            if lang == "ru":
                text += f"{i}. <b>{material['name']}</b>\n"
                text += f"   📦 Количество: {material['quantity']}\n"
                text += f"   💰 Цена: {fmt_sum(material['price'])} сум\n\n"
            else:
                text += f"{i}. <b>{material['name']}</b>\n"
                text += f"   📦 Miqdor: {material['quantity']}\n"
                text += f"   💰 Narx: {fmt_sum(material['price'])} so'm\n\n"
            keyboard_buttons.append([KeyboardButton(text=f"{i}. {material['name']}")])
        
        cancel_text = "❌ Отмена" if lang == "ru" else "❌ Bekor qilish"
        keyboard_buttons.append([KeyboardButton(text=cancel_text)])
        keyboard = ReplyKeyboardMarkup(keyboard=keyboard_buttons, resize_keyboard=True)
        
        await state.update_data(materials=materials)
        await state.set_state(UpdateMaterialStates.select)
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        
        if lang == "ru":
            await message.answer("👆 Выберите нужный товар из списка выше:")
        else:
            await message.answer("👆 Yuqoridagi ro'yxatdan kerakli mahsulotni tanlang:")
        
    except Exception as e:
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer(f"❌ Ошибка: {e}\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer(f"❌ Xatolik: {e}\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

# ============== 📄 Barcha mahsulotlar ==============

@router.message(StateFilter(WarehouseStates.inventory_menu), F.text.in_(["📄 Barcha mahsulotlar", "📄 Все товары"]))
async def inv_all_materials(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    
    try:
        materials = await get_all_materials()
        if not materials:
            if lang == "ru":
                return await message.answer("📄 Пока нет товаров.")
            else:
                return await message.answer("📄 Hozircha hech qanday mahsulot yo'q.")
        
        # Paginatsiya uchun ma'lumotlarni saqlash
        await state.update_data(all_materials=materials, current_page=0)
        
        # Birinchi sahifani ko'rsatish
        await show_materials_page(message, materials, 0, state, lang)
        
    except Exception as e:
        if lang == "ru":
            await message.answer(f"❌ Ошибка: {e}")
        else:
            await message.answer(f"❌ Xatolik: {e}")

async def show_materials_page(message: Message, materials: list, page: int, state: FSMContext, lang: str = "uz"):
    """Mahsulotlarni sahifa bo'yicha ko'rsatish"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    items_per_page = 7
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_materials = materials[start_idx:end_idx]
    
    total_pages = (len(materials) + items_per_page - 1) // items_per_page
    
    if lang == "ru":
        text = f"📄 Все товары (Страница {page + 1}/{total_pages}):\n\n"
    else:
        text = f"📄 Barcha mahsulotlar (Sahifa {page + 1}/{total_pages}):\n\n"
    
    for i, material in enumerate(page_materials, start=start_idx + 1):
        if lang == "ru":
            text += f"{i}. <b>{material['name']}</b>\n"
            text += f"   📦 Количество: {material['quantity']}\n"
            text += f"   💰 Цена: {fmt_sum(material['price'])} сум\n"
            if material.get('description'):
                text += f"   📝 Описание: {material['description']}\n"
        else:
            text += f"{i}. <b>{material['name']}</b>\n"
            text += f"   📦 Miqdor: {material['quantity']}\n"
            text += f"   💰 Narx: {fmt_sum(material['price'])} so'm\n"
            if material.get('description'):
                text += f"   📝 Tavsif: {material['description']}\n"
        text += "\n"
    
    # Paginatsiya tugmalari
    buttons = []
    
    if len(materials) > items_per_page:
        if page > 0:
            prev_text = "⬅️ Предыдущая" if lang == "ru" else "⬅️ Oldingi"
            buttons.append(InlineKeyboardButton(text=prev_text, callback_data=f"materials_page_{page-1}"))
        if page < total_pages - 1:
            next_text = "Следующая ➡️" if lang == "ru" else "Keyingi ➡️"
            buttons.append(InlineKeyboardButton(text=next_text, callback_data=f"materials_page_{page+1}"))
    
    keyboard_rows = []
    if buttons:
        keyboard_rows.append(buttons)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    try:
        await message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except:
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

# Paginatsiya callback handlerlari

@router.callback_query(F.data.startswith('materials_page_'))
async def materials_pagination_handler(callback_query: CallbackQuery, state: FSMContext):
    """Paginatsiya tugmalarini boshqarish"""
    try:
        page = int(callback_query.data.split('_')[-1])
        data = await state.get_data()
        materials = data.get('all_materials', [])
        lang = await get_user_language(callback_query.from_user.id) or "uz"
        
        await state.update_data(current_page=page)
        await show_materials_page(callback_query.message, materials, page, state, lang)
        await callback_query.answer()
        
    except Exception as e:
        lang = await get_user_language(callback_query.from_user.id) or "uz"
        await callback_query.answer(
            "❌ Xatolik yuz berdi" if lang == "uz" else "❌ Произошла ошибка",
            show_alert=True
        )

# ============== 🔎 Qidirish ==============

@router.message(StateFilter(WarehouseStates.inventory_menu), F.text.in_(["🔎 Qidirish", "🔎 Поиск"]))
async def inv_search_start(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    # Alhida state — boshqa tugmalar bilan to'qnashmaydi
    await state.set_state(SearchMaterialStates.query)
    
    if lang == "ru":
        
        await message.answer("🔎 Введите название товара для поиска:", reply_markup=cancel_kb("ru"))
    else:
        await message.answer("🔎 Qidirmoqchi bo'lgan mahsulot nomini kiriting:", reply_markup=cancel_kb())

@router.message(StateFilter(SearchMaterialStates.query))
async def inv_search_query(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    text = message.text.strip()
    
    # Agar bekor qilish tugmasi bosilsa
    if text.lower() in ("❌ bekor qilish", "bekor", "cancel", "❌ отмена", "отмена"):
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer("❌ Отменено.\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer("❌ Bekor qilindi.\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))
    
    if len(text) < 2:
        if lang == "ru":
            return await message.answer("❗ Поисковый запрос слишком короткий. Введите заново:")
        else:
            return await message.answer("❗ Qidiruv so'zi juda qisqa. Qaytadan kiriting:")
    
    try:
        materials = await search_materials(text)
        if not materials:
            # Avvalgi xulq-atvorga mos: menyuga qaytarmaymiz, foydalanuvchi yana yozsin
            if lang == "ru":
                return await message.answer("❌ Товары не найдены. Попробуйте другой поисковый запрос:")
            else:
                return await message.answer("❌ Hech qanday mahsulot topilmadi. Boshqa nom bilan qidiring:")
        
        if lang == "ru":
            result_text = f"🔎 Найденные товары по запросу '{text}':\n\n"
            for i, material in enumerate(materials, 1):
                result_text += f"{i}. <b>{material['name']}</b>\n"
                result_text += f"   📦 Количество: {material['quantity']}\n"
                result_text += f"   💰 Цена: {fmt_sum(material['price'])} сум\n\n"
        else:
            result_text = f"🔎 '{text}' bo'yicha topilgan mahsulotlar:\n\n"
            for i, material in enumerate(materials, 1):
                result_text += f"{i}. <b>{material['name']}</b>\n"
                result_text += f"   📦 Miqdor: {material['quantity']}\n"
                result_text += f"   💰 Narx: {fmt_sum(material['price'])} so'm\n\n"
        
        await message.answer(result_text, parse_mode="HTML")
        await state.set_state(WarehouseStates.inventory_menu)
        
        if lang == "ru":
            await message.answer("📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            await message.answer("📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))
        
    except Exception as e:
        if lang == "ru":
            await message.answer(f"❌ Ошибка: {e}")
            await state.set_state(WarehouseStates.inventory_menu)
            await message.answer("📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            await message.answer(f"❌ Xatolik: {e}")
            await state.set_state(WarehouseStates.inventory_menu)
            await message.answer("📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

# ============== ⚠️ Kam zaxira ==============

@router.message(StateFilter(WarehouseStates.inventory_menu), F.text.in_(["⚠️ Kam zaxira", "⚠️ Низкий запас"]))
async def inv_low_stock(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    
    try:
        materials = await get_low_stock_materials(10)  
        
        if not materials:
            if lang == "ru":
                return await message.answer("✅ Все товары в достаточном количестве.")
            else:
                return await message.answer("✅ Barcha mahsulotlar yetarli miqdorda mavjud.")
        
        if lang == "ru":
            text = "⚠️ <b>Товары с низким запасом (менее 10):</b>\n\n"
        else:
            text = "⚠️ <b>Kam zaxirali mahsulotlar (10 dan kam):</b>\n\n"
        
        for i, material in enumerate(materials, 1):
            if material['quantity'] == 0:
                status_icon = "🔴"  # Tugagan
            elif material['quantity'] <= 3:
                status_icon = "🟠"  # Juda kam
            elif material['quantity'] <= 7:
                status_icon = "🟡"  # Kam
            else:
                status_icon = "⚠️"  # Ogohlantirish
            
            if lang == "ru":
                text += f"{status_icon} <b>{i}. {material['name']}</b>\n"
                text += f"   📦 Количество: <b>{material['quantity']}</b>\n"
                text += f"   💰 Цена: {fmt_sum(material['price'])} сум\n"
                
                if material.get('description'):
                    text += f"   📝 Описание: {material['description'][:50]}{'...' if len(material['description']) > 50 else ''}\n"
            else:
                text += f"{status_icon} <b>{i}. {material['name']}</b>\n"
                text += f"   📦 Miqdor: <b>{material['quantity']}</b>\n"
                text += f"   💰 Narx: {fmt_sum(material['price'])} so'm\n"
                
                if material.get('description'):
                    text += f"   📝 Tavsif: {material['description'][:50]}{'...' if len(material['description']) > 50 else ''}\n"
            
            text += "\n"
        
        if lang == "ru":
            text += f"\n📊 <b>Всего:</b> {len(materials)} товаров с низким запасом\n"
            text += "\n💡 <i>Совет: Пополните эти товары как можно скорее!</i>"
        else:
            text += f"\n📊 <b>Jami:</b> {len(materials)} ta mahsulot kam zaxiraga ega\n"
            text += "\n💡 <i>Maslahat: Ushbu mahsulotlarni tezroq to'ldiring!</i>"
        
        await message.answer(text, parse_mode="HTML")
        
    except Exception as e:
        if lang == "ru":
            await message.answer(f"❌ Ошибка: {e}")
        else:
            await message.answer(f"❌ Xatolik: {e}")

# ============== ❌ Tugagan mahsulotlar ==============

@router.message(StateFilter(WarehouseStates.inventory_menu), F.text.in_(["❌ Tugagan mahsulotlar", "❌ Закончились"]))
async def inv_out_of_stock(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    
    try:
        materials = await get_out_of_stock_materials()
        if not materials:
            if lang == "ru":
                return await message.answer("✅ Ни один товар не закончился.")
            else:
                return await message.answer("✅ Hech qanday mahsulot tugamagan.")
        
        if lang == "ru":
            text = "❌ Закончившиеся товары:\n\n"
            for i, material in enumerate(materials, 1):
                text += f"{i}. <b>{material['name']}</b>\n"
                text += f"   💰 Цена: {fmt_sum(material['price'])} сум\n\n"
        else:
            text = "❌ Tugagan mahsulotlar:\n\n"
            for i, material in enumerate(materials, 1):
                text += f"{i}. <b>{material['name']}</b>\n"
                text += f"   💰 Narx: {fmt_sum(material['price'])} so'm\n\n"
        
        await message.answer(text, parse_mode="HTML")
        
    except Exception as e:
        if lang == "ru":
            await message.answer(f"❌ Ошибка: {e}")
        else:
            await message.answer(f"❌ Xatolik: {e}")

@router.message(StateFilter(UpdateMaterialStates.select))
async def inv_update_select(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    
    if message.text.strip().lower() in ("❌ bekor qilish", "bekor", "cancel", "❌ отмена", "отмена"):
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer("❌ Отменено.\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer("❌ Bekor qilindi.\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

    data = await state.get_data()
    materials = data.get('materials', [])
    
    selected_material = None
    text = message.text.strip()
    
    if text.startswith(tuple(f"{i}." for i in range(1, 11))):
        try:
            index = int(text.split('.')[0]) - 1
            if 0 <= index < len(materials):
                selected_material = materials[index]
        except (ValueError, IndexError):
            pass
    
    if not selected_material:
        if lang == "ru":
            return await message.answer("❗ Неверный выбор. Выберите один из списка:")
        else:
            return await message.answer("❗ Noto'g'ri tanlov. Ro'yxatdan birini tanlang:")
    
    await state.update_data(selected_material=selected_material)
    await state.set_state(UpdateMaterialStates.quantity)
    
    if lang == "ru":
        await message.answer(
            f"📦 Выбранный товар: <b>{selected_material['name']}</b>\n"
            f"📊 Текущее количество: <b>{selected_material['quantity']}</b> шт.\n\n"
            f"➕ Введите количество для добавления (только положительное число):",
            parse_mode="HTML",
            reply_markup=cancel_kb("ru")
        )
    else:
        await message.answer(
            f"📦 Tanlangan mahsulot: <b>{selected_material['name']}</b>\n"
            f"📊 Joriy miqdor: <b>{selected_material['quantity']}</b> dona\n\n"
            f"➕ Qo'shiladigan miqdorni kiriting (faqat musbat son):",
            parse_mode="HTML",
            reply_markup=cancel_kb()
        )

@router.message(StateFilter(UpdateMaterialStates.quantity))
async def inv_update_quantity(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    
    if message.text.strip().lower() in ("❌ bekor qilish", "bekor", "cancel", "❌ отмена", "отмена"):
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer("❌ Отменено.\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer("❌ Bekor qilindi.\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

    try:
        additional_quantity = int(message.text.strip())
        if additional_quantity <= 0:
            if lang == "ru":
                return await message.answer("❗ Введите только положительное число (больше 0):")
            else:
                return await message.answer("❗ Faqat musbat son kiriting (0 dan katta):")
    except ValueError:
        if lang == "ru":
            return await message.answer("❗ Неверный формат. Введите только число:")
        else:
            return await message.answer("❗ Noto'g'ri format. Faqat son kiriting:")

    data = await state.get_data()
    selected_material = data['selected_material']
    
    try:
        updated_material = await update_material_quantity(selected_material['id'], additional_quantity)
        
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            await message.answer(
                f"✅ Количество товара успешно обновлено!\n\n"
                f"📦 Товар: <b>{selected_material['name']}</b>\n"
                f"📊 Предыдущее количество: <b>{selected_material['quantity']}</b> шт.\n"
                f"➕ Добавлено: <b>{additional_quantity}</b> шт.\n"
                f"📊 Новое количество: <b>{updated_material['quantity']}</b> шт.\n\n"
                f"📦 Меню инвентаризации:",
                parse_mode="HTML",
                reply_markup=get_inventory_actions_keyboard("ru")
            )
        else:
            await message.answer(
                f"✅ Mahsulot miqdori muvaffaqiyatli yangilandi!\n\n"
                f"📦 Mahsulot: <b>{selected_material['name']}</b>\n"
                f"📊 Avvalgi miqdor: <b>{selected_material['quantity']}</b> dona\n"
                f"➕ Qo'shilgan: <b>{additional_quantity}</b> dona\n"
                f"📊 Yangi miqdor: <b>{updated_material['quantity']}</b> dona\n\n"
                f"📦 Inventarizatsiya menyusi:",
                parse_mode="HTML",
                reply_markup=get_inventory_actions_keyboard("uz")
            )
    except Exception as e:
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            await message.answer(
                f"❌ Произошла ошибка: {str(e)}\n\n📦 Меню инвентаризации:",
                reply_markup=get_inventory_actions_keyboard("ru")
            )
        else:
            await message.answer(
                f"❌ Xatolik yuz berdi: {str(e)}\n\n📦 Inventarizatsiya menyusi:",
                reply_markup=get_inventory_actions_keyboard("uz")
            )

@router.message(StateFilter(UpdateMaterialStates.name))
async def inv_update_name(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    
    if message.text.strip().lower() in ("❌ bekor qilish", "bekor", "cancel", "❌ отмена", "отмена"):
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer("❌ Отменено.\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer("❌ Bekor qilindi.\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

    new_name = message.text.strip()
    if len(new_name) < 2:
        if lang == "ru":
            return await message.answer("❗ Название товара слишком короткое. Введите заново:")
        else:
            return await message.answer("❗ Mahsulot nomi juda qisqa. Qayta kiriting:")

    await state.update_data(new_name=new_name)
    await state.set_state(UpdateMaterialStates.description)
    
    data = await state.get_data()
    selected_material = data['selected_material']
    
    if lang == "ru":
        await message.answer(
            f"✏️ Новое название: <b>{new_name}</b>\n\n"
            f"📝 Текущее описание: <b>{selected_material.get('description', 'Описание отсутствует')}</b>\n\n"
            f"📝 Введите новое описание (или напишите 'пропустить'):",
            parse_mode="HTML",
            reply_markup=cancel_kb("ru")
        )
    else:
        skip_text = "o'tkazib yuborish"
        no_description = "Tavsif yo'q"
        await message.answer(
            f"✏️ Yangi nom: <b>{new_name}</b>\n\n"
            f"📝 Joriy tavsif: <b>{selected_material.get('description', no_description)}</b>\n\n"
            f"📝 Yangi tavsif kiriting (yoki '{skip_text}' deb yozing):",
            parse_mode="HTML",
            reply_markup=cancel_kb()
        )

@router.message(StateFilter(UpdateMaterialStates.description))
async def inv_update_description(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    
    if message.text.strip().lower() in ("❌ bekor qilish", "bekor", "cancel", "❌ отмена", "отмена"):
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer("❌ Отменено.\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer("❌ Bekor qilindi.\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))

    new_description = message.text.strip()
    if new_description.lower() in ("o'tkazib yuborish", "otkazib yuborish", "skip", "-", "пропустить", "пропустить"):
        new_description = None

    data = await state.get_data()
    selected_material = data['selected_material']
    new_name = data['new_name']
    
    try:
        updated_material = await update_material_name_description(selected_material['id'], new_name, new_description)
        
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            await message.answer(
                "✅ Информация о товаре успешно обновлена!\n"
                f"🏷️ Старое название: <b>{selected_material['name']}</b>\n"
                f"🏷️ Новое название: <b>{updated_material['name']}</b>\n"
                f"📝 Старое описание: <b>{selected_material.get('description', 'Описание отсутствует')}</b>\n"
                f"📝 Новое описание: <b>{updated_material.get('description', 'Описание отсутствует')}</b>\n\n"
                "📦 Меню инвентаризации:",
                parse_mode="HTML",
                reply_markup=get_inventory_actions_keyboard("ru")
            )
        else:
            no_description = "Tavsif yo'q"
            await message.answer(
                "✅ Mahsulot ma'lumotlari muvaffaqiyatli yangilandi!\n"
                f"🏷️ Eski nom: <b>{selected_material['name']}</b>\n"
                f"🏷️ Yangi nom: <b>{updated_material['name']}</b>\n"
                f"📝 Eski tavsif: <b>{selected_material.get('description', no_description)}</b>\n"
                f"📝 Yangi tavsif: <b>{updated_material.get('description', no_description)}</b>\n\n"
                "📦 Inventarizatsiya menyusi:",
                parse_mode="HTML",
                reply_markup=get_inventory_actions_keyboard("uz")
            )
        
    except Exception as e:
        await state.set_state(WarehouseStates.inventory_menu)
        if lang == "ru":
            return await message.answer(f"❌ Ошибка: {e}\n\n📦 Меню инвентаризации:", reply_markup=get_inventory_actions_keyboard("ru"))
        else:
            return await message.answer(f"❌ Xatolik: {e}\n\n📦 Inventarizatsiya menyusi:", reply_markup=get_inventory_actions_keyboard("uz"))
