from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from keyboards.warehouse_buttons import get_warehouse_export_types_keyboard, get_warehouse_export_formats_keyboard
from database.warehouse.materials import (
    get_warehouse_inventory_for_export,
)
from database.warehouse.statistics import (
    get_warehouse_statistics_for_export,
)
from utils.export_utils import ExportUtils
from database.basic.language import get_user_language
from states.warehouse_states import WarehouseStates
import logging
from filters.role_filter import RoleFilter

router = Router()
router.message.filter(RoleFilter(role="warehouse"))
logger = logging.getLogger(__name__)

@router.message(F.text.in_(["📤 Export", "📤 Экспорт"]))
async def export_handler(message: Message, state: FSMContext):
    """Main export handler - shows export types"""
    lang = await get_user_language(message.from_user.id) or "uz"
    
    try:
        await state.clear()
        keyboard = get_warehouse_export_types_keyboard(lang)
        
        if lang == "ru":
            text = (
                "📤 <b>Экспорт данных</b>\n\n"
                "Выберите один из следующих типов экспорта:\n\n"
                "📦 <b>Инвентаризация</b> - Список всех материалов\n"
                "📊 <b>Статистика</b> - Статистика склада\n\n"
                "👤 <b>Роль:</b> Склад"
            )
        else:
            text = (
                "📤 <b>Ma'lumotlarni Export qilish</b>\n\n"
                "Quyidagi export turlaridan birini tanlang:\n\n"
                "📦 <b>Inventarizatsiya</b> - Barcha materiallar ro'yxati\n"
                "📊 <b>Statistika</b> - Ombor statistikasi\n\n"
                "👤 <b>Rol:</b> Ombor"
            )
        
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Export handler error: {e}")
        if lang == "ru":
            await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")
        else:
            await message.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

@router.callback_query(F.data == "warehouse_export_inventory")
async def export_inventory_handler(callback: CallbackQuery, state: FSMContext):
    """Handle inventory export selection"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    
    try:
        await state.update_data(export_type="inventory")
        keyboard = get_warehouse_export_formats_keyboard(lang)
        
        if lang == "ru":
            text = (
                "📦 <b>Экспорт инвентаризации</b>\n\n"
                "Выберите формат экспорта:\n\n"
                "• <b>CSV</b> - Табличный формат\n"
                "• <b>Excel</b> - Microsoft Excel\n"
                "• <b>Word</b> - Microsoft Word\n"
                "• <b>PDF</b> - Portable Document Format"
            )
        else:
            text = (
                "📦 <b>Inventarizatsiya Export</b>\n\n"
                "Export formatini tanlang:\n\n"
                "• <b>CSV</b> - Jadval formati\n"
                "• <b>Excel</b> - Microsoft Excel\n"
                "• <b>Word</b> - Microsoft Word\n"
                "• <b>PDF</b> - Portable Document Format"
            )
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Export inventory handler error: {e}")
        if lang == "ru":
            await callback.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await callback.answer("❌ Xatolik yuz berdi", show_alert=True)

@router.callback_query(F.data == "warehouse_export_statistics")
async def export_statistics_handler(callback: CallbackQuery, state: FSMContext):
    """Handle statistics export selection"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    
    try:
        await state.update_data(export_type="statistics")
        keyboard = get_warehouse_export_formats_keyboard(lang)
        
        if lang == "ru":
            text = (
                "📊 <b>Экспорт статистики</b>\n\n"
                "Выберите формат экспорта:\n\n"
                "• <b>CSV</b> - Табличный формат\n"
                "• <b>Excel</b> - Microsoft Excel\n"
                "• <b>Word</b> - Microsoft Word\n"
                "• <b>PDF</b> - Portable Document Format"
            )
        else:
            text = (
                "📊 <b>Statistika Export</b>\n\n"
                "Export formatini tanlang:\n\n"
                "• <b>CSV</b> - Jadval formati\n"
                "• <b>Excel</b> - Microsoft Excel\n"
                "• <b>Word</b> - Microsoft Word\n"
                "• <b>PDF</b> - Portable Document Format"
            )
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Export statistics handler error: {e}")
        if lang == "ru":
            await callback.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await callback.answer("❌ Xatolik yuz berdi", show_alert=True)

@router.callback_query(F.data.startswith("warehouse_format_"))
async def export_format_handler(callback: CallbackQuery, state: FSMContext):
    """Handle export format selection and generate file"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    
    try:
        format_type = callback.data.split("_")[-1]  # csv, xlsx, docx, pdf
        data = await state.get_data()
        export_type = data.get("export_type", "inventory")
        
        # Show processing message
        if lang == "ru":
            await callback.message.edit_text(
                "⏳ <b>Процесс экспорта...</b>\n\n"
                "Данные подготавливаются, пожалуйста, подождите...",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "⏳ <b>Export jarayoni...</b>\n\n"
                "Ma'lumotlar tayyorlanmoqda, iltimos kuting...",
                parse_mode="HTML"
            )
        
        # Get data based on export type
        if export_type == "inventory":
            raw_data = await get_warehouse_inventory_for_export()
            if lang == "ru":
                title = "Отчет по инвентаризации склада"
                filename_base = "sklad_inventarizatsiya"
            else:
                title = "Ombor Inventarizatsiya Hisoboti"
                filename_base = "ombor_inventarizatsiya"
        elif export_type == "statistics":
            raw_data = await get_warehouse_statistics_for_export()
            if lang == "ru":
                title = "Статистический отчет склада"
                filename_base = "sklad_statistika"
            else:
                title = "Ombor Statistika Hisoboti"
                filename_base = "ombor_statistika"
        else:
            raw_data = []
            if lang == "ru":
                title = "Отчет склада"
                filename_base = "sklad_hisoboti"
            else:
                title = "Ombor Hisoboti"
                filename_base = "ombor_hisoboti"
        
        if not raw_data:
            if lang == "ru":
                await callback.message.edit_text(
                    "❌ <b>Данные не найдены</b>\n\n"
                    "Нет данных для экспорта.",
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text(
                    "❌ <b>Ma'lumot topilmadi</b>\n\n"
                    "Export qilish uchun ma'lumotlar mavjud emas.",
                    parse_mode="HTML"
                )
            await callback.answer()
            return
        
        # Format data for export
        formatted_data = ExportUtils.format_data_for_export(raw_data, export_type)
        
        # Generate file based on format
        if format_type == "csv":
            file_content = ExportUtils.generate_csv(formatted_data)
            filename = ExportUtils.get_filename_with_timestamp(filename_base, "csv")
            document = BufferedInputFile(
                file_content.getvalue(),
                filename=filename
            )
        elif format_type == "xlsx":
            if lang == "ru":
                file_content = ExportUtils.generate_excel(formatted_data, "Данные склада", title)
            else:
                file_content = ExportUtils.generate_excel(formatted_data, "Ombor Ma'lumotlari", title)
            filename = ExportUtils.get_filename_with_timestamp(filename_base, "xlsx")
            document = BufferedInputFile(
                file_content.getvalue(),
                filename=filename
            )
        elif format_type == "docx":
            file_content = ExportUtils.generate_word(formatted_data, title)
            filename = ExportUtils.get_filename_with_timestamp(filename_base, "docx")
            document = BufferedInputFile(
                file_content.getvalue(),
                filename=filename
            )
        elif format_type == "pdf":
            file_content = ExportUtils.generate_pdf(formatted_data, title)
            filename = ExportUtils.get_filename_with_timestamp(filename_base, "pdf")
            document = BufferedInputFile(
                file_content.getvalue(),
                filename=filename
            )
        else:
            if lang == "ru":
                await callback.message.edit_text(
                    "❌ <b>Неверный формат</b>\n\n"
                    "Выбранный формат не поддерживается.",
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text(
                    "❌ <b>Noto'g'ri format</b>\n\n"
                    "Tanlangan format qo'llab-quvvatlanmaydi.",
                    parse_mode="HTML"
                )
            await callback.answer()
            return
        
        # Send the file
        if lang == "ru":
            caption = (
                f"📄 <b>{title}</b>\n\n"
                f"📊 Количество данных: {len(formatted_data)}\n"
                f"📅 Создан: {ExportUtils.get_filename_with_timestamp('', '').split('_')[1][:8]}\n"
                f"📁 Формат: {format_type.upper()}\n\n"
                f"✅ Экспорт успешно завершен!"
            )
        else:
            caption = (
                f"📄 <b>{title}</b>\n\n"
                f"📊 Ma'lumotlar soni: {len(formatted_data)}\n"
                f"📅 Yaratilgan: {ExportUtils.get_filename_with_timestamp('', '').split('_')[1][:8]}\n"
                f"📁 Format: {format_type.upper()}\n\n"
                f"✅ Export muvaffaqiyatli yakunlandi!"
            )
        
        await callback.message.answer_document(
            document=document,
            caption=caption,
            parse_mode="HTML"
        )
        
        # Clear the processing message
        await callback.message.delete()
        
        if lang == "ru":
            await callback.answer("✅ Экспорт готов!")
        else:
            await callback.answer("✅ Export tayyor!")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Export format handler error: {e}")
        if lang == "ru":
            await callback.message.edit_text(
                "❌ <b>Ошибка экспорта</b>\n\n"
                "Произошла ошибка при создании файла. Попробуйте еще раз.",
                parse_mode="HTML"
            )
            await callback.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await callback.message.edit_text(
                "❌ <b>Export xatoligi</b>\n\n"
                "Fayl yaratishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.",
                parse_mode="HTML"
            )
            await callback.answer("❌ Xatolik yuz berdi", show_alert=True)

@router.callback_query(F.data == "warehouse_export_back_types")
async def export_back_to_types_handler(callback: CallbackQuery, state: FSMContext):
    """Go back to export types selection"""
    lang = await get_user_language(callback.from_user.id) or "uz"
    
    try:
        keyboard = get_warehouse_export_types_keyboard(lang)
        
        if lang == "ru":
            text = (
                "📤 <b>Экспорт данных</b>\n\n"
                "Выберите один из следующих типов экспорта:\n\n"
                "📦 <b>Инвентаризация</b> - Список всех материалов\n"
                "📊 <b>Статистика</b> - Статистика склада\n\n"
                "👤 <b>Роль:</b> Склад"
            )
        else:
            text = (
                "📤 <b>Ma'lumotlarni Export qilish</b>\n\n"
                "Quyidagi export turlaridan birini tanlang:\n\n"
                "📦 <b>Inventarizatsiya</b> - Barcha materiallar ro'yxati\n"
                "📊 <b>Statistika</b> - Ombor statistikasi\n\n"
                "👤 <b>Rol:</b> Ombor"
            )
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Export back handler error: {e}")
        if lang == "ru":
            await callback.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await callback.answer("❌ Xatolik yuz berdi", show_alert=True)
