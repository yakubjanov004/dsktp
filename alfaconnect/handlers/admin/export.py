from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from filters.role_filter import RoleFilter
from keyboards.admin_buttons import (
    get_admin_export_types_keyboard,
    get_admin_export_formats_keyboard,
    get_admin_time_period_keyboard,
)
from utils.export_utils import ExportUtils
from database.admin.export import (
    get_admin_users_for_export,
    get_admin_connection_orders_for_export,
    get_admin_technician_orders_for_export,
    get_admin_staff_orders_for_export,
    get_admin_statistics_for_export,
)
from database.warehouse.queries import (
    get_warehouse_inventory_for_export,
    get_warehouse_statistics_for_export,
)
from datetime import datetime
import logging
import os
import zipfile
import io
from database.basic.language import get_user_language

router = Router()
router.message.filter(RoleFilter(role="admin"))
logger = logging.getLogger(__name__)

@router.message(F.text.in_(["📤 Export", "📤 Экспорт"]))
async def export_handler(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_language(message.from_user.id) or "uz"
    await message.answer(
        ("📤 <b>Admin eksportlari</b>\n\nKerakli bo'limni tanlang:" if lang == "uz" else "📤 <b>Экспорт администратора</b>\n\nВыберите нужный раздел:"),
        reply_markup=get_admin_export_types_keyboard(lang),
        parse_mode="HTML",
    )


@router.message(F.text.in_(["🗄️ Backup & Logs", "🗄️ Бэкап и логи"]))
async def backup_and_logs_handler(message: Message, state: FSMContext):
    """Baza backup va log fayllarini zip qilib yuklab berish"""
    await state.clear()
    lang = await get_user_language(message.from_user.id) or "uz"
    
    try:
        # Loading xabari
        loading_text = "⏳ <b>Backup va loglar tayyorlanmoqda...</b>" if lang == "uz" else "⏳ <b>Подготовка бэкапа и логов...</b>"
        loading_msg = await message.answer(loading_text, parse_mode="HTML")
        
        # Zip fayl yaratish
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Database backup qo'shish
            try:
                from config import settings
                import subprocess
                import tempfile
                
                # PostgreSQL dump yaratish
                with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as temp_file:
                    temp_sql_path = temp_file.name
                
                # pg_dump buyrug'ini ishga tushirish
                dump_cmd = [
                    'pg_dump',
                    f'--host={settings.DB_HOST}',
                    f'--port={settings.DB_PORT}',
                    f'--username={settings.DB_USER}',
                    f'--dbname={settings.DB_NAME}',
                    '--no-password',  # Parol environment variable dan olinadi
                    '--format=plain',
                    '--no-owner',
                    '--no-privileges',
                    '--file', temp_sql_path
                ]
                
                # Environment variable qo'shish
                env = os.environ.copy()
                env['PGPASSWORD'] = settings.DB_PASSWORD
                
                result = subprocess.run(dump_cmd, env=env, capture_output=True, text=True)
                
                if result.returncode == 0:
                    # SQL faylni zip ga qo'shish
                    with open(temp_sql_path, 'rb') as sql_file:
                        zip_file.writestr('database_backup.sql', sql_file.read())
                    
                    # Temp faylni o'chirish
                    os.unlink(temp_sql_path)
                else:
                    logger.error(f"Database backup failed: {result.stderr}")
                    # Xatolik bo'lsa ham davom etamiz
                    
            except Exception as e:
                logger.error(f"Database backup error: {e}")
                # Xatolik bo'lsa ham davom etamiz
            
            # Log fayllarini qo'shish
            log_files = ['logs/bot.log', 'logs/errors.log']
            for log_file in log_files:
                if os.path.exists(log_file):
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            log_content = f.read()
                        zip_file.writestr(f'logs/{os.path.basename(log_file)}', log_content)
                    except Exception as e:
                        logger.error(f"Error reading {log_file}: {e}")
            
            # README fayl qo'shish
            readme_content = f"""# System Backup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Bu fayl quyidagilarni o'z ichiga oladi:
- database_backup.sql: PostgreSQL ma'lumotlar bazasi backup
- logs/bot.log: Bot ishlash loglari
- logs/errors.log: Xatolik loglari

Backup vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            zip_file.writestr('README.txt', readme_content)
        
        # Zip faylni yuklab berish
        zip_buffer.seek(0)
        timestamp = int(datetime.now().timestamp())
        filename = f"system_backup_{timestamp}.zip"
        
        file_to_send = BufferedInputFile(
            zip_buffer.getvalue(), 
            filename=filename
        )
        
        success_text = f"✅ <b>Backup muvaffaqiyatli yaratildi!</b>\n\n📁 Fayl: {filename}\n📅 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" if lang == "uz" else f"✅ <b>Бэкап успешно создан!</b>\n\n📁 Файл: {filename}\n📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await loading_msg.delete()
        await message.answer_document(
            document=file_to_send,
            caption=success_text,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Backup and logs error: {e}", exc_info=True)
        error_text = "❌ Backup yaratishda xatolik yuz berdi" if lang == "uz" else "❌ Ошибка при создании бэкапа"
        await message.answer(error_text)


@router.callback_query(F.data.startswith("admin_export_users_"))
async def admin_export_users(cb: CallbackQuery, state: FSMContext):
    user_type = cb.data.split("_")[-1]  # clients | staff
    await state.update_data(export_type=f"users:{user_type}")
    lang = await get_user_language(cb.from_user.id) or "uz"
    
    # For staff users, go directly to format (no time filter needed)
    if user_type == "staff":
        await state.update_data(time_period="total")
        await cb.message.edit_text(
            ("👥 <b>Xodimlar</b>\n\nBarcha xodimlar export qilinadi.\n\nFormatni tanlang:" if lang == "uz" else "👥 <b>Сотрудники</b>\n\nВсе сотрудники будут экспортированы.\n\nВыберите формат:"),
            reply_markup=get_admin_export_formats_keyboard(lang),
            parse_mode="HTML",
        )
    else:
        # For clients, go directly to format (no time filter for user list)
        await cb.message.edit_text(
            ("👤 <b>Foydalanuvchilar</b>\n\nFormatni tanlang:" if lang == "uz" else "👤 <b>Пользователи</b>\n\nВыберите формат:"),
            reply_markup=get_admin_export_formats_keyboard(lang),
            parse_mode="HTML",
        )
    await cb.answer()


@router.callback_query(F.data == "admin_export_connection")
async def admin_export_connection(cb: CallbackQuery, state: FSMContext):
    await state.update_data(export_type="connection")
    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.message.edit_text(
        ("🔌 <b>Ulanish arizalari</b>\n\nQaysi davr uchun export qilasiz?" if lang == "uz" else "🔌 <b>Заявки на подключение</b>\n\nЗа какой период экспортировать?"),
        reply_markup=get_admin_time_period_keyboard(lang),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "admin_export_technician")
async def admin_export_technician(cb: CallbackQuery, state: FSMContext):
    await state.update_data(export_type="technician")
    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.message.edit_text(
        ("🔧 <b>Texnik arizalar</b>\n\nQaysi davr uchun export qilasiz?" if lang == "uz" else "🔧 <b>Технические заявки</b>\n\nЗа какой период экспортировать?"),
        reply_markup=get_admin_time_period_keyboard(lang),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "admin_export_staff")
async def admin_export_staff(cb: CallbackQuery, state: FSMContext):
    await state.update_data(export_type="staff")
    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.message.edit_text(
        ("👤 <b>Xodim arizalari</b>\n\nQaysi davr uchun export qilasiz?" if lang == "uz" else "👤 <b>Заявки сотрудников</b>\n\nЗа какой период экспортировать?"),
        reply_markup=get_admin_time_period_keyboard(lang),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "admin_export_statistics")
async def admin_export_statistics(cb: CallbackQuery, state: FSMContext):
    await state.update_data(export_type="statistics")
    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.message.edit_text(
        ("📊 <b>Statistika</b>\n\nQaysi davr uchun export qilasiz?" if lang == "uz" else "📊 <b>Статистика</b>\n\nЗа какой период экспортировать?"),
        reply_markup=get_admin_time_period_keyboard(lang),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "admin_export_back_types")
async def admin_export_back_types(cb: CallbackQuery, state: FSMContext):
    """Handle back - go to time period selection or initial export types"""
    data = await state.get_data()
    export_type = data.get("export_type")
    time_period = data.get("time_period")
    lang = await get_user_language(cb.from_user.id) or "uz"
    
    # If we're coming from format selection (time_period is set)
    # and export type needs time filter, go back to time period selection
    # Note: users:staff doesn't need time filter - goes directly to format
    needs_time_filter = export_type in ["connection", "technician", "staff", "statistics"]
    
    if time_period and export_type and needs_time_filter:
        # Remove time_period from state to allow re-selection
        await state.update_data(time_period=None)
        
        keyboard = get_admin_time_period_keyboard(lang)
        
        title_texts = {
            "connection": ("Ulanish arizalari", "Заявки на подключение"),
            "technician": ("Texnik arizalar", "Технические заявки"),
            "staff": ("Xodim arizalari", "Заявки сотрудников"),
            "statistics": ("Statistika", "Статистика"),
        }
        
        title = title_texts.get(export_type, ("Export", "Экспорт"))
        text_title = title[0] if lang == "uz" else title[1]
        emoji = {"connection": "🔌", "technician": "🔧", "staff": "👤", "statistics": "📊"}.get(export_type, "📤")
        
        try:
            await cb.message.edit_text(
                f"{emoji} <b>{text_title}</b>\n\n"
                f"Qaysi davr uchun export qilasiz?" if lang == "uz" else f"За какой период экспортировать?",
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            await cb.answer()
        except Exception:
            await cb.answer("✅", show_alert=False)
    else:
        # Go back to initial export types screen
        await state.update_data(export_type=None, time_period=None)
        await cb.message.edit_text(
            ("📤 <b>Admin eksportlari</b>\n\nKerakli bo'limni tanlang:" if lang == "uz" else "📤 <b>Экспорт администратора</b>\n\nВыберите нужный раздел:"),
            reply_markup=get_admin_export_types_keyboard(lang),
            parse_mode="HTML",
        )
        await cb.answer()


@router.callback_query(F.data == "admin_export_end")
async def admin_export_end(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        pass
    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.answer("Yopildi" if lang == "uz" else "Закрыто")


@router.callback_query(F.data.startswith("admin_time_"))
async def admin_time_period_handler(cb: CallbackQuery, state: FSMContext):
    """Handle time period selection - show format selection"""
    try:
        time_period = cb.data.replace("admin_time_", "")  # today, week, month, total
        export_type = (await state.get_data()).get("export_type", "connection")
        
        # For staff users, always use "total" regardless of selection
        if export_type == "users:staff":
            time_period = "total"
        
        await state.update_data(time_period=time_period)
        
        lang = await get_user_language(cb.from_user.id) or "uz"
        
        # Get period text
        period_texts = {
            "today": ("Bugungi hisobot", "Отчёт за сегодня"),
            "week": ("Haftalik hisobot (Dushanba - {today})", "Недельный отчёт (Понедельник - {today})"),
            "month": ("Oylik hisobot", "Месячный отчёт"),
            "total": ("Jami hisobot", "Общий отчёт")
        }
        
        # Calculate period text
        if time_period == "week":
            from datetime import datetime
            today = datetime.now().strftime("%d.%m.%Y")
            period_text = period_texts["week"][0].format(today=today) if lang == "uz" else period_texts["week"][1].format(today=today)
        else:
            period_text = period_texts[time_period][0] if lang == "uz" else period_texts[time_period][1]
        
        keyboard = get_admin_export_formats_keyboard(lang)
        
        title_texts = {
            "connection": ("Ulanish arizalari", "Заявки на подключение"),
            "technician": ("Texnik arizalar", "Технические заявки"),
            "staff": ("Xodim arizalari", "Заявки сотрудников"),
            "statistics": ("Statistika", "Статистика"),
            "users:clients": ("Foydalanuvchilar (mijozlar)", "Пользователи (клиенты)"),
            "users:staff": ("Xodimlar", "Сотрудники"),
        }
        
        title = title_texts.get(export_type, ("Export", "Экспорт"))
        text_title = title[0] if lang == "uz" else title[1]
        emoji = {"connection": "🔌", "technician": "🔧", "staff": "👤", "statistics": "📊", "users:clients": "👤", "users:staff": "👥"}.get(export_type, "📤")
        
        await cb.message.edit_text(
            f"{emoji} <b>{text_title}</b>\n\n"
            f"📅 Davr: <i>{period_text}</i>\n\n"
            f"Formatni tanlang:" if lang == "uz" else f"Выберите формат:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await cb.answer()
    except Exception as e:
        logger.error(f"Admin time period handler error: {e}")
        await cb.answer("❌ Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("admin_format_"))
async def admin_export_format(cb: CallbackQuery, state: FSMContext):
    format_type = cb.data.split("_")[-1]  # csv | xlsx | docx | pdf
    data = await state.get_data()
    export_type = data.get("export_type", "connection")
    time_period = data.get("time_period", "total")  # today, week, month, total

    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.message.edit_text(("⏳ <b>Eksport tayyorlanmoqda...</b>" if lang == "uz" else "⏳ <b>Экспорт подготавливается...</b>"), parse_mode="HTML")
    
    # State ni tozalash
    await state.clear()

    try:
        title = ""
        filename_base = "export"
        headers = []

        if export_type.startswith("users:"):
            user_type = export_type.split(":")[1]
            raw_data = await get_admin_users_for_export("clients" if user_type == "clients" else "staff")
            title = ("Foydalanuvchilar (mijozlar)" if user_type == "clients" else "Xodimlar") if lang == "uz" else ("Пользователи (клиенты)" if user_type == "clients" else "Сотрудники")
            filename_base = f"users_{user_type}"
            headers = ["ID", "Telegram ID", "Username", "Ism", "Telefon", "Rol", "Yaratilgan", "Yangilangan", "Bloklangan"]
        elif export_type == "connection":
            raw_data = await get_admin_connection_orders_for_export(time_period)
            title = "Ulanish arizalari" if lang == "uz" else "Заявки на подключение"
            filename_base = "connection_orders"
        elif export_type == "technician":
            raw_data = await get_admin_technician_orders_for_export(time_period)
            title = "Texnik arizalar" if lang == "uz" else "Технические заявки"
            filename_base = "technician_orders"
        elif export_type == "staff":
            raw_data = await get_admin_staff_orders_for_export(time_period)
            title = "Xodim arizalari" if lang == "uz" else "Заявки сотрудников"
            filename_base = "staff_orders"
        elif export_type == "warehouse_inventory":
            raw_data = await get_warehouse_inventory_for_export()
            title = "Ombor inventarizatsiyasi" if lang == "uz" else "Инвентаризация склада"
            filename_base = "warehouse_inventory"
            headers = [
                ("ID" if lang == "uz" else "ID"),
                ("Nomi" if lang == "uz" else "Название"),
                ("Seriya raqami" if lang == "uz" else "Серийный №"),
                ("Miqdor" if lang == "uz" else "Количество"),
                ("Narx" if lang == "uz" else "Цена"),
                ("Yaratilgan" if lang == "uz" else "Создано"),
            ]
        elif export_type == "warehouse_stats":
            stats = await get_warehouse_statistics_for_export('all')
            # Convert dict to list format for export
            raw_data = []
            label_key = "Ko'rsatkich" if lang == "uz" else "Показатель"
            value_key = "Qiymat" if lang == "uz" else "Значение"
            raw_data.append({label_key: ("Jami materiallar" if lang == "uz" else "Всего материалов"), value_key: stats.get("total_materials", 0)})
            raw_data.append({label_key: ("Jami miqdor" if lang == "uz" else "Общее количество"), value_key: stats.get("total_quantity", 0)})
            raw_data.append({label_key: ("Jami qiymat" if lang == "uz" else "Общая стоимость"), value_key: stats.get("total_value", 0)})
            raw_data.append({label_key: ("Mavjud materiallar" if lang == "uz" else "Доступные материалы"), value_key: stats.get("available_materials", 0)})
            raw_data.append({label_key: ("Tugagan materiallar" if lang == "uz" else "Завершенные материалы"), value_key: stats.get("out_of_stock", 0)})
            raw_data.append({label_key: ("Kam qolgan materiallar" if lang == "uz" else "Материалы с низким запасом"), value_key: stats.get("low_stock", 0)})
            title = "Ombor statistikasi" if lang == "uz" else "Статистика склада"
            filename_base = "warehouse_statistics"
        elif export_type == "statistics":
            stats = await get_admin_statistics_for_export(time_period)
            # Flatten to rows
            raw_data = []
            label_key = "Ko'rsatkich" if lang == "uz" else "Показатель"
            value_key = "Qiymat" if lang == "uz" else "Значение"
            raw_data.append({label_key: ("Jami foydalanuvchilar" if lang == "uz" else "Всего пользователей"), value_key: stats.get("total_users", 0)})
            raw_data.append({label_key: ("Faol ulanish arizalari" if lang == "uz" else "Активные заявки на подключение"), value_key: stats.get("active_connections", 0)})
            raw_data.append({label_key: ("Faol texnik arizalar" if lang == "uz" else "Активные технические заявки"), value_key: stats.get("active_technician", 0)})
            raw_data.append({label_key: ("Faol xodim arizalari" if lang == "uz" else "Активные заявки сотрудников"), value_key: stats.get("active_staff", 0)})
            raw_data.append({label_key: ("Jami materiallar" if lang == "uz" else "Всего материалов"), value_key: stats.get("total_materials", 0)})
            title = "Statistika" if lang == "uz" else "Статистика"
            filename_base = "statistics"
            headers = (["Ko'rsatkich", "Qiymat"] if lang == "uz" else ["Показатель", "Значение"])
        else:
            raw_data = []

        export_utils = ExportUtils()

        if format_type == "csv":
            file_data = export_utils.to_csv(raw_data, headers=headers if headers else None)
            file_to_send = BufferedInputFile(file_data.getvalue(), filename=f"{filename_base}_{int(datetime.now().timestamp())}.csv")
        elif format_type == "xlsx":
            file_data = export_utils.generate_excel(raw_data, sheet_name="export", title=title)
            file_to_send = BufferedInputFile(file_data.getvalue(), filename=f"{filename_base}_{int(datetime.now().timestamp())}.xlsx")
        elif format_type == "docx":
            file_data = export_utils.generate_word(raw_data, title=title)
            file_to_send = BufferedInputFile(file_data.getvalue(), filename=f"{filename_base}_{int(datetime.now().timestamp())}.docx")
        elif format_type == "pdf":
            file_data = export_utils.generate_pdf(raw_data, title=title)
            file_to_send = BufferedInputFile(file_data.getvalue(), filename=f"{filename_base}_{int(datetime.now().timestamp())}.pdf")
        else:
            await cb.answer("Format noto'g'ri", show_alert=True)
            return

        # Format caption with time period (if applicable)
        if export_type.startswith("users:"):
            caption_text = f"📤 {title} — {format_type.upper()}"
        else:
            period_texts = {
                "today": ("Bugun", "Сегодня"),
                "week": ("Hafta (Dushanba - hozirgi)", "Неделя (Понедельник - сейчас)"),
                "month": ("Oy", "Месяц"),
                "total": ("Jami", "Всего")
            }
            period_text = period_texts.get(time_period, ("Jami", "Всего"))[0] if lang == "uz" else period_texts.get(time_period, ("Jami", "Всего"))[1]
            from datetime import datetime
            caption_text = f"📤 {title}\n📅 Davr: {period_text}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n✅ Muvaffaqiyatli yuklab olindi!" if lang == "uz" else f"📤 {title}\n📅 Период: {period_text}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n✅ Успешно загружено!"
        
        await cb.message.answer_document(
            document=file_to_send,
            caption=caption_text,
        )

        await cb.message.answer(
            ("Yana qaysi bo'limni eksport qilamiz?" if lang == "uz" else "Что экспортируем дальше?"),
            reply_markup=get_admin_export_types_keyboard(lang),
        )

    except Exception as e:
        logger.error(f"Admin export error: {e}", exc_info=True)
        await cb.message.answer("❌ Eksportda xatolik yuz berdi")
    finally:
        await cb.answer()


# Warehouse specific selections -> format selection
@router.callback_query(F.data == "admin_export_warehouse_inventory")
async def admin_export_wh_inventory(cb: CallbackQuery, state: FSMContext):
    await state.update_data(export_type="warehouse_inventory")
    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.message.edit_text(
        ("📦 <b>Ombor inventarizatsiyasi</b>\n\nFormatni tanlang:" if lang == "uz" else "📦 <b>Инвентаризация склада</b>\n\nВыберите формат:"),
        reply_markup=get_admin_export_formats_keyboard(lang),
        parse_mode="HTML",
    )
    await cb.answer()

@router.callback_query(F.data == "admin_export_warehouse_stats")
async def admin_export_wh_stats(cb: CallbackQuery, state: FSMContext):
    await state.update_data(export_type="warehouse_stats")
    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.message.edit_text(
        ("📊 <b>Ombor statistikasi</b>\n\nFormatni tanlang:" if lang == "uz" else "📊 <b>Статистика склада</b>\n\nВыберите формат:"),
        reply_markup=get_admin_export_formats_keyboard(lang),
        parse_mode="HTML",
    )
    await cb.answer()

@router.callback_query(F.data == "admin_export_warehouse_low_stock")
async def admin_export_wh_low(cb: CallbackQuery, state: FSMContext):
    await state.update_data(export_type="warehouse_low_stock")
    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.message.edit_text(
        ("⚠️ <b>Kam zaxira</b>\n\nFormatni tanlang:" if lang == "uz" else "⚠️ <b>Низкий остаток</b>\n\nВыберите формат:"),
        reply_markup=get_admin_export_formats_keyboard(lang),
        parse_mode="HTML",
    )
    await cb.answer()

@router.callback_query(F.data == "admin_export_warehouse_out_of_stock")
async def admin_export_wh_oos(cb: CallbackQuery, state: FSMContext):
    await state.update_data(export_type="warehouse_out_of_stock")
    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.message.edit_text(
        ("⛔ <b>Zaxira tugagan</b>\n\nFormatni tanlang:" if lang == "uz" else "⛔ <b>Нет в наличии</b>\n\nВыберите формат:"),
        reply_markup=get_admin_export_formats_keyboard(lang),
        parse_mode="HTML",
    )
    await cb.answer()
