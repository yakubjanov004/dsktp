from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from filters.role_filter import RoleFilter
from keyboards.admin_buttons import get_statistics_keyboard
from database.admin.queries import get_user_statistics, get_system_overview
from database.manager.export import get_manager_statistics_for_export
from database.controller.export import get_controller_statistics_for_export
from database.basic.language import get_user_language
import logging

router = Router()
logger = logging.getLogger(__name__)
router.message.filter(RoleFilter("admin"))
router.callback_query.filter(RoleFilter("admin"))

@router.message(F.text.in_( ["📊 Statistika", "📊 Статистика"]))
async def statistics_handler(message: Message):
    """Admin statistika bo'limi - asosiy menyu"""
    lang = await get_user_language(message.from_user.id) or "uz"
    text = ("📊 **Admin Statistika Bo'limi**\n\n" if lang == "uz" else "📊 **Раздел статистики администратора**\n\n")
    text += ("Quyidagi bo'limlardan birini tanlang:" if lang == "uz" else "Выберите один из следующих разделов:")
    
    await message.answer(
        text,
        reply_markup=get_statistics_keyboard(lang),
        parse_mode="Markdown"
    )

# Umumiy ko'rinish
@router.callback_query(F.data == "stats_overview")
async def stats_overview_handler(callback: CallbackQuery):
    """Umumiy statistika ko'rinishi"""
    await callback.answer()
    
    try:
        lang = await get_user_language(callback.from_user.id) or "uz"
        # Tizim umumiy ma'lumotlari
        system_stats = await get_system_overview()
        
        text = ("📈 **Umumiy Ko'rinish**\n\n" if lang == "uz" else "📈 **Общий обзор**\n\n")
        
        # Foydalanuvchilar
        text += ("👥 **Foydalanuvchilar:**\n" if lang == "uz" else "👥 **Пользователи:**\n")
        text += (f"• Jami: {system_stats['total_users']}\n" if lang == "uz" else f"• Всего: {system_stats['total_users']}\n")
        text += (f"• Faol: {system_stats['active_users']}\n" if lang == "uz" else f"• Активные: {system_stats['active_users']}\n")
        text += (f"• Bloklangan: {system_stats['blocked_users']}\n\n" if lang == "uz" else f"• Заблокированные: {system_stats['blocked_users']}\n\n")
        
        # Buyurtmalar
        text += ("📋 **Buyurtmalar:**\n" if lang == "uz" else "📋 **Заявки:**\n")
        text += (f"• Ulanish: {system_stats['total_connection_orders']}\n" if lang == "uz" else f"• Подключение: {system_stats['total_connection_orders']}\n")
        text += (f"• Texnik: {system_stats['total_technician_orders']}\n" if lang == "uz" else f"• Технические: {system_stats['total_technician_orders']}\n")
        text += (f"• staff: {system_stats['total_staff_orders']}\n\n" if lang == "uz" else f"• Сотрудники: {system_stats['total_staff_orders']}\n\n")
        
        # Bugungi buyurtmalar
        text += ("📅 **Bugungi buyurtmalar:**\n" if lang == "uz" else "📅 **Заявки за сегодня:**\n")
        text += (f"• Ulanish: {system_stats['today_connection_orders']}\n" if lang == "uz" else f"• Подключение: {system_stats['today_connection_orders']}\n")
        text += (f"• Texnik: {system_stats['today_technician_orders']}\n" if lang == "uz" else f"• Технические: {system_stats['today_technician_orders']}\n")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_statistics_keyboard(lang),
            parse_mode="Markdown"
        )
    except Exception as e:
        lang = await get_user_language(callback.from_user.id) or "uz"
        await callback.message.edit_text(
            ("❌ Statistika ma'lumotlarini yuklashda xatolik yuz berdi." if lang == "uz" else "❌ Произошла ошибка при загрузке статистики."),
            reply_markup=get_statistics_keyboard(lang)
        )

# Foydalanuvchilar statistikasi
@router.callback_query(F.data == "stats_users")
async def stats_users_handler(callback: CallbackQuery):
    """Foydalanuvchilar statistikasi"""
    await callback.answer()
    
    try:
        lang = await get_user_language(callback.from_user.id) or "uz"
        user_stats = await get_user_statistics()
        
        text = ("👥 **Foydalanuvchilar Statistikasi**\n\n" if lang == "uz" else "👥 **Статистика пользователей**\n\n")
        text += ("📊 **Umumiy ma'lumotlar:**\n" if lang == "uz" else "📊 **Общие сведения:**\n")
        text += (f"• Jami foydalanuvchilar: {user_stats['total_users']}\n" if lang == "uz" else f"• Всего пользователей: {user_stats['total_users']}\n")
        text += (f"• Faol foydalanuvchilar: {user_stats['active_users']}\n" if lang == "uz" else f"• Активные пользователи: {user_stats['active_users']}\n")
        text += (f"• Bloklangan: {user_stats['blocked_users']}\n\n" if lang == "uz" else f"• Заблокированные: {user_stats['blocked_users']}\n\n")
        
        text += ("👤 **Rollar bo'yicha:**\n" if lang == "uz" else "👤 **По ролям:**\n")
        for role_stat in user_stats['role_statistics']:
            role_name = {
                'admin': ('Admin' if lang == 'uz' else 'Админ'),
                'client': ('Mijoz' if lang == 'uz' else 'Клиент'),
                'manager': ('Menejer' if lang == 'uz' else 'Менеджер'),
                'junior_manager': ('Kichik menejer' if lang == 'uz' else 'Джуниор-менеджер'),
                'controller': ('Nazoratchi' if lang == 'uz' else 'Контроллер'),
                'technician': ('Texnik' if lang == 'uz' else 'Техник'),
                'warehouse': ('Ombor' if lang == 'uz' else 'Склад'),
                'callcenter_supervisor': ('Call center supervisor' if lang == 'uz' else 'Руководитель колл-центра'),
                'callcenter_operator': ('Call center operator' if lang == 'uz' else 'Оператор колл-центра')
            }.get(role_stat['role'], role_stat['role'])
            text += f"• {role_name}: {role_stat['count']}\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_statistics_keyboard(lang),
            parse_mode="Markdown"
        )
    except Exception as e:
        lang = await get_user_language(callback.from_user.id) or "uz"
        await callback.message.edit_text(
            ("❌ Foydalanuvchilar statistikasini yuklashda xatolik yuz berdi." if lang == "uz" else "❌ Произошла ошибка при загрузке статистики пользователей."),
            reply_markup=get_statistics_keyboard(lang)
        )

# Ulanish buyurtmalari statistikasi
@router.callback_query(F.data == "stats_connection_orders")
async def stats_connection_orders_handler(callback: CallbackQuery):
    """Ulanish buyurtmalari statistikasi"""
    await callback.answer()
    
    try:
        lang = await get_user_language(callback.from_user.id) or "uz"
        manager_stats = await get_manager_statistics_for_export()
        
        text = ("📋 **Ulanish Buyurtmalari Statistikasi**\n\n" if lang == "uz" else "📋 **Статистика заявок на подключение**\n\n")
        
        if manager_stats and 'summary' in manager_stats:
            summary = manager_stats['summary']
            text += ("📊 **Umumiy ma'lumotlar:**\n" if lang == "uz" else "📊 **Общие сведения:**\n")
            text += (f"• Jami buyurtmalar: {summary['total_orders']}\n" if lang == "uz" else f"• Всего заявок: {summary['total_orders']}\n")
            text += (f"• Yangi: {summary['new_orders']}\n" if lang == "uz" else f"• Новые: {summary['new_orders']}\n")
            text += (f"• Jarayonda: {summary['in_progress_orders']}\n" if lang == "uz" else f"• В процессе: {summary['in_progress_orders']}\n")
            text += (f"• Yakunlangan: {summary['completed_orders']}\n" if lang == "uz" else f"• Завершенные: {summary['completed_orders']}\n")
            text += (f"• Yakunlanish foizi: {summary['completion_rate']}%\n" if lang == "uz" else f"• Процент завершения: {summary['completion_rate']}%\n")
            text += (f"• Yagona mijozlar: {summary['unique_clients']}\n" if lang == "uz" else f"• Уникальные клиенты: {summary['unique_clients']}\n")
            text += (f"• Tarif rejalari: {summary['unique_tariffs_used']}\n" if lang == "uz" else f"• Тарифные планы: {summary['unique_tariffs_used']}\n")
        else:
            text += ("📊 Hozircha buyurtmalar mavjud emas." if lang == "uz" else "📊 Пока заявок нет.")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_statistics_keyboard(lang),
            parse_mode="Markdown"
        )
    except Exception as e:
        lang = await get_user_language(callback.from_user.id) or "uz"
        await callback.message.edit_text(
            ("❌ Ulanish buyurtmalari statistikasini yuklashda xatolik yuz berdi." if lang == "uz" else "❌ Ошибка при загрузке статистики подключений."),
            reply_markup=get_statistics_keyboard(lang)
        )

# Texnik buyurtmalar statistikasi
@router.callback_query(F.data == "stats_tech_orders")
async def stats_tech_orders_handler(callback: CallbackQuery):
    """Texnik buyurtmalar statistikasi"""
    await callback.answer()
    
    try:
        lang = await get_user_language(callback.from_user.id) or "uz"
        controller_stats = await get_controller_statistics_for_export()
        
        text = ("🔧 **Texnik Buyurtmalar Statistikasi**\n\n" if lang == "uz" else "🔧 **Статистика технических заявок**\n\n")
        
        if controller_stats and 'summary' in controller_stats:
            summary = controller_stats['summary']
            text += ("📊 **Umumiy ma'lumotlar:**\n" if lang == "uz" else "📊 **Общие сведения:**\n")
            text += (f"• Jami arizalar: {summary['total_requests']}\n" if lang == "uz" else f"• Всего заявок: {summary['total_requests']}\n")
            text += (f"• Yangi: {summary['new_requests']}\n" if lang == "uz" else f"• Новые: {summary['new_requests']}\n")
            text += (f"• Jarayonda: {summary['in_progress_requests']}\n" if lang == "uz" else f"• В процессе: {summary['in_progress_requests']}\n")
            text += (f"• Yakunlangan: {summary['completed_requests']}\n" if lang == "uz" else f"• Завершенные: {summary['completed_requests']}\n")
            text += (f"• Yakunlanish foizi: {summary['completion_rate']}%\n" if lang == "uz" else f"• Процент завершения: {summary['completion_rate']}%\n")
            text += (f"• Yagona mijozlar: {summary['unique_clients']}\n" if lang == "uz" else f"• Уникальные клиенты: {summary['unique_clients']}\n")
            text += (f"• Muammo turlari: {summary['unique_problem_types']}\n" if lang == "uz" else f"• Типы проблем: {summary['unique_problem_types']}\n")
        else:
            text += ("📊 Hozircha texnik arizalar mavjud emas." if lang == "uz" else "📊 Технических заявок пока нет.")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_statistics_keyboard(lang),
            parse_mode="Markdown"
        )
    except Exception as e:
        lang = await get_user_language(callback.from_user.id) or "uz"
        await callback.message.edit_text(
            ("❌ Texnik buyurtmalar statistikasini yuklashda xatolik yuz berdi." if lang == "uz" else "❌ Ошибка при загрузке статистики технических заявок."),
            reply_markup=get_statistics_keyboard(lang)
        )

# Rollar bo'yicha statistika
@router.callback_query(F.data == "stats_by_roles")
async def stats_by_roles_handler(callback: CallbackQuery):
    """Rollar bo'yicha batafsil statistika"""
    await callback.answer()
    
    try:
        lang = await get_user_language(callback.from_user.id) or "uz"
        system_stats = await get_system_overview()
        
        text = ("👤 **Rollar Bo'yicha Batafsil Statistika**\n\n" if lang == "uz" else "👤 **Подробная статистика по ролям**\n\n")
        
        if 'users_by_role' in system_stats:
            for role, count in system_stats['users_by_role'].items():
                role_name = {
                    'admin': ('👑 Admin' if lang == 'uz' else '👑 Админ'),
                    'client': ('👤 Mijoz' if lang == 'uz' else '👤 Клиент'),
                    'manager': ('👨‍💼 Menejer' if lang == 'uz' else '👨‍💼 Менеджер'),
                    'junior_manager': ('👨‍💻 Kichik menejer' if lang == 'uz' else '👨‍💻 Джуниор-менеджер'),
                    'controller': ('🔍 Nazoratchi' if lang == 'uz' else '🔍 Контроллер'),
                    'technician': ('🔧 Texnik' if lang == 'uz' else '🔧 Техник'),
                    'warehouse': ('📦 Ombor' if lang == 'uz' else '📦 Склад'),
                    'callcenter_supervisor': ('📞 Call center supervisor' if lang == 'uz' else '📞 Руководитель КЦ'),
                    'callcenter_operator': ('☎️ Call center operator' if lang == 'uz' else '☎️ Оператор КЦ')
                }.get(role, f"❓ {role}")
                text += f"{role_name}: **{count}**\n"
        else:
            text += ("📊 Rol statistikasi mavjud emas." if lang == "uz" else "📊 Статистика по ролям отсутствует.")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_statistics_keyboard(lang),
            parse_mode="Markdown"
        )
    except Exception as e:
        lang = await get_user_language(callback.from_user.id) or "uz"
        await callback.message.edit_text(
            ("❌ Rollar statistikasini yuklashda xatolik yuz berdi." if lang == "uz" else "❌ Ошибка при загрузке статистики по ролям."),
            reply_markup=get_statistics_keyboard(lang)
        )

# Oylik statistika
@router.callback_query(F.data == "stats_monthly")
async def stats_monthly_handler(callback: CallbackQuery):
    """Oylik statistika tendensiyalari"""
    await callback.answer()
    
    try:
        lang = await get_user_language(callback.from_user.id) or "uz"
        manager_stats = await get_manager_statistics_for_export()
        controller_stats = await get_controller_statistics_for_export()
        
        text = ("📊 **Oylik Statistika (Oxirgi 6 oy)**\n\n" if lang == "uz" else "📊 **Месячная статистика (последние 6 месяцев)**\n\n")
        
        # Ulanish buyurtmalari oylik
        if manager_stats and 'monthly_trends' in manager_stats and manager_stats['monthly_trends']:
            text += ("📋 **Ulanish buyurtmalari:**\n" if lang == "uz" else "📋 **Подключения:**\n")
            for month_data in manager_stats['monthly_trends'][:3]:  # Faqat oxirgi 3 oy
                text += (f"• {month_data['month']}: {month_data['total_orders']} (✅ {month_data['completed_orders']})\n")
            text += "\n"
        
        # Texnik buyurtmalar oylik
        if controller_stats and 'monthly_trends' in controller_stats and controller_stats['monthly_trends']:
            text += ("🔧 **Texnik buyurtmalar:**\n" if lang == "uz" else "🔧 **Технические заявки:**\n")
            for month_data in controller_stats['monthly_trends'][:3]:  # Faqat oxirgi 3 oy
                text += (f"• {month_data['month']}: {month_data['total_requests']} (✅ {month_data['completed_requests']})\n")
        
        if not (manager_stats.get('monthly_trends') or controller_stats.get('monthly_trends')):
            text += ("📊 Oylik statistika ma'lumotlari mavjud emas." if lang == "uz" else "📊 Данные по месячной статистике отсутствуют.")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_statistics_keyboard(lang),
            parse_mode="Markdown"
        )
    except Exception as e:
        lang = await get_user_language(callback.from_user.id) or "uz"
        await callback.message.edit_text(
            ("❌ Oylik statistikani yuklashda xatolik yuz berdi." if lang == "uz" else "❌ Ошибка при загрузке месячной статистики."),
            reply_markup=get_statistics_keyboard(lang)
        )

# Close statistics menu
@router.callback_query(F.data == "stats_close")
async def close_statistics_handler(callback: CallbackQuery):
    """Close statistics menu and return to main menu"""
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    lang = await get_user_language(callback.from_user.id) or "uz"
    await callback.message.answer(
        ("Statistika bo'limi yopildi" if lang == "uz" else "Раздел статистики закрыт"),
    )
