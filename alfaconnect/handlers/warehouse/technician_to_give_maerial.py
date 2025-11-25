from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import logging

from database.warehouse.materials import get_all_materials, search_materials, get_material_by_id
from database.technician.materials import fetch_technician_materials, fetch_assigned_qty
from database.basic.user import find_user_by_telegram_id, get_user_by_id
from database.warehouse.users import get_users_by_role
from keyboards.warehouse_buttons import get_warehouse_main_menu
from filters.role_filter import RoleFilter
from states.warehouse_states import TechnicianMaterialStates
from database.basic.language import get_user_language

router = Router()
logger = logging.getLogger(__name__)

@router.message(RoleFilter("warehouse"), F.text.in_(["📦 Teknik xodimga mahsulot berish", "📦 Отдать материал технику"]))
async def technician_material_menu(message: Message, state: FSMContext):
    """Texnikka material berish menyusi / Меню выдачи материала технику"""
    lang = await get_user_language(message.from_user.id) or "uz"
    await state.set_state(TechnicianMaterialStates.select_technician)
    
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
        await state.clear()
        return
    
    # Texniklarni inline keyboard qilish
    keyboard = []
    for tech in technicians:
        full_name = (tech.get('full_name') or '').strip()
        keyboard.append([
            InlineKeyboardButton(
                text=f"👨‍🔧 {full_name}",
                callback_data=f"select_tech_{tech['id']}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text=("◀️ Orqaga" if lang == "uz" else "◀️ Назад"),
            callback_data="back_to_warehouse_menu"
        )
    ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    if lang == "ru":
        await message.answer(
            "👨‍🔧 Кому из техников выдать материал?\n\nВыберите технического сотрудника:",
            reply_markup=reply_markup
        )
    else:
        await message.answer(
            "👨‍🔧 Qaysi texnik xodimga material berishni xohlaysiz?\n\nTexnik xodimni tanlang:",
            reply_markup=reply_markup
        )

@router.callback_query(F.data.startswith("select_tech_"))
async def select_technician(callback: CallbackQuery, state: FSMContext):
    """Texnikni tanlash / Выбор техника"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    tech_id = int(callback.data.split("_")[-1])
    
    # Texnik ma'lumotlarini olish
    technician = await get_user_by_id(tech_id)
    if not technician:
        await callback.answer(("❌ Texnik topilmadi!" if lang == "uz" else "❌ Техник не найден!"), show_alert=True)
        return
    
    # State ga texnik ID sini saqlash
    await state.update_data(technician_id=tech_id)
    await state.set_state(TechnicianMaterialStates.select_material)
    
    # Texnikning mavjud materiallarini ko'rsatish
    tech_materials = await fetch_technician_materials(tech_id)
    
    full_name = (technician.get('full_name') or '').strip() or f"ID: {tech_id}"
    
    message_text = (
        f"👨‍🔧 **{full_name}** texnikining mavjud materiallari:\n\n"
        if lang == "uz" else
        f"👨‍🔧 **{full_name}** — материалы у техника:\n\n"
    )
    
    if tech_materials:
        message_text += ("📦 **Mavjud materiallar:**\n" if lang == "uz" else "📦 **Имеющиеся материалы:**\n")
        for material in tech_materials:
            message_text += (
                f"• {material['name']} - {material['stock_quantity']} dona\n"
                if lang == "uz" else
                f"• {material['name']} — {material['stock_quantity']} шт.\n"
            )
    else:
        message_text += ("📦 Hozirda texnikda materiallar mavjud emas.\n"
                         if lang == "uz" else
                         "📦 У техника сейчас нет материалов.\n")
    
    message_text += ("\n🔍 Qo'shish uchun material tanlang:" if lang == "uz" else "\n🔍 Выберите материал для выдачи:")
    
    # Ombordagi barcha materiallarni ko'rsatish
    warehouse_materials = await get_all_materials()
    
    if not warehouse_materials:
        await callback.message.edit_text(
            message_text + ("\n\n❌ Omborda materiallar mavjud emas." if lang == "uz" else "\n\n❌ На складе нет материалов."),
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    # Materiallarni inline keyboard qilish
    keyboard = []
    for material in warehouse_materials:
        if material['quantity'] > 0:  # Faqat mavjud materiallar
            keyboard.append([
                InlineKeyboardButton(
                    text=(
                        f"📦 {material['name']} ({material['quantity']} dona)"
                        if lang == "uz" else
                        f"📦 {material['name']} ({material['quantity']} шт.)"
                    ),
                    callback_data=f"select_material_{material['id']}"
                )
            ])
    
    if not keyboard:
        await callback.message.edit_text(
            message_text + ("\n\n❌ Omborda mavjud materiallar yo'q." if lang == "uz" else "\n\n❌ На складе нет доступных материалов."),
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    keyboard.append([
        InlineKeyboardButton(
            text=("◀️ Orqaga" if lang == "uz" else "◀️ Назад"),
            callback_data="back_to_tech_selection"
        )
    ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("select_material_"))
async def select_material(callback: CallbackQuery, state: FSMContext):
    """Materialni tanlash / Выбор материала"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    material_id = int(callback.data.split("_")[-1])
    
    # Material ma'lumotlarini olish
    material = await get_material_by_id(material_id)
    if not material:
        await callback.answer(("❌ Material topilmadi!" if lang == "uz" else "❌ Материал не найден!"), show_alert=True)
        return
    
    if material['quantity'] <= 0:
        await callback.answer(("❌ Bu material omborda mavjud emas!" if lang == "uz" else "❌ Этого материала нет на складе!"), show_alert=True)
        return
    
    # State ga material ID sini saqlash
    await state.update_data(material_id=material_id)
    await state.set_state(TechnicianMaterialStates.enter_quantity)
    
    # State dan texnik ID sini olish
    data = await state.get_data()
    tech_id = data.get('technician_id')
    
    # Texnikning bu materialdagi mavjud miqdorini olish
    current_qty = await fetch_assigned_qty(tech_id, material_id)
    
    await callback.message.edit_text(
        (
            f"📦 **{material['name']}**\n\n"
            f"💰 Narxi: {material.get('price', 'Belgilanmagan')}\n"
            f"📊 Omborda mavjud: {material['quantity']} dona\n"
            f"👨‍🔧 Texnikda mavjud: {current_qty} dona\n\n"
            f"❓ Texnikka necha dona bermoqchisiz?\n"
            f"(1 dan {material['quantity']} gacha raqam kiriting)"
        ) if lang == "uz" else
        (
            f"📦 **{material['name']}**\n\n"
            f"💰 Цена: {material.get('price', 'Не указана')}\n"
            f"📊 На складе: {material['quantity']} шт.\n"
            f"👨‍🔧 У техника: {current_qty} шт.\n\n"
            f"❓ Сколько штук выдать технику?\n"
            f"(Введите число от 1 до {material['quantity']})"
        ),
        parse_mode="Markdown"
    )

@router.message(TechnicianMaterialStates.enter_quantity)
async def enter_quantity(message: Message, state: FSMContext):
    """Miqdorni kiritish / Ввод количества"""
    lang = await get_user_language(message.from_user.id) or "uz"
    try:
        quantity = int((message.text or "").strip())
    except ValueError:
        await message.answer(("❌ Iltimos, faqat raqam kiriting!" if lang == "uz" else "❌ Пожалуйста, введите только число!"))
        return
    
    if quantity <= 0:
        await message.answer(("❌ Miqdor 0 dan katta bo'lishi kerak!" if lang == "uz" else "❌ Количество должно быть больше 0!"))
        return
    
    # State dan ma'lumotlarni olish
    data = await state.get_data()
    tech_id = data.get('technician_id')
    material_id = data.get('material_id')
    
    # Material ma'lumotlarini tekshirish
    material = await get_material_by_id(material_id)
    if not material or material['quantity'] < quantity:
        await message.answer(
            (
                f"❌ Omborda yetarli material yo'q!\nMavjud: {material['quantity'] if material else 0} dona"
            ) if lang == "uz" else
            (
                f"❌ Недостаточно материала на складе!\nДоступно: {material['quantity'] if material else 0} шт."
            )
        )
        return
    
    # Texnik ma'lumotlarini olish
    technician = await get_user_by_id(tech_id)
    full_name = (technician.get('full_name') or '').strip() or f"ID: {tech_id}"
    
    # Tasdiqlash uchun keyboard
    keyboard = [
        [
            InlineKeyboardButton(
                text=("✅ Tasdiqlash" if lang == "uz" else "✅ Подтвердить"),
                callback_data=f"confirm_assign_{tech_id}_{material_id}_{quantity}"
            ),
            InlineKeyboardButton(
                text=("❌ Bekor qilish" if lang == "uz" else "❌ Отмена"),
                callback_data="cancel_assign"
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        (
            f"📋 **Tasdiqlash**\n\n"
            f"👨‍🔧 Texnik: {full_name}\n"
            f"📦 Material: {material['name']}\n"
            f"📊 Miqdor: {quantity} dona\n\n"
            f"❓ Materialni texnikka berishni tasdiqlaysizmi?"
        ) if lang == "uz" else
        (
            f"📋 **Подтверждение**\n\n"
            f"👨‍🔧 Техник: {full_name}\n"
            f"📦 Материал: {material['name']}\n"
            f"📊 Количество: {quantity} шт.\n\n"
            f"❓ Подтвердить выдачу материала технику?"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("confirm_assign_"))
async def confirm_assignment(callback: CallbackQuery, state: FSMContext):
    """Material berishni tasdiqlash / Подтверждение выдачи"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    try:
        parts = callback.data.split("_")
        tech_id = int(parts[2])
        material_id = int(parts[3])
        quantity = int(parts[4])
        
        # Material va texnik ma'lumotlarini olish
        material = await get_material_by_id(material_id)
        technician = await get_user_by_id(tech_id)
        
        if not material or not technician:
            await callback.answer(("❌ Ma'lumotlar topilmadi!" if lang == "uz" else "❌ Данные не найдены!"), show_alert=True)
            return
        
        if material['quantity'] < quantity:
            await callback.answer(("❌ Omborda yetarli material yo'q!" if lang == "uz" else "❌ На складе недостаточно материала!"), show_alert=True)
            return
        
        # Material berishni amalga oshirish
        import asyncpg
        from config import settings
        
        conn = await asyncpg.connect(settings.DB_URL)
        try:
            async with conn.transaction():
                # Ombordagi materialni kamaytirish
                await conn.execute(
                    "UPDATE materials SET quantity = quantity - $1 WHERE id = $2",
                    quantity, material_id
                )
                
                # Texnikka material berish (material_and_technician jadvaliga qo'shish)
                # First check if record exists
                existing_record = await conn.fetchrow(
                    "SELECT id, quantity FROM material_and_technician WHERE user_id = $1 AND material_id = $2",
                    tech_id, material_id
                )
                
                if existing_record:
                    # Update existing record
                    await conn.execute(
                        "UPDATE material_and_technician SET quantity = quantity + $1 WHERE id = $2",
                        quantity, existing_record['id']
                    )
                else:
                    # Insert new record
                    await conn.execute(
                        "INSERT INTO material_and_technician (user_id, material_id, quantity) VALUES ($1, $2, $3)",
                        tech_id, material_id, quantity
                    )
        except asyncpg.UniqueViolationError as e:
            # Handle unique constraint violation
            await callback.answer(
                ("❌ Bu material allaqachon texnikka berilgan!" if lang == "uz" else "❌ Этот материал уже выдан технику!"), 
                show_alert=True
            )
            return
        except Exception as db_error:
            # Handle other database errors
            await callback.answer(
                (f"❌ Ma'lumotlar bazasi xatosi: {str(db_error)}" if lang == "uz" else f"❌ Ошибка базы данных: {str(db_error)}"), 
                show_alert=True
            )
            return
        finally:
            await conn.close()
        
        full_name = (technician.get('full_name') or '').strip() or f"ID: {tech_id}"
        
        await callback.message.edit_text(
            (
                f"✅ **Muvaffaqiyatli bajarildi!**\n\n"
                f"👨‍🔧 Texnik: {full_name}\n"
                f"📦 Material: {material['name']}\n"
                f"📊 Berilgan miqdor: {quantity} dona\n\n"
                f"Material texnikka muvaffaqiyatli berildi!"
            ) if lang == "uz" else
            (
                f"✅ **Успешно!**\n\n"
                f"👨‍🔧 Техник: {full_name}\n"
                f"📦 Материал: {material['name']}\n"
                f"📊 Выдано: {quantity} шт.\n\n"
                f"Материал успешно выдан технику!"
            ),
            parse_mode="Markdown"
        )
        
        await state.clear()
        
        # Asosiy menyuga qaytish
        await callback.message.answer(
            ("🏠 Asosiy menyu:" if lang == "uz" else "🏠 Главное меню:"),
            reply_markup=get_warehouse_main_menu(lang)
        )
        
    except Exception as e:
        await callback.answer(
            (f"❌ Xatolik yuz berdi: {str(e)}" if lang == "uz" else f"❌ Произошла ошибка: {str(e)}"),
            show_alert=True
        )
        await state.clear()

@router.callback_query(F.data == "cancel_assign")
async def cancel_assignment(callback: CallbackQuery, state: FSMContext):
    """Material berishni bekor qilish / Отмена выдачи"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    await callback.message.edit_text(
        ("❌ Material berish bekor qilindi." if lang == "uz" else "❌ Выдача материала отменена.")
    )
    await state.clear()
    
    await callback.message.answer(
        ("🏠 Asosiy menyu:" if lang == "uz" else "🏠 Главное меню:"),
        reply_markup=get_warehouse_main_menu(lang)
    )

@router.callback_query(F.data == "back_to_warehouse_menu")
async def back_to_warehouse_menu(callback: CallbackQuery, state: FSMContext):
    """Warehouse menyusiga qaytish / Возврат в меню склада"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    await callback.message.delete()
    await state.clear()
    
    await callback.message.answer(
        ("🏠 Asosiy menyu:" if lang == "uz" else "🏠 Главное меню:"),
        reply_markup=get_warehouse_main_menu(lang)
    )

@router.callback_query(F.data == "back_to_tech_selection")
async def back_to_tech_selection(callback: CallbackQuery, state: FSMContext):
    """Texnik tanlashga qaytish / Вернуться к выбору техника"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    await state.set_state(TechnicianMaterialStates.select_technician)
    
    # Barcha texniklarni olish
    technicians = await get_users_by_role("technician")
    
    if not technicians:
        await callback.message.edit_text(
            ("❌ Hozirda tizimda texnik xodimlar mavjud emas." if lang == "uz" else "❌ В системе сейчас нет технических сотрудников.")
        )
        await state.clear()
        return
    
    # Texniklarni inline keyboard qilish
    keyboard = []
    for tech in technicians:
        full_name = (tech.get('full_name') or '').strip() or f"ID: {tech['id']}"
        keyboard.append([
            InlineKeyboardButton(
                text=f"👨‍🔧 {full_name}",
                callback_data=f"select_tech_{tech['id']}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text=("◀️ Orqaga" if lang == "uz" else "◀️ Назад"),
            callback_data="back_to_warehouse_menu"
        )
    ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        ("👨‍🔧 Qaysi texnik xodimga material berishni xohlaysiz?\n\nTexnik xodimni tanlang:"
         if lang == "uz" else
         "👨‍🔧 Кому из техников выдать материал?\n\nВыберите технического сотрудника:"),
        reply_markup=reply_markup
    )
