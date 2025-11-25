from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime
import logging

from database.admin.queries import (
    get_system_overview,
    get_recent_activity,
    get_performance_metrics,
    get_database_info
)
from keyboards.admin_buttons import get_system_status_keyboard
from database.basic.language import get_user_language

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text.in_( ["🔧 Tizim holati", "🔧 Состояние системы"]))
async def status_handler(message: Message, state: FSMContext = None):
    """Tizim holati asosiy menyusi"""
    if state:
        await state.clear()
    
    lang = await get_user_language(message.from_user.id) or "uz"
    
    text = ("🔧 **Tizim holati boshqaruvi**\n\n" if lang == "uz" else "🔧 **Панель состояния системы**\n\n")
    text += ("Quyidagi bo'limlardan birini tanlang:" if lang == "uz" else "Выберите один из следующих разделов:")
    
    await message.answer(
        text,
        reply_markup=get_system_status_keyboard(lang),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "system_overview")
async def system_overview_handler(callback: CallbackQuery):
    """Tizimning umumiy ko'rinishi"""
    await callback.answer()
    
    try:
        lang = await get_user_language(callback.from_user.id) or "uz"
        stats = await get_system_overview()
        
        text = ("📊 **Tizimning umumiy ko'rinishi**\n\n" if lang == "uz" else "📊 **Общий обзор системы**\n\n")
        
        # Foydalanuvchilar statistikasi
        text += ("👥 **Foydalanuvchilar:**\n" if lang == "uz" else "👥 **Пользователи:**\n")
        text += (f"• Jami: {stats['total_users']}\n" if lang == "uz" else f"• Всего: {stats['total_users']}\n")
        text += (f"• Faol: {stats['active_users']}\n" if lang == "uz" else f"• Активные: {stats['active_users']}\n")
        text += (f"• Bloklangan: {stats['blocked_users']}\n\n" if lang == "uz" else f"• Заблокированные: {stats['blocked_users']}\n\n")
        
        # Rollar bo'yicha
        text += ("👤 **Rollar bo'yicha:**\n" if lang == "uz" else "👤 **По ролям:**\n")
        for role, count in stats['users_by_role'].items():
            role_name = {
                'admin': ('Admin' if lang == 'uz' else 'Админ'),
                'client': ('Mijoz' if lang == 'uz' else 'Клиент'),
                'manager': ('Menejer' if lang == 'uz' else 'Менеджер'),
                'junior_manager': ('Kichik menejer' if lang == 'uz' else 'Джуниор-менеджер'),
                'controller': ('Nazoratchi' if lang == 'uz' else 'Контроллер'),
                'technician': ('Texnik' if lang == 'uz' else 'Техник'),
                'warehouse': ('Ombor' if lang == 'uz' else 'Склад'),
                'callcenter_supervisor': ('Call center supervisor' if lang == 'uz' else 'Руководитель КЦ'),
                'callcenter_operator': ('Call center operator' if lang == 'uz' else 'Оператор КЦ')
            }.get(role, role)
            text += f"• {role_name}: {count}\n"
        
        text += ("\n📝 **Zayavkalar:**\n" if lang == "uz" else "\n📝 **Заявки:**\n")
        text += (f"• Ulanish: {stats['total_connection_orders']}\n" if lang == "uz" else f"• Подключение: {stats['total_connection_orders']}\n")
        text += (f"• Texnik: {stats['total_technician_orders']}\n" if lang == "uz" else f"• Технические: {stats['total_technician_orders']}\n")
        text += (f"• Xodim: {stats['total_staff_orders']}\n\n" if lang == "uz" else f"• Сотрудники: {stats['total_staff_orders']}\n\n")
        
        text += ("📅 **Bugungi zayavkalar:**\n" if lang == "uz" else "📅 **Заявки за сегодня:**\n")
        text += (f"• Ulanish: {stats['today_connection_orders']}\n" if lang == "uz" else f"• Подключение: {stats['today_connection_orders']}\n")
        text += (f"• Texnik: {stats['today_technician_orders']}\n\n" if lang == "uz" else f"• Технические: {stats['today_technician_orders']}\n\n")
        
        text += (f"🕐 Yangilangan: {datetime.now().strftime('%H:%M:%S')}" if lang == "uz" else f"🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_system_status_keyboard(lang),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        lang = await get_user_language(callback.from_user.id) or "uz"
        await callback.message.edit_text(
            (f"❌ Xatolik yuz berdi: {str(e)}" if lang == "uz" else f"❌ Произошла ошибка: {str(e)}"),
            reply_markup=get_system_status_keyboard(lang)
        )

@router.callback_query(F.data == "system_close")
async def system_close_handler(callback: CallbackQuery):
    """Tizim holati menyusini yopish"""
    await callback.answer()
    
    try:
        # Xabarni o'chirish
        await callback.message.delete()
        
    except Exception as e:
        # Agar o'chirib bo'lmasa, oddiy xabar bilan almashtirish
        lang = await get_user_language(callback.from_user.id) or "uz"
        await callback.message.edit_text(
            ("✅ Tizim holati menyusi yopildi." if lang == "uz" else "✅ Меню состояния системы закрыто."),
            reply_markup=None
        )

@router.callback_query(F.data == "system_orders")
async def system_orders_handler(callback: CallbackQuery):
    """Zayavkalar holati"""
    await callback.answer()
    
    try:
        lang = await get_user_language(callback.from_user.id) or "uz"
        orders_data = await get_orders_by_status()
        
        text = ("📝 **Zayavkalar holati**\n\n" if lang == "uz" else "📝 **Статус заявок**\n\n")
        
        # Ulanish zayavkalari
        text += ("🔗 **Ulanish zayavkalari:**\n" if lang == "uz" else "🔗 **Заявки на подключение:**\n")
        for status, count in orders_data['connection_orders'].items():
            status_name = {
                'new': ('Yangi' if lang == 'uz' else 'Новая'),
                'in_manager': ('Menejerda' if lang == 'uz' else 'У менеджера'),
                'in_junior_manager': ('Kichik Menejerda' if lang == 'uz' else 'У джуниор-менеджера'),
                'in_controller': ('Nazoratchida' if lang == 'uz' else 'У контроллера'),
                'in_technician': ('Texnikda' if lang == 'uz' else 'У техника'),
                'in_technician_work': ('Texnik ishda' if lang == 'uz' else 'В работе у техника'),
                'completed': ('Bajarilgan' if lang == 'uz' else 'Завершена')
            }.get(status, status)
            text += f"• {status_name}: {count}\n"
        
        text += ("\n🔧 **Texnik zayavkalar:**\n" if lang == "uz" else "\n🔧 **Технические заявки:**\n")
        for status, count in orders_data['technician_orders'].items():
            status_name = {
                'new': ('Yangi' if lang == 'uz' else 'Новая'),
                'in_controller': ('Nazoratchida' if lang == 'uz' else 'У контроллера'),
                'in_technician': ('Texnikda' if lang == 'uz' else 'У техника'),
                'in_technician_work': ('Texnik ishda' if lang == 'uz' else 'В работе у техника'),
                'completed': ('Bajarilgan' if lang == 'uz' else 'Завершена')
            }.get(status, status)
            text += f"• {status_name}: {count}\n"
        
        text += ("\n👥 **Xodim zayavkalari:**\n" if lang == "uz" else "\n👥 **Заявки сотрудников:**\n")
        for status, count in orders_data['staff_orders'].items():
            status_name = {
                'new': ('Yangi' if lang == 'uz' else 'Новая'),
                'in_manager': ('Menejerda' if lang == 'uz' else 'У менеджера'),
                'in_junior_manager': ('Kichik Menejerda' if lang == 'uz' else 'У джуниор-менеджера'),
                'in_controller': ('Nazoratchida' if lang == 'uz' else 'У контроллера'),
                'completed': ('Bajarilgan' if lang == 'uz' else 'Завершена')
            }.get(status, status)
            text += f"• {status_name}: {count}\n"
        
        text += (f"\n🕐 Yangilangan: {datetime.now().strftime('%H:%M:%S')}" if lang == "uz" else f"\n🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_system_status_keyboard(lang),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        lang = await get_user_language(callback.from_user.id) or "uz"
        await callback.message.edit_text(
            (f"❌ Xatolik yuz berdi: {str(e)}" if lang == "uz" else f"❌ Произошла ошибка: {str(e)}"),
            reply_markup=get_system_status_keyboard(lang)
        )

@router.callback_query(F.data == "system_performance")
async def system_performance_handler(callback: CallbackQuery):
    """Ishlash ko'rsatkichlari"""
    await callback.answer()
    
    try:
        lang = await get_user_language(callback.from_user.id) or "uz"
        metrics = await get_performance_metrics()
        
        text = ("⚡ **Ishlash ko'rsatkichlari**\n\n" if lang == "uz" else "⚡ **Показатели производительности**\n\n")
        
        text += ("📈 **Bajarilish foizi:**\n" if lang == "uz" else "📈 **Процент выполнения:**\n")
        text += ((f"• Ulanish zayavkalari: {metrics['connection_completion_rate']:.1f}%\n") if lang == "uz" else (f"• Подключение: {metrics['connection_completion_rate']:.1f}%\n"))
        text += ((f"• Texnik zayavkalar: {metrics['technician_completion_rate']:.1f}%\n\n") if lang == "uz" else (f"• Технические: {metrics['technician_completion_rate']:.1f}%\n\n"))
        
        text += ("⏱ **O'rtacha bajarilish vaqti:**\n" if lang == "uz" else "⏱ **Среднее время выполнения:**\n")
        text += ((f"• {metrics['avg_completion_hours']:.1f} soat\n\n") if lang == "uz" else (f"• {metrics['avg_completion_hours']:.1f} ч.\n\n"))
        
        text += ("🏆 **Eng faol xodimlar:**\n" if lang == "uz" else "🏆 **Самые активные сотрудники:**\n")
        for staff in metrics['active_staff'][:5]:
            text += f"• {staff['full_name']} ({staff['role']}): {staff['activity_count']} faoliyat\n"
        
        text += (f"\n🕐 Yangilangan: {datetime.now().strftime('%H:%M:%S')}" if lang == "uz" else f"\n🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_system_status_keyboard(lang),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        lang = await get_user_language(callback.from_user.id) or "uz"
        await callback.message.edit_text(
            (f"❌ Xatolik yuz berdi: {str(e)}" if lang == "uz" else f"❌ Произошла ошибка: {str(e)}"),
            reply_markup=get_system_status_keyboard(lang)
        )

@router.callback_query(F.data == "system_activity")
async def system_activity_handler(callback: CallbackQuery):
    """So'nggi faoliyat"""
    await callback.answer()
    
    try:
        lang = await get_user_language(callback.from_user.id) or "uz"
        activities = await get_recent_activity()
        
        text = ("🔄 **So'nggi 10ta faoliyat**\n\n" if lang == "uz" else "🔄 **Последние 10 действий**\n\n")
        
        if not activities:
            text += ("Hech qanday faoliyat topilmadi." if lang == "uz" else "Активность не найдена.")
        else:
            for activity in activities[:10]:
                activity_type = {
                    'connection_order': ('🔗 Ulanish' if lang == 'uz' else '🔗 Подключение'),
                    'technician_order': ('🔧 Texnik' if lang == 'uz' else '🔧 Техническая'),
                    'staff_order': ('👥 Xodim' if lang == 'uz' else '👥 Сотрудник')
                }.get(activity['type'], activity['type'])
                
                status_name = {
                    'new': ('Yangi' if lang == 'uz' else 'Новая'),
                    'in_manager': ('Menejerda' if lang == 'uz' else 'У менеджера'),
                    'in_junior_manager': ('Kichik Menejerda' if lang == 'uz' else 'У джуниор-менеджера'), 
                    'in_controller': ('Nazoratchida' if lang == 'uz' else 'У контроллера'),
                    'in_technician': ('Texnikda' if lang == 'uz' else 'У техника'),
                    'in_technician_work': ('Texnik ishda' if lang == 'uz' else 'В работе у техника'),
                    'in_diagnostics': ('Diagnostikada' if lang == 'uz' else 'На диагностике'),
                    'in_repairs': ("Ta'mirda" if lang == 'uz' else 'В ремонте'),
                    'in_warehouse': ('Omborda' if lang == 'uz' else 'На складе'),
                    'completed': ('Bajarilgan' if lang == 'uz' else 'Завершена'),
                    'betweencontrollertechnician': ('Nazoratchi → Texnik' if lang == 'uz' else 'Контроллер → Техник'),
                    'between_controller_technician': ('Nazoratchi → Texnik' if lang == 'uz' else 'Контроллер → Техник'),
                    'pending': ('Kutilmoqda' if lang == 'uz' else 'Ожидает'),
                    'assigned': ('Tayinlangan' if lang == 'uz' else 'Назначена'),
                    'cancelled': ('Bekor qilingan' if lang == 'uz' else 'Отменена')
                }.get(activity['status'], activity['status'])
                
                time_str = activity['updated_at'].strftime('%H:%M')
                text += f"• {activity_type} #{activity['id']} - {status_name} ({time_str})\n"
        
        text += (f"\n🕐 Yangilangan: {datetime.now().strftime('%H:%M:%S')}" if lang == "uz" else f"\n🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_system_status_keyboard(lang),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        lang = await get_user_language(callback.from_user.id) or "uz"
        await callback.message.edit_text(
            (f"❌ Xatolik yuz berdi: {str(e)}" if lang == "uz" else f"❌ Произошла ошибка: {str(e)}"),
            reply_markup=get_system_status_keyboard(lang)
        )

@router.callback_query(F.data == "system_database")
async def system_database_handler(callback: CallbackQuery):
    """Ma'lumotlar bazasi haqida ma'lumot"""
    await callback.answer()
    
    try:
        lang = await get_user_language(callback.from_user.id) or "uz"
        db_info = await get_database_info()
        
        text = ("💾 **Ma'lumotlar bazasi**\n\n" if lang == "uz" else "💾 **База данных**\n\n")
        
        text += (f"📊 **Umumiy hajm:** {db_info['database_size']}\n" if lang == "uz" else f"📊 **Общий размер:** {db_info['database_size']}\n")
        text += (f"🔗 **Faol ulanishlar:** {db_info['active_connections']}\n\n" if lang == "uz" else f"🔗 **Активные подключения:** {db_info['active_connections']}\n\n")
        
        text += ("📋 **Jadvallar hajmi:**\n" if lang == "uz" else "📋 **Размеры таблиц:**\n")
        for table in db_info['table_sizes'][:8]:
            text += f"• {table['tablename']}: {table['size']}\n"
        
        text += (f"\n🕐 Yangilangan: {datetime.now().strftime('%H:%M:%S')}" if lang == "uz" else f"\n🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_system_status_keyboard(lang),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        lang = await get_user_language(callback.from_user.id) or "uz"
        await callback.message.edit_text(
            (f"❌ Xatolik yuz berdi: {str(e)}" if lang == "uz" else f"❌ Произошла ошибка: {str(e)}"),
            reply_markup=get_system_status_keyboard(lang)
        )

@router.callback_query(F.data == "system_refresh")
async def system_refresh_handler(callback: CallbackQuery):
    """Tizim holatini yangilash"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    await callback.answer("🔄 Yangilanmoqda..." if lang == "uz" else "🔄 Обновляется...")
    
    try:
        # Yangilangan asosiy menyu matnini yaratish
        text = (f"🔧 **Tizim holati boshqaruvi**\n\n" if lang == "uz" else f"🔧 **Панель состояния системы**\n\n")
        text += (f"Quyidagi bo'limlardan birini tanlang:\n\n" if lang == "uz" else f"Выберите один из разделов:\n\n")
        text += (f"📊 **Umumiy ko'rinish** - Tizim statistikasi\n" if lang == "uz" else f"📊 **Общий обзор** - Статистика системы\n")
        text += (f"📋 **Zayavkalar holati** - Barcha zayavkalar\n" if lang == "uz" else f"📋 **Статус заявок** - Все заявки\n")
        text += (f"⚡ **Ishlash ko'rsatkichlari** - Tizim samaradorligi\n" if lang == "uz" else f"⚡ **Показатели производительности** - Эффективность системы\n")
        text += (f"🔄 **So'nggi faoliyat** - Oxirgi 10tasi\n" if lang == "uz" else f"🔄 **Последняя активность** - Последние 10\n")
        text += (f"💾 **Ma'lumotlar bazasi** - DB holati\n\n" if lang == "uz" else f"💾 **База данных** - Состояние БД\n\n")
        text += (f"🕐 Yangilangan: {datetime.now().strftime('%H:%M:%S')}" if lang == "uz" else f"🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}")
        
        # Xabarni edit qilish
        await callback.message.edit_text(
            text,
            reply_markup=get_system_status_keyboard(lang),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await callback.message.edit_text(
            (f"❌ Xatolik yuz berdi: {str(e)}" if lang == "uz" else f"❌ Произошла ошибка: {str(e)}"),
            reply_markup=get_system_status_keyboard(lang)
        )
