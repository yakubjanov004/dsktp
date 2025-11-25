from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from keyboards.manager_buttons import (
    get_manager_export_types_keyboard, 
    get_manager_export_formats_keyboard,
    get_manager_time_period_keyboard
)
from database.manager.export import (
    get_manager_connection_orders_for_export,
    get_manager_statistics_for_export,
    get_manager_employees_for_export
)
from utils.export_utils import ExportUtils
from utils.universal_error_logger import get_universal_logger, log_error
from states.manager_states import ManagerExportStates
from database.basic.language import get_user_language
import logging
from filters.role_filter import RoleFilter
from datetime import datetime

router = Router()
router.message.filter(RoleFilter("manager"))
logger = get_universal_logger("ManagerExport")

@router.message(F.text.in_(["📤 Export", "📤 Экспорт"]))
async def export_handler(message: Message, state: FSMContext):
    """Main export handler - shows export types"""
    try:
        await state.clear()
        lang = await get_user_language(message.from_user.id) or "uz"
        keyboard = get_manager_export_types_keyboard(lang)
        
        if lang == "uz":
            text = "📊 <b>Menejerlar uchun hisobotlar</b>\n\nQuyidagi hisobot turlaridan birini tanlang:"
        else:
            text = "📊 <b>Отчеты для менеджеров</b>\n\nВыберите один из типов отчетов:"
            
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Export handler error: {e}")
        lang = await get_user_language(message.from_user.id) or "uz"
        error_text = "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте снова."
        await message.answer(error_text)

@router.callback_query(F.data == "manager_export_orders")
async def export_orders_handler(callback: CallbackQuery, state: FSMContext):
    """Handle orders export selection - show time period selection"""
    try:
        await state.update_data(export_type="orders")
        lang = await get_user_language(callback.from_user.id) or "uz"
        keyboard = get_manager_time_period_keyboard(lang)
        
        if lang == "uz":
            text = "📋 <b>Buyurtmalar ro'yxati</b>\n\nQaysi davr uchun export qilasiz?"
        else:
            text = "📋 <b>Список заказов</b>\n\nЗа какой период экспортировать?"
            
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Export orders handler error: {e}")
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)

@router.callback_query(F.data == "manager_export_statistics")
async def export_statistics_handler(callback: CallbackQuery, state: FSMContext):
    """Handle statistics export selection - show time period selection"""
    try:
        await state.update_data(export_type="statistics")
        lang = await get_user_language(callback.from_user.id) or "uz"
        keyboard = get_manager_time_period_keyboard(lang)
        
        if lang == "uz":
            text = "📊 <b>Statistika hisoboti</b>\n\nQaysi davr uchun export qilasiz?"
        else:
            text = "📊 <b>Статистический отчет</b>\n\nЗа какой период экспортировать?"
            
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Export statistics handler error: {e}")
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)

@router.callback_query(F.data == "manager_export_employees")
async def export_employees_handler(callback: CallbackQuery, state: FSMContext):
    """Handle employees export selection - go directly to format selection"""
    try:
        await state.update_data(export_type="employees", time_period="total")
        lang = await get_user_language(callback.from_user.id) or "uz"
        keyboard = get_manager_export_formats_keyboard(lang)
        
        if lang == "uz":
            text = "👥 <b>Xodimlar ro'yxati</b>\n\nBarcha xodimlar (Managerlar va Junior Managerlar) export qilinadi.\n\nExport formatini tanlang:"
        else:
            text = "👥 <b>Список сотрудников</b>\n\nВсе сотрудники (Менеджеры и Младшие менеджеры) будут экспортированы.\n\nВыберите формат экспорта:"
            
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Export employees handler error: {e}")
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("manager_time_"))
async def export_time_period_handler(callback: CallbackQuery, state: FSMContext):
    """Handle time period selection - show format selection"""
    try:
        time_period = callback.data.replace("manager_time_", "")  # today, week, month, total
        export_type = (await state.get_data()).get("export_type", "orders")
        
        # For employees, always use "total" regardless of selection
        if export_type == "employees":
            time_period = "total"
        
        await state.update_data(time_period=time_period)
        
        lang = await get_user_language(callback.from_user.id) or "uz"
        
        # Get period text
        period_texts = {
            "today": ("Bugungi hisobot", "Отчёт за сегодня"),
            "week": ("Haftalik hisobot (Dushanba - {today})", "Недельный отчёт (Понедельник - {today})"),
            "month": ("Oylik hisobot", "Месячный отчёт"),
            "total": ("Jami hisobot", "Общий отчёт")
        }
        
        export_type = (await state.get_data()).get("export_type", "orders")
        
        # Calculate period text
        if time_period == "week":
            today = datetime.now().strftime("%d.%m.%Y")
            period_text = period_texts["week"][0].format(today=today) if lang == "uz" else period_texts["week"][1].format(today=today)
        else:
            period_text = period_texts[time_period][0] if lang == "uz" else period_texts[time_period][1]
        
        keyboard = get_manager_export_formats_keyboard(lang)
        
        title_text = {
            "orders": ("Buyurtmalar ro'yxati", "Список заказов"),
            "statistics": ("Statistika hisoboti", "Статистический отчёт"),
            "employees": ("Xodimlar ro'yxati", "Список сотрудников")
        }.get(export_type, ("Export", "Экспорт"))
        
        title = title_text[0] if lang == "uz" else title_text[1]
        emoji = {"orders": "📋", "statistics": "📊", "employees": "👥"}.get(export_type, "📤")
        
        await callback.message.edit_text(
            f"{emoji} <b>{title}</b>\n\n"
            f"📅 Davr: <i>{period_text}</i>\n\n"
            f"Export formatini tanlang:" if lang == "uz" else f"Экспорт формата:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Export time period handler error: {e}")
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)

@router.callback_query(F.data.startswith("manager_format_"))
async def export_format_handler(callback: CallbackQuery, state: FSMContext):
    """Handle export format selection and generate file"""
    try:
        format_type = callback.data.split("_")[-1]  # csv, xlsx, docx, pdf
        data = await state.get_data()
        export_type = data.get("export_type", "orders")
        time_period = data.get("time_period", "total")  # today, week, month, total
        lang = await get_user_language(callback.from_user.id) or "uz"
        
        # Get data based on export type
        if export_type == "orders":
            raw_data = await get_manager_connection_orders_for_export(time_period)
            if lang == "uz":
                title = "Buyurtmalar ro'yxati"
                filename_base = "buyurtmalar"
                headers = ["ID", "Buyurtma raqami", "Mijoz ismi", "Telefon", "Mijoz abonent ID", "Hudud", "Manzil", "Uzunlik", "Kenglik", "Tarif", "Tarif rasmi", "Ulanish sanasi", "Yangilangan sana", "Holati", "Reyting", "Izohlar", "JM izohlar", "Menejer", "Menejer telefon", "Akt raqami", "Akt fayl yo'li", "Akt yaratilgan", "Mijozga yuborilgan", "Akt reytingi", "Akt izohi"]
            else:
                title = "Список заказов"
                filename_base = "zakazy"
                headers = ["ID", "Номер заказа", "Имя клиента", "Телефон", "ID клиента", "Регион", "Адрес", "Долгота", "Широта", "Тариф", "Изображение тарифа", "Дата подключения", "Дата обновления", "Статус", "Рейтинг", "Комментарии", "Комментарии JM", "Менеджер", "Телефон менеджера", "Номер акта", "Путь к файлу акта", "Акт создан", "Отправлено клиенту", "Рейтинг акта", "Комментарий акта"]
            
        elif export_type == "statistics":
            stats = await get_manager_statistics_for_export(time_period)
            if lang == "uz":
                title = "Statistika hisoboti"
                filename_base = "statistika"
                headers = ["Ko'rsatkich", "Qiymat"]
            else:
                title = "Статистический отчет"
                filename_base = "statistika"
                headers = ["Показатель", "Значение"]
            raw_data = []

            def add_row_dict(label: str, value: str):
                raw_data.append({headers[0]: label, headers[1]: value})

            def add_section(title_text: str):
                # blank line, section header, divider
                raw_data.append({headers[0]: "", headers[1]: ""})
                raw_data.append({headers[0]: f"🔹 {title_text.upper()}", headers[1]: ""})
                raw_data.append({headers[0]: "-" * 30, headers[1]: "-" * 30})

            # 1) Umumiy statistika
            if lang == "uz":
                add_section("Umumiy statistika")
                add_row_dict("📊 Jami buyurtmalar:", str(stats['summary']['total_orders']))
                add_row_dict("🆕 Yangi arizalar:", str(stats['summary']['new_orders']))
                add_row_dict("🔄 Jarayondagi arizalar:", str(stats['summary']['in_progress_orders']))
                add_row_dict("✅ Yakunlangan arizalar:", str(stats['summary']['completed_orders']))
                add_row_dict("📈 Yakunlangan arizalar foizi:", f"{stats['summary']['completion_rate']}%")
                add_row_dict("👥 Yagona mijozlar:", str(stats['summary']['unique_clients']))
                add_row_dict("📋 Foydalanilgan tarif rejalari:", str(stats['summary']['unique_tariffs_used']))
            else:
                add_section("Общая статистика")
                add_row_dict("📊 Всего заказов:", str(stats['summary']['total_orders']))
                add_row_dict("🆕 Новые заявки:", str(stats['summary']['new_orders']))
                add_row_dict("🔄 Заявки в процессе:", str(stats['summary']['in_progress_orders']))
                add_row_dict("✅ Завершенные заявки:", str(stats['summary']['completed_orders']))
                add_row_dict("📈 Процент завершенных:", f"{stats['summary']['completion_rate']}%")
                add_row_dict("👥 Уникальные клиенты:", str(stats['summary']['unique_clients']))
                add_row_dict("📋 Использованные тарифы:", str(stats['summary']['unique_tariffs_used']))

            # 2) Menejerlar bo'yicha statistika
            if stats['by_manager']:
                add_section("Menejerlar bo'yicha statistika")
                for i, manager in enumerate(stats['by_manager'], 1):
                    manager_title = f"👤 {i}. {manager['manager_name']}"
                    phone = manager['manager_phone'] or "Tel. yo'q"
                    add_row_dict(manager_title, "")
                    add_row_dict("  📞 Telefon:", str(phone))
                    add_row_dict("  📊 Jami buyurtmalar:", str(manager['total_orders']))
                    add_row_dict("  ✅ Yakunlangan:", str(manager['completed_orders']))
                    raw_data.append({headers[0]: "", headers[1]: ""})

            # 3) Oylik statistika
            if stats['monthly_trends']:
                add_section("Oylik statistika (6 oy)")
                for month_data in stats['monthly_trends']:
                    month = month_data['month']
                    add_row_dict(f"🗓️ {month}:", "")
                    add_row_dict("  📊 Jami:", str(month_data['total_orders']))
                    add_row_dict("  🆕 Yangi:", str(month_data['new_orders']))
                    add_row_dict("  ✅ Yakunlangan:", str(month_data['completed_orders']))

            # 4) Tarif rejalari bo'yicha statistika
            if stats['by_tariff']:
                add_section("Tarif rejalari bo'yicha statistika")
                for tariff in stats['by_tariff']:
                    add_row_dict(f"📋 {tariff['tariff_name']}", "")
                    add_row_dict("  📊 Buyurtmalar soni:", str(tariff['total_orders']))
                    add_row_dict("  👥 Mijozlar soni:", str(tariff['unique_clients']))

            # 5) So'nggi faollik
            if stats['recent_activity']:
                add_section("So'nggi faollik (30 kun)")
                for activity in stats['recent_activity']:
                    if activity['recent_orders'] > 0:
                        last_active = activity['last_activity'].strftime('%Y-%m-%d')
                        add_row_dict(f"👤 {activity['manager_name']}", f"📅 So'nggi: {last_active}")
                        add_row_dict("  📊 Arizalar soni:", str(activity['recent_orders']))
            
        elif export_type == "employees":
            raw_data = await get_manager_employees_for_export()
            if lang == "uz":
                title = "Xodimlar ro'yxati"
                filename_base = "xodimlar"
                headers = ["ID", "Ism-sharif", "Telefon", "Lavozim", "Holati", "Qo'shilgan sana"]
            else:
                title = "Список сотрудников"
                filename_base = "sotrudniki"
                headers = ["ID", "ФИО", "Телефон", "Должность", "Статус", "Дата добавления"]
        
        else:
            error_text = "❌ Noto'g'ri hisobot turi" if lang == "uz" else "❌ Неверный тип отчета"
            await callback.message.answer(error_text)
            return
        
        # Ensure data is in the correct format (list of dicts)
        if not isinstance(raw_data, list):
            raw_data = [raw_data] if raw_data is not None else []

        if raw_data and not isinstance(raw_data[0], dict):
            # If we have headers and rows are sequences, map by headers
            if 'headers' in locals() and headers and isinstance(raw_data[0], (list, tuple)):
                raw_data = [
                    {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
                    for row in raw_data
                ]
            elif all(hasattr(item, '_asdict') for item in raw_data):
                raw_data = [dict(row) for row in raw_data]
            else:
                raw_data = [{"value": str(item)} for item in raw_data]
        
        # Generate file based on format
        export_utils = ExportUtils()
        file_data = None
        
        try:
            if format_type == "csv":
                if not raw_data:
                    raise ValueError("No data to export")
                file_data = export_utils.to_csv(raw_data, headers=headers)
                file_to_send = BufferedInputFile(
                    file_data.getvalue(), 
                    filename=f"export_{int(datetime.now().timestamp())}.csv"
                )
            elif format_type == "xlsx":
                file_data = export_utils.generate_excel(raw_data, sheet_name=export_type, title=title)
                file_to_send = BufferedInputFile(
                    file_data.getvalue(), 
                    filename=f"export_{int(datetime.now().timestamp())}.xlsx"
                )
            elif format_type == "docx":
                file_data = export_utils.generate_word(raw_data, title=title)
                file_to_send = BufferedInputFile(
                    file_data.getvalue(), 
                    filename=f"export_{int(datetime.now().timestamp())}.docx"
                )
            elif format_type == "pdf":
                file_data = export_utils.generate_pdf(raw_data, title=title)
                file_to_send = BufferedInputFile(
                    file_data.getvalue(), 
                    filename=f"export_{int(datetime.now().timestamp())}.pdf"
                )
            else:
                error_text = "❌ Noto'g'ri format" if lang == "uz" else "❌ Неверный формат"
                await callback.message.answer(error_text)
                return
        except Exception as e:
            logger.error(f"Error generating file: {e}")
            error_text = "❌ Fayl yaratishda xatolik yuz berdi" if lang == "uz" else "❌ Ошибка при создании файла"
            await callback.message.answer(error_text)
            return
        
        # Send the file
        try:
            # Format caption with time period (if applicable)
            if export_type == "employees":
                caption_text = f"📤 {title}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n✅ Muvaffaqiyatli yuklab olindi!" if lang == "uz" else f"📤 {title}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n✅ Успешно загружено!"
            else:
                period_texts = {
                    "today": ("Bugun", "Сегодня"),
                    "week": ("Hafta (Dushanba - hozirgi)", "Неделя (Понедельник - сейчас)"),
                    "month": ("Oy", "Месяц"),
                    "total": ("Jami", "Всего")
                }
                period_text = period_texts.get(time_period, ("Jami", "Всего"))[0] if lang == "uz" else period_texts.get(time_period, ("Jami", "Всего"))[1]
                caption_text = f"📤 {title}\n📅 Davr: {period_text}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n✅ Muvaffaqiyatli yuklab olindi!" if lang == "uz" else f"📤 {title}\n📅 Период: {period_text}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n✅ Успешно загружено!"
            
            await callback.message.answer_document(
                document=file_to_send,
                caption=caption_text,
                disable_notification=True
            )
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            error_text = "❌ Fayl yuborishda xatolik yuz berdi" if lang == "uz" else "❌ Ошибка при отправке файла"
            await callback.message.answer(error_text)
            
        # Remove the inline keyboard
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except:
            pass
            
    except Exception as e:
        log_error(e, "Manager export format handler", callback.from_user.id)
        await callback.message.answer("❌ Hisobot yaratishda xatolik yuz berdi")
    finally:
        await callback.answer()

@router.callback_query(F.data == "manager_export_back_types")
async def export_back_to_types_handler(callback: CallbackQuery, state: FSMContext):
    """Handle back - go to time period selection or initial export types"""
    try:
        data = await state.get_data()
        export_type = data.get("export_type")
        time_period = data.get("time_period")
        lang = await get_user_language(callback.from_user.id) or "uz"
        
        # If we're coming from format selection (time_period is set) and it's not employees,
        # go back to time period selection
        if time_period and export_type and export_type != "employees":
            # Remove time_period from state to allow re-selection
            await state.update_data(time_period=None)
            
            keyboard = get_manager_time_period_keyboard(lang)
            
            title_text = {
                "orders": ("Buyurtmalar ro'yxati", "Список заказов"),
                "statistics": ("Statistika hisoboti", "Статистический отчёт")
            }.get(export_type, ("Export", "Экспорт"))
            
            title = title_text[0] if lang == "uz" else title_text[1]
            emoji = {"orders": "📋", "statistics": "📊"}.get(export_type, "📤")
            
            edited = False
            try:
                await callback.message.edit_text(
                    f"{emoji} <b>{title}</b>\n\n"
                    f"Qaysi davr uchun export qilasiz?" if lang == "uz" else f"За какой период экспортировать?",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                edited = True
            except Exception as edit_error:
                if "message is not modified" in str(edit_error):
                    pass
                else:
                    raise edit_error
            
            if not edited:
                await callback.answer("✅", show_alert=False)
            else:
                await callback.answer()
        else:
            # Go back to initial export types screen
            await state.clear()
            lang = await get_user_language(callback.from_user.id) or "uz"
            keyboard = get_manager_export_types_keyboard(lang)
            
            if lang == "uz":
                text = "📊 <b>Menejerlar uchun hisobotlar</b>\n\nQuyidagi hisobot turlaridan birini tanlang:"
            else:
                text = "📊 <b>Отчеты для менеджеров</b>\n\nВыберите один из типов отчетов:"
            
            edited = False
            try:
                await callback.message.edit_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                edited = True
            except Exception as edit_error:
                if "message is not modified" in str(edit_error):
                    pass
                else:
                    raise edit_error
            
            if not edited:
                await callback.answer("✅", show_alert=False)
            else:
                await callback.answer()
    except Exception as e:
        logger.error(f"Export back handler error: {e}")
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)

@router.callback_query(F.data == "manager_export_end")
async def export_end_handler(callback: CallbackQuery, state: FSMContext):
    """End export session"""
    try:
        await state.clear()
        await callback.message.delete()
        await callback.answer("📊 Hisobot oynasi yopildi", show_alert=False)
    except Exception as e:
        logger.error(f"Export end handler error: {e}")
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)