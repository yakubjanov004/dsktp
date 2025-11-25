from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import logging

from database.warehouse.users import get_users_by_role
from database.technician.materials import fetch_technician_materials
from database.basic.user import find_user_by_telegram_id, get_user_by_id
from database.basic.language import get_user_language
from keyboards.warehouse_buttons import get_warehouse_main_menu
from filters.role_filter import RoleFilter

router = Router()
logger = logging.getLogger(__name__)

@router.message(RoleFilter("warehouse"), F.text.in_(["📦🔎 Teknikda qolgan mat.", "📦🔎 Остаток мат. у техника"]))
async def technician_material_balance_menu(message: Message, state: FSMContext):
    """Texniklarning material qoldiqlari menyusi / Меню остатков материалов у техников"""
    lang = await get_user_language(message.from_user.id) or "uz"
    
    # Barcha texniklarni olish
    technicians = await get_users_by_role("technician")
    
    if not technicians:
        if lang == "ru":
            await message.answer(
                "❌ В системе сейчас нет технических сотрудников.",
                reply_markup=get_warehouse_main_menu("ru")
            )
        else:
            await message.answer(
                "❌ Hozirda tizimda texnik xodimlar mavjud emas.",
                reply_markup=get_warehouse_main_menu("uz")
            )
        return
    
    # State ga barcha texniklarni saqlash
    await state.update_data(all_technicians=technicians)
    
    # Paginatsiya uchun boshlang'ich konfiguratsiya
    await state.update_data(current_page=0, page_size=5)
    
    # Birinchi sahifani ko'rsatish
    await show_technicians_page(message, state, lang)

async def show_technicians_page(message: Message, state: FSMContext, lang: str, callback: CallbackQuery = None):
    """Texniklarni sahifalab ko'rsatish / Отображение техников постранично"""
    data = await state.get_data()
    technicians = data.get('all_technicians', [])
    current_page = data.get('current_page', 0)
    page_size = data.get('page_size', 5)
    
    total_pages = (len(technicians) + page_size - 1) // page_size
    
    if current_page >= total_pages:
        current_page = total_pages - 1
    
    start_index = current_page * page_size
    end_index = min(start_index + page_size, len(technicians))
    current_technicians = technicians[start_index:end_index]
    
    # Xabarni tayyorlash
    message_text = (
        f"👨‍🔧 **Texnik xodimlarning material qoldiqlari**\n"
        f"Sahifa {current_page + 1}/{total_pages}\n\n"
        if lang == "uz" else
        f"👨‍🔧 **Остатки материалов у технических сотрудников**\n"
        f"Страница {current_page + 1}/{total_pages}\n\n"
    )
    
    if not current_technicians:
        message_text += ("❌ Texnik xodimlar topilmadi." if lang == "uz" else "❌ Техники не найдены.")
    else:
        for i, tech in enumerate(current_technicians, start=start_index + 1):
            full_name = (tech.get('full_name') or '').strip() or f"ID: {tech['id']}"
            message_text += f"{i}. {full_name}\n"
    
    # Keyboard yaratish
    keyboard = []
    
    # Texnik tanlash tugmalari
    for tech in current_technicians:
        full_name = (tech.get('full_name') or '').strip() or f"ID: {tech['id']}"
        keyboard.append([
            InlineKeyboardButton(
                text=f"👨‍🔧 {full_name}",
                callback_data=f"balance_tech_{tech['id']}"
            )
        ])
    
    # Navigatsiya tugmalari
    nav_row = []
    if current_page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️",
            callback_data=f"balance_page_{current_page - 1}"
        ))
    
    nav_row.append(InlineKeyboardButton(
        text=f"{current_page + 1}/{total_pages}",
        callback_data="balance_page_info"
    ))
    
    if current_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️",
            callback_data=f"balance_page_{current_page + 1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Orqaga tugmasi
    keyboard.append([
        InlineKeyboardButton(
            text=("❌ Yopish" if lang == "uz" else "❌ Закрыть"),
            callback_data="balance_back_to_menu"
        )
    ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    if callback:
        # Callback query orqali kelgan bo'lsa, xabarni tahrirlaymiz
        try:
            await callback.message.edit_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
        except:
            # Agar tahrirlab bo'lmasa, yangi xabar yuboramiz
            await callback.message.answer(message_text, reply_markup=reply_markup, parse_mode="Markdown")
        await callback.answer()
    else:
        # Oddiy xabar orqali kelgan bo'lsa, yangi xabar yuboramiz
        await message.answer(message_text, reply_markup=reply_markup, parse_mode="Markdown")

@router.callback_query(F.data.startswith("balance_page_"))
async def change_balance_page(callback: CallbackQuery, state: FSMContext):
    """Sahifani o'zgartirish / Смена страницы"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    try:
        new_page = int(callback.data.split("_")[-1])
        await state.update_data(current_page=new_page)
        await show_technicians_page(callback.message, state, lang, callback)
    except (ValueError, IndexError):
        await callback.answer(("❌ Xatolik yuz berdi!" if lang == "uz" else "❌ Произошла ошибка!"), show_alert=True)

@router.callback_query(F.data.startswith("balance_tech_"))
async def show_technician_balance(callback: CallbackQuery, state: FSMContext):
    """Tanlangan texnikning material qoldiqlarini ko'rsatish / Показать остатки материалов выбранного техника"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    tech_id = int(callback.data.split("_")[-1])
    
    # Texnik ma'lumotlarini olish
    technician = await get_user_by_id(tech_id)
    if not technician:
        await callback.answer(("❌ Texnik topilmadi!" if lang == "uz" else "❌ Техник не найден!"), show_alert=True)
        return
    
    # Texnikning materiallarini olish
    tech_materials = await fetch_technician_materials(tech_id)
    
    full_name = (technician.get('full_name') or '').strip() or f"ID: {tech_id}"
    
    message_text = (
        f"👨‍🔧 **{full_name}** texnikining material qoldiqlari:\n\n"
        if lang == "uz" else
        f"👨‍🔧 **{full_name}** — остатки материалов у техника:\n\n"
    )
    
    if tech_materials:
        total_value = 0
        for material in tech_materials:
            price = material.get('price', 0) or 0
            quantity = material.get('stock_quantity', 0) or 0
            material_value = price * quantity
            total_value += material_value
            
            message_text += (
                f"📦 **{material['name']}**\n"
                f"   • Miqdor: {material['stock_quantity']} dona\n"
                f"   • Narxi: {price:,} so'm\n"
                f"   • Qiymati: {material_value:,} so'm\n\n"
                if lang == "uz" else
                f"📦 **{material['name']}**\n"
                f"   • Количество: {material['stock_quantity']} шт.\n"
                f"   • Цена: {price:,} сум\n"
                f"   • Стоимость: {material_value:,} сум\n\n"
            )
        
        message_text += (
            f"💰 **Jami qiymati: {total_value:,} so'm**\n"
            if lang == "uz" else
            f"💰 **Общая стоимость: {total_value:,} сум**\n"
        )
    else:
        message_text += ("📦 Hozirda texnikda materiallar mavjud emas.\n"
                         if lang == "uz" else
                         "📦 У техника сейчас нет материалов.\n")
    
    # Orqaga tugmalari
    keyboard = [
        [
            InlineKeyboardButton(
                text=("◀️ Orqaga" if lang == "uz" else "◀️ Назад"),
                callback_data="balance_back_to_list"
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "balance_back_to_list")
async def back_to_technicians_list(callback: CallbackQuery, state: FSMContext):
    """Texniklar ro'yxatiga qaytish / Вернуться к списку техников"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    await show_technicians_page(callback.message, state, lang, callback)

@router.callback_query(F.data == "balance_back_to_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Asosiy menyuga qaytish / Вернуться в главное меню"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    await state.clear()
    
    try:
        await callback.message.delete()
    except:
        pass  # Xabarni o'chirish muvaffaqiyatsiz bo'lsa, e'tiborsiz qoldiramiz
    
    await callback.message.answer(
        ("🏠 Asosiy menyu:" if lang == "uz" else "🏠 Главное меню:"),
        reply_markup=get_warehouse_main_menu(lang)
    )
    await callback.answer()

@router.callback_query(F.data == "balance_page_info")
async def balance_page_info(callback: CallbackQuery):
    """Sahifa ma'lumoti / Информация о странице"""
    await callback.answer()
