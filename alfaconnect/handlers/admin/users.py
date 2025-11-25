from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
import asyncpg
import re
import logging
from config import settings
from typing import Optional
from filters.role_filter import RoleFilter
from database.basic.user import (
    find_user_by_telegram_id,
    find_user_by_phone,
    update_user_role
)
from database.admin.users import (
    get_all_users_paginated,
    get_users_by_role_paginated,
    search_users_paginated,
    toggle_user_block_status
)
from datetime import datetime
from keyboards.admin_buttons import (
    get_user_management_keyboard,
    get_inline_role_selection,
    get_inline_search_method,
    get_admin_main_menu
)
from database.basic.language import get_user_language

router = Router()
router.message.filter(RoleFilter("admin")) 
class UserRoleChange(StatesGroup):
    waiting_for_search_method = State()
    waiting_for_telegram_id = State()
    waiting_for_phone = State()
    waiting_for_new_role = State()

class UsersPagination(StatesGroup):
    viewing_all_users = State()
    viewing_staff_users = State()

class UserBlockManagement(StatesGroup):
    waiting_for_user_search = State()


ROLE_MAPPING = {
    'role_admin': 'admin',
    'role_client': 'client',
    'role_manager': 'manager',
    'role_junior_manager': 'junior_manager',
    'role_controller': 'controller',
    'role_technician': 'technician',
    'role_warehouse': 'warehouse',
    'role_callcenter_operator': 'callcenter_operator',
    'role_callcenter_supervisor': 'callcenter_supervisor'
}

@router.message(F.text.in_( ["👥 Foydalanuvchilar", "👥 Пользователи"]))
async def users_handler(message: Message):
    lang = await get_user_language(message.from_user.id) or "uz"
    await message.answer(
        ("👥 Foydalanuvchilar boshqaruvi" if lang == "uz" else "👥 Управление пользователями"),
        reply_markup=get_user_management_keyboard(lang)
    )


@router.message(F.text.in_(["👥 Barcha foydalanuvchilar", "👥 Все пользователи"]))
async def all_users_handler(message: Message, state: FSMContext):
    """Faqat client foydalanuvchilarni ko'rsatish (paginatsiya bilan)"""
    await state.set_state(UsersPagination.viewing_all_users)
    await show_users_page(message, state, page=1, user_type="client")


@router.message(F.text.in_(["👤 Xodimlar", "👤 Сотрудники"]))
async def staff_handler(message: Message, state: FSMContext):
    """Xodimlarni ko'rsatish (client bo'lmagan foydalanuvchilar)"""
    await state.set_state(UsersPagination.viewing_staff_users)
    await show_users_page(message, state, page=1, user_type="staff")


@router.message(F.text.in_(["🔒 Bloklash/Blokdan chiqarish", "🔒 Блокировка/Разблокировка"]))
async def block_user_handler(message: Message, state: FSMContext):
    await state.set_state(UserBlockManagement.waiting_for_user_search)
    lang = await get_user_language(message.from_user.id) or "uz"
    await message.answer(
        (
            "🔒 <b>Foydalanuvchini bloklash/blokdan chiqarish</b>\n\n"
            "Quyidagi usullardan birini tanlang:\n\n"
            "📱 <b>Telefon raqam</b> - masalan: +998901234567\n"
            "🆔 <b>Telegram ID</b> - masalan: 123456789\n"
            "👤 <b>Username</b> - masalan: @username\n\n"
            "❌ Bekor qilish uchun /cancel yozing"
        ) if lang == "uz" else (
            "🔒 <b>Блокировка/разблокировка пользователя</b>\n\n"
            "Выберите один из способов:\n\n"
            "📱 <b>Телефон</b> - например: +998901234567\n"
            "🆔 <b>Telegram ID</b> - например: 123456789\n"
            "👤 <b>Username</b> - например: @username\n\n"
            "❌ Для отмены введите /cancel"
        ),
        parse_mode='HTML'
    )


@router.message(UserBlockManagement.waiting_for_user_search)
async def process_user_search_for_block(message: Message, state: FSMContext):
    search_text = message.text.strip()
    lang = await get_user_language(message.from_user.id) or "uz"
    
    if search_text.lower() in ['/cancel', 'bekor qilish', 'cancel']:
        await state.clear()
        await message.answer(("❌ Bloklash jarayoni bekor qilindi." if lang == "uz" else "❌ Процесс блокировки отменен."), parse_mode='HTML')
        return
    
    user = None
    
    # Telegram ID bo'yicha qidirish (faqat raqamlar)
    if search_text.isdigit() and not search_text.startswith('+'):
        telegram_id = int(search_text)
        user = await find_user_by_telegram_id(telegram_id)
    
    # Telefon raqam bo'yicha qidirish
    elif search_text.startswith('+') or (search_text.replace(' ', '').isdigit() and len(search_text.replace(' ', '')) >= 9):
        clean_phone = search_text.replace(' ', '').replace('-', '')
        user = await find_user_by_phone(clean_phone)
    
    # Username bo'yicha qidirish
    elif search_text.startswith('@'):
        username = search_text[1:]  # @ belgisini olib tashlash
        conn = await asyncpg.connect(settings.DB_URL)
        try:
            user_data = await conn.fetchrow(
                "SELECT * FROM users WHERE username = $1", username
            )
            if user_data:
                user = dict(user_data)
        finally:
            await conn.close()
    
    if not user:
        await message.answer(
            (
                "❌ Foydalanuvchi topilmadi!\n\n"
                "Iltimos, to'g'ri ma'lumot kiriting:\n"
                "📱 Telefon: +998901234567\n"
                "🆔 Telegram ID: 123456789\n"
                "👤 Username: @username"
            ) if lang == "uz" else (
                "❌ Пользователь не найден!\n\n"
                "Пожалуйста, введите корректные данные:\n"
                "📱 Телефон: +998901234567\n"
                "🆔 Telegram ID: 123456789\n"
                "👤 Username: @username"
            ),
            parse_mode='HTML'
        )
        return
    
    # Foydalanuvchi ma'lumotlarini ko'rsatish va bloklash/blokdan chiqarish
    block_status = ("🔴 Bloklangan" if lang == "uz" else "🔴 Заблокирован") if user.get('is_blocked') else ("🟢 Faol" if lang == "uz" else "🟢 Активен")
    action_text = ("blokdan chiqarish" if lang == "uz" else "разблокировать") if user.get('is_blocked') else ("bloklash" if lang == "uz" else "заблокировать")
    action_emoji = "🔓" if user.get('is_blocked') else "🔒"
    
    user_info = ("👤 <b>Topilgan foydalanuvchi:</b>\n\n" if lang == "uz" else "👤 <b>Найденный пользователь:</b>\n\n")
    unknown_name = "Noma'lum" if lang == "uz" else "Неизвестно"
    unknown_phone = "Noma'lum" if lang == "uz" else "Неизвестно"
    user_info += (f"📝 <b>Ism:</b> {user.get('full_name', unknown_name)}\n" if lang == "uz" else f"📝 <b>Имя:</b> {user.get('full_name', unknown_name)}\n")
    user_info += f"🆔 <b>Telegram ID:</b> <code>{user.get('telegram_id')}</code>\n"
    user_info += (f"📱 <b>Telefon:</b> {user.get('phone', unknown_phone)}\n" if lang == "uz" else f"📱 <b>Телефон:</b> {user.get('phone', unknown_phone)}\n")
    if user.get('username'):
        user_info += f"👤 <b>Username:</b> @{user.get('username')}\n"
    user_info += ((f"🎭 <b>Rol:</b> {user.get('role', 'client')}\n") if lang == "uz" else (f"🎭 <b>Роль:</b> {user.get('role', 'client')}\n"))
    user_info += ((f"📊 <b>Holat:</b> {block_status}\n\n") if lang == "uz" else (f"📊 <b>Статус:</b> {block_status}\n\n"))
    
    # Bloklash/blokdan chiqarish
    success = await toggle_user_block_status(user['id'])
    
    if success:
        new_status = ("🔴 Bloklangan" if lang == "uz" else "🔴 Заблокирован") if not user.get('is_blocked') else ("🟢 Faol" if lang == "uz" else "🟢 Активен")
        user_info += ((f"✅ <b>Muvaffaqiyatli {action_text} qilindi!</b>\n") if lang == "uz" else (f"✅ <b>Успешно выполнено: {action_text}!</b>\n"))
        user_info += ((f"📊 <b>Yangi holat:</b> {new_status}") if lang == "uz" else (f"📊 <b>Новый статус:</b> {new_status}"))
    else:
        user_info += ("❌ <b>Xatolik yuz berdi!</b>\n" if lang == "uz" else "❌ <b>Произошла ошибка!</b>\n")
        user_info += ((f"Foydalanuvchini {action_text} qilib bo'lmadi.") if lang == "uz" else (f"Не удалось {action_text} пользователя."))
    
    await state.clear()
    await message.answer(user_info, parse_mode='HTML')

@router.message(F.text == "🔄 Rolni o'zgartirish")
async def change_user_role(message: Message, state: FSMContext):
    """Start the role change process by asking for search method"""
    lang = await get_user_language(message.from_user.id) or "uz"
    await message.answer(
        ("Foydalanuvchini qanday qidirmoqchisiz?" if lang == "uz" else "Как хотите искать пользователя?"),
        reply_markup=get_inline_search_method()
    )
    await state.set_state(UserRoleChange.waiting_for_search_method)


@router.callback_query(F.data.startswith('search_'))
async def process_search_method(callback: CallbackQuery, state: FSMContext):
    search_type = callback.data
    lang = await get_user_language(callback.from_user.id) or "uz"

    if search_type == 'search_telegram_id':
        await callback.message.edit_text(
            ("Foydalanuvchining Telegram ID raqamini yuboring:" if lang == "uz" else "Отправьте Telegram ID пользователя:"),
            reply_markup=None
        )
        await state.set_state(UserRoleChange.waiting_for_telegram_id)

    elif search_type == 'search_phone':
        await callback.message.edit_text(
            ("Foydalanuvchining telefon raqamini yuboring (998XXXXXXXXX formatida):" if lang == "uz" else "Отправьте номер телефона пользователя (в формате 998XXXXXXXXX):"),
            reply_markup=None
        )
        await state.set_state(UserRoleChange.waiting_for_phone)

    else:
        await state.clear()
        await callback.message.edit_text(
            ("❌ Rol o'zgartirish bekor qilindi." if lang == "uz" else "❌ Изменение роли отменено."),
            reply_markup=None
        )
        await callback.message.answer(
            ("Foydalanuvchilar paneli" if lang == "uz" else "Панель пользователей"),
            reply_markup=get_user_management_keyboard(lang)
        )

    await callback.answer()



@router.message(UserRoleChange.waiting_for_telegram_id)
async def process_telegram_id(message: Message, state: FSMContext):
    telegram_id = message.text.strip()
    lang = await get_user_language(message.from_user.id) or "uz"

    if not telegram_id.isdigit():
        await message.answer("❌ Xato! Telegram ID raqami bo'lishi kerak." if lang == "uz" else "❌ Ошибка! Должен быть числовой Telegram ID.")
        return

    user = await find_user_by_telegram_id(int(telegram_id))
    await process_user_found(message, state, user)


@router.message(UserRoleChange.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    lang = await get_user_language(message.from_user.id) or "uz"
    
    # Telefon raqami formatini tekshirish - turli formatlarni qo'llab-quvvatlash
    phone_pattern = re.compile(r"^\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$|^\+?998\d{9}$|^998\d{9}$|^\d{9}$")
    
    if not phone_pattern.match(phone):
        await message.answer(
            ("❌ Xato! Telefon raqami quyidagi formatlardan birida bo'lishi kerak:\n"
             "• +998901234567\n"
             "• 998901234567\n"
             "• 901234567\n"
             "• +998 90 123 45 67") if lang == "uz" else
            ("❌ Ошибка! Номер телефона должен быть в одном из форматов:\n"
             "• +998901234567\n"
             "• 998901234567\n"
             "• 901234567\n"
             "• +998 90 123 45 67")
        )
        return
        
    user = await find_user_by_phone(phone)
    await process_user_found(message, state, user)


async def process_user_found(message: Message, state: FSMContext, user):
    if user:
        await state.update_data(telegram_id=user['telegram_id'])
        await state.set_state(UserRoleChange.waiting_for_new_role)
        
        lang = await get_user_language(message.from_user.id) or "uz"
        role_display = ({
            'admin': '👑 Admin',
            'client': '👤 Mijoz',
            'manager': '👔 Menejer',
            'junior_manager': '👔 Junior Menejer',
            'controller': '👤 Controller',
            'technician': '🔧 Texnik',
            'warehouse': '📦 Ombor',
            'callcenter_operator': '📞 Call Center',
            'callcenter_supervisor': '📞 Call Center Supervisor'
        } if lang == "uz" else {
            'admin': '👑 Админ',
            'client': '👤 Клиент',
            'manager': '👔 Менеджер',
            'junior_manager': '👔 Джуниор-менеджер',
            'controller': '👤 Контроллер',
            'technician': '🔧 Техник',
            'warehouse': '📦 Склад',
            'callcenter_operator': '📞 Call Center',
            'callcenter_supervisor': '📞 Руководитель Call Center'
        }).get(user['role'], user['role'])
        
        await message.answer(
            (
                f"✅ Foydalanuvchi topildi!\n\n"
                f"🆔 Telegram ID: {user['telegram_id']}\n"
                f"👤 Foydalanuvchi: {user['full_name'] or user['username'] or 'N/A'}\n"
                f"📱 Telefon: {user['phone'] or 'N/A'}\n"
                f"👤 Hozirgi rol: {role_display}\n\n"
                "Yangi rolni tanlang:"
            ) if lang == "uz" else (
                f"✅ Пользователь найден!\n\n"
                f"🆔 Telegram ID: {user['telegram_id']}\n"
                f"👤 Пользователь: {user['full_name'] or user['username'] or 'N/A'}\n"
                f"📱 Телефон: {user['phone'] or 'N/A'}\n"
                f"👤 Текущая роль: {role_display}\n\n"
                "Выберите новую роль:"
            ),
            reply_markup=get_inline_role_selection()
        )
    else:
        await message.answer(("❌ Foydalanuvchi topilmadi. Qaytadan urinib ko'ring." if (await get_user_language(message.from_user.id) or "uz") == "uz" else "❌ Пользователь не найден. Попробуйте еще раз."))


@router.callback_query(F.data.startswith('role_'))
async def process_role_selection(callback: CallbackQuery, state: FSMContext):
    """Handle role selection from inline keyboard"""
    role_key = callback.data
    lang = await get_user_language(callback.from_user.id) or "uz"
    
    if role_key == 'role_cancel':
        await state.clear()
        await callback.message.edit_text(
            ("❌ Rol o'zgartirish bekor qilindi." if lang == "uz" else "❌ Изменение роли отменено."),
            reply_markup=None
        )
        await callback.message.answer(
            ("Foydalanuvchilar paneli" if lang == "uz" else "Панель пользователей"),
            reply_markup=get_user_management_keyboard(lang)
        )
    else:
        role_value = ROLE_MAPPING.get(role_key)
        if not role_value:
            await callback.answer(("❌ Xato! Noto'g'ri rol tanlandi." if lang == "uz" else "❌ Ошибка! Неверная роль."), show_alert=True)
            return
            
        data = await state.get_data()
        telegram_id = data.get('telegram_id')
        
        if not telegram_id:
            await callback.answer("❌ Xatolik: Foydalanuvchi topilmadi.", show_alert=True)
            return
            
        success = await update_user_role(telegram_id, role_value)
        
        if success:
            role_display = callback.message.reply_markup.inline_keyboard
            role_name = next((btn.text for row in role_display for btn in row if btn.callback_data == role_key), role_value)
            
            await callback.message.edit_text(
                ((f"✅ Foydalanuvchi roli muvaffaqiyatli o'zgartirildi!\n" f"👤 Yangi rol: {role_name}") if lang == "uz" else (f"✅ Роль пользователя успешно изменена!\n" f"👤 Новая роль: {role_name}")),
                reply_markup=None
            )
            await callback.message.answer(
                ("Bosh menyu" if lang == "uz" else "Главное меню"),
                reply_markup=get_user_management_keyboard(lang)
            )
        else:
            await callback.message.edit_text(
                ("❌ Xatolik: Rolni o'zgartirishda xatolik yuz berdi." if lang == "uz" else "❌ Ошибка: Не удалось изменить роль."),
                reply_markup=None
            )
            await callback.message.answer(
                ("Bosh menyu" if lang == "uz" else "Главное меню"),
                reply_markup=get_admin_main_menu(lang)
            )
        
        await state.clear()
    
    await callback.answer()


def format_user_info(user: dict, index: int) -> str:
    """Mijoz ma'lumotlarini muvozanatli formatda tayyorlash
    
    Args:
        user: Foydalanuvchi ma'lumotlari
        index: Tartib raqami
    
    Returns:
        str: Formatlangan mijoz ma'lumotlari
    """
    # Ro'yxatdan o'tgan vaqtni formatlash
    created_at = user.get('created_at')
    if created_at:
        if isinstance(created_at, str):
            try:
                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                formatted_date = created_date.strftime("%d.%m.%Y")
            except:
                formatted_date = "Noma'lum"
        else:
            formatted_date = created_at.strftime("%d.%m.%Y")
    else:
        formatted_date = "Noma'lum"
    
    # Mijoz ma'lumotlarini muvozanatli formatlash
    default_name = "Noma'lum"
    default_phone = "Noma'lum"
    newline = "\n"
    user_info = f"👤 <b>{index}.</b> {user.get('full_name', default_name)}{newline}"
    user_info += f"    🆔 <b>ID:</b> <code>{user.get('telegram_id')}</code>{newline}"
    user_info += f"    📱 <b>Telefon:</b> {user.get('phone', default_phone)}{newline}"
    
    # Username mavjud bo'lsa
    if user.get('username'):
        user_info += f"    👤 <b>Username:</b> @{user.get('username')}{newline}"
    
    # Rol ma'lumotini ko'rsatish
    default_role = "Noma'lum"
    role = user.get('role', default_role)
    role_display = {
        'admin': '👑 Admin',
        'client': '👤 Mijoz',
        'manager': '👨‍💼 Menejer',
        'junior_manager': '👨‍💼 Kichik Menejer',
        'controller': '🎛️ Nazoratchi',
        'technician': '🔧 Texnik',
        'warehouse': '📦 Ombor',
        'callcenter_operator': '📞 Call Center',
        'callcenter_supervisor': '📞 Call Center Boshlig\'i'
    }.get(role, f'🚀 {role.title()}')
    
    user_info += f"    🚀 <b>Rol:</b> {role_display}\n"
    user_info += f"    📅 <b>Sana:</b> {formatted_date}\n\n"
    
    return user_info


async def show_users_page(message: Message, state: FSMContext, page: int = 1, user_type: str = "all"):
    """Foydalanuvchilar sahifasini ko'rsatish"""
    try:
        per_page = 5
        offset = (page - 1) * per_page
        
        if user_type == "all":
            users = await get_all_users_paginated(limit=per_page, offset=offset)
            # Get total count
            all_users = await get_all_users_paginated(limit=1000, offset=0)
            total = len(all_users)
            title = "👥 Barcha foydalanuvchilar"
        elif user_type == "staff":
            # Barcha rollarni olish (client dan boshqa)
            staff_roles = ['admin', 'manager', 'junior_manager', 'controller', 'technician', 'warehouse', 'callcenter_operator', 'callcenter_supervisor']
            # Get all users first, then filter
            all_users = await get_all_users_paginated(limit=1000, offset=0)
            staff_users = [user for user in all_users if user['role'] in staff_roles]
            total = len(staff_users)
            # Apply pagination to filtered results
            users = staff_users[offset:offset + per_page]
            title = "👤 Xodimlar ro'yxati"
        elif user_type == "client":
            users = await get_users_by_role_paginated(role="client", limit=per_page, offset=offset)
            # Get total count for clients
            all_clients = await get_users_by_role_paginated(role="client", limit=1000, offset=0)
            total = len(all_clients)
            title = "👤 Mijozlar ro'yxati"
        else:
            await message.answer("❌ Noto'g'ri foydalanuvchi turi!", parse_mode='Markdown')
            return

        if not users:
            await message.answer(f"{title}\n\n📭 Foydalanuvchilar topilmadi.", parse_mode='Markdown')
            return

        # Calculate pagination info
        total_pages = (total + per_page - 1) // per_page  # Ceiling division
        has_prev = page > 1
        has_next = page < total_pages

        # Sarlavha va statistika
        text = f"{title}\n\n"
        text += f"📊 Jami: {total} ta | Sahifa: {page}/{total_pages}\n\n"
        if user_type == "client":
            text += "📋 <b>Mijozlar ro'yxati:</b>\n\n"
        elif user_type == "staff":
            text += "📋 <b>Xodimlar ro'yxati:</b>\n\n"
        else:
            text += "📋 <b>Foydalanuvchilar ro'yxati:</b>\n\n"
        
        # Foydalanuvchilar ro'yxatini formatlash
        for i, user in enumerate(users, 1):
            text += format_user_info(user, i)
        
        # Paginatsiya tugmalari
        from keyboards.admin_buttons import get_users_pagination_keyboard
        keyboard = get_users_pagination_keyboard(
            current_page=page,
            total_pages=total_pages,
            has_prev=has_prev,
            has_next=has_next,
            user_type=user_type
        )
        
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
        
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}", parse_mode='Markdown')


@router.callback_query(F.data.startswith('users_page_'))
async def handle_users_pagination(callback: CallbackQuery, state: FSMContext):
    """Foydalanuvchilar paginatsiyasini boshqarish"""
    try:
        # Callback data: users_page_TYPE_PAGE
        parts = callback.data.split('_')
        if len(parts) >= 4:
            user_type = parts[2]  # all, staff yoki client
            page = int(parts[3])
            
            # Eski xabarni o'chirish va yangi xabar yuborish o'rniga
            # Xabar matnini yangilash
            per_page = 5
            offset = (page - 1) * per_page
            
            if user_type == "all":
                users = await get_all_users_paginated(limit=per_page, offset=offset)
                # Get total count
                all_users = await get_all_users_paginated(limit=1000, offset=0)
                total = len(all_users)
                title = "👥 Barcha foydalanuvchilar"
            elif user_type == "staff":
                staff_roles = ['admin', 'manager', 'junior_manager', 'controller', 'technician', 'warehouse', 'callcenter_operator', 'callcenter_supervisor']
                # Get all users first, then filter
                all_users = await get_all_users_paginated(limit=1000, offset=0)
                staff_users = [user for user in all_users if user['role'] in staff_roles]
                total = len(staff_users)
                # Apply pagination to filtered results
                users = staff_users[offset:offset + per_page]
                title = "👤 Xodimlar ro'yxati"
            elif user_type == "client":
                users = await get_users_by_role_paginated(role="client", limit=per_page, offset=offset)
                # Get total count for clients
                all_clients = await get_users_by_role_paginated(role="client", limit=1000, offset=0)
                total = len(all_clients)
                title = "👤 Mijozlar ro'yxati"
            else:
                await callback.answer("❌ Noto'g'ri foydalanuvchi turi!", show_alert=True)
                return

            if not users:
                await callback.message.edit_text(f"{title}\n\n📭 Foydalanuvchilar topilmadi.", parse_mode='Markdown')
                return

            # Calculate pagination info
            total_pages = (total + per_page - 1) // per_page  # Ceiling division
            has_prev = page > 1
            has_next = page < total_pages

            # Sarlavha va statistika
            text = f"{title}\n\n"
            text += f"📊 Jami: {total} ta | Sahifa: {page}/{total_pages}\n\n"
            if user_type == "client":
                text += "📋 **Mijozlar ro'yxati:**\n\n"
            elif user_type == "staff":
                text += "📋 **Xodimlar ro'yxati:**\n\n"
            else:
                text += "📋 **Foydalanuvchilar ro'yxati:**\n\n"
            
            # Foydalanuvchilar ro'yxatini formatlash
            for i, user in enumerate(users, 1):
                text += format_user_info(user, i)
            
            # Paginatsiya tugmalari
            from keyboards.admin_buttons import get_users_pagination_keyboard
            keyboard = get_users_pagination_keyboard(
                current_page=page,
                total_pages=total_pages,
                has_prev=has_prev,
                has_next=has_next,
                user_type=user_type
            )
            
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
    except Exception as e:
        await callback.answer(f"❌ Xatolik: {str(e)}", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data == 'users_back_to_menu')
async def users_back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Foydalanuvchilar menyusiga qaytish"""
    await state.clear()
    await callback.message.edit_text(
        "Foydalanuvchilar paneli",
        reply_markup=None
    )
    await callback.message.answer(
        "Foydalanuvchilar paneli",
        reply_markup=get_user_management_keyboard()
    )
    await callback.answer()


@router.message(F.text.in_(["◀️ Orqaga", "◀️ Назад"]))
async def back_to_main_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Admin paneli",
        reply_markup=get_admin_main_menu()
    )
