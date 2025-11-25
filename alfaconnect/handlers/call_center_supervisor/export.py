from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from aiogram.fsm.context import FSMContext
from filters.role_filter import RoleFilter

from keyboards.call_center_supervisor_buttons import (
    get_ccs_export_types_keyboard,
    get_ccs_export_formats_keyboard,
    get_ccs_time_period_keyboard,
)
from database.call_center_supervisor.export import (
    get_ccs_connection_orders_for_export,
    get_ccs_operator_orders_for_export,
    get_ccs_operators_for_export,
    get_ccs_statistics_for_export
)
from utils.export_utils import ExportUtils
from database.basic.language import get_user_language
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(RoleFilter("callcenter_supervisor"))

@router.message(F.text.in_(["📤 Export", "📤 Экспорт"]))
async def export_handler(message: Message, state: FSMContext):
    """Handle export button click"""
    await state.clear()
    lang = await get_user_language(message.from_user.id) or "uz"
    await message.answer(
        ("📤 <b>Call Center Supervisor eksportlari</b>\n\nKerakli bo'limni tanlang:" if lang == "uz" else "📤 <b>Экспорт супервайзера колл-центра</b>\n\nВыберите нужный раздел:"),
        reply_markup=get_ccs_export_types_keyboard(lang),
        parse_mode="HTML",
    )

@router.callback_query(F.data == "ccs_export_operator_orders")
async def export_operator_orders(cb: CallbackQuery, state: FSMContext):
    await state.update_data(export_type="operator_orders")
    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.message.edit_text(
        ("📋 <b>Operatorlar ochgan arizalar</b>\n\nQaysi davr uchun export qilasiz?" if lang == "uz" else "📋 <b>Заявки операторов</b>\n\nЗа какой период экспортировать?"),
        reply_markup=get_ccs_time_period_keyboard(lang),
        parse_mode="HTML",
    )
    await cb.answer()

@router.callback_query(F.data == "ccs_export_operators")
async def export_operators(cb: CallbackQuery, state: FSMContext):
    await state.update_data(export_type="operators", time_period="total")
    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.message.edit_text(
        ("👥 <b>Operatorlar</b>\n\nBarcha Call Center operatorlari export qilinadi.\n\nFormatni tanlang:" if lang == "uz" else "👥 <b>Операторы</b>\n\nВсе операторы Call Center будут экспортированы.\n\nВыберите формат:"),
        reply_markup=get_ccs_export_formats_keyboard(lang),
        parse_mode="HTML",
    )
    await cb.answer()

@router.callback_query(F.data == "ccs_export_statistics")
async def export_statistics(cb: CallbackQuery, state: FSMContext):
    await state.update_data(export_type="statistics")
    lang = await get_user_language(cb.from_user.id) or "uz"
    await cb.message.edit_text(
        ("📊 <b>Statistika</b>\n\nQaysi davr uchun export qilasiz?" if lang == "uz" else "📊 <b>Статистика</b>\n\nЗа какой период экспортировать?"),
        reply_markup=get_ccs_time_period_keyboard(lang),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ccs_format_"))
async def export_format_handler(cb: CallbackQuery, state: FSMContext):
    """Handle format selection and generate export"""
    try:
        format_type = cb.data.split("_")[-1]  # csv, xlsx, docx, pdf
        data = await state.get_data()
        export_type = data.get("export_type")
        time_period = data.get("time_period", "total")  # today, week, month, total
        
        if not export_type:
            await cb.answer("❌ Eksport turi tanlanmagan!", show_alert=True)
            return
            
        lang = await get_user_language(cb.from_user.id) or "uz"
        
        # Processing message
        processing_text = ("⏳ <b>Ma'lumotlar tayyorlanmoqda...</b>" if lang == "uz" else "⏳ <b>Подготовка данных...</b>")
        await cb.message.edit_text(processing_text, parse_mode="HTML")
        
        # Get data based on export type
        data_rows = []
        filename_prefix = ""
        
        if export_type == "operator_orders":
            data_rows = await get_ccs_operator_orders_for_export(time_period)
            filename_prefix = "operator_orders"
        elif export_type == "operators":
            # Operators always use "total"
            data_rows = await get_ccs_operators_for_export()
            filename_prefix = "operators"
        elif export_type == "statistics":
            data_rows = await get_ccs_statistics_for_export(time_period)
            filename_prefix = "statistics"
        
        if not data_rows:
            no_data_text = ("❌ <b>Ma'lumot topilmadi</b>\n\nTanlangan bo'lim bo'yicha hech qanday ma'lumot mavjud emas." if lang == "uz" else "❌ <b>Данные не найдены</b>\n\nПо выбранному разделу нет доступных данных.")
            await cb.message.edit_text(no_data_text, parse_mode="HTML")
            await cb.answer()
            return
        
        # Generate file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ccs_{filename_prefix}_{timestamp}.{format_type}"
        
        # Create ExportUtils instance and generate file
        export_utils = ExportUtils()
        if export_type == "statistics":
            # For statistics, convert list to dict format expected by generate_statistics_export
            stats_dict = {}
            if data_rows:
                for item in data_rows:
                    if 'total_orders' in item:
                        stats_dict = item
                        break
            file_content = export_utils.generate_statistics_export(stats_dict, format_type, f"Call Center Supervisor {export_type.title()}")
        else:
            # For other types, use generate_orders_export
            file_content = export_utils.generate_orders_export(data_rows, format_type, f"Call Center Supervisor {export_type.title()}")
        
        if file_content:
            file = BufferedInputFile(file_content, filename=filename)
            
            # Format caption with time period (if applicable)
            if export_type == "operators":
                success_text = (f"✅ <b>Eksport tayyor!</b>\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}" if lang == "uz" else f"✅ <b>Экспорт готов!</b>\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            else:
                period_texts = {
                    "today": ("Bugun", "Сегодня"),
                    "week": ("Hafta (Dushanba - hozirgi)", "Неделя (Понедельник - сейчас)"),
                    "month": ("Oy", "Месяц"),
                    "total": ("Jami", "Всего")
                }
                period_text = period_texts.get(time_period, ("Jami", "Всего"))[0] if lang == "uz" else period_texts.get(time_period, ("Jami", "Всего"))[1]
                success_text = (f"✅ <b>Eksport tayyor!</b>\n📅 Davr: {period_text}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}" if lang == "uz" else f"✅ <b>Экспорт готов!</b>\n📅 Период: {period_text}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            
            await cb.message.answer_document(
                document=file,
                caption=success_text,
                parse_mode="HTML"
            )
        else:
            error_text = ("❌ <b>Xatolik yuz berdi</b>\n\nFaylni yaratishda muammo bo'ldi." if lang == "uz" else "❌ <b>Произошла ошибка</b>\n\nПроблема при создании файла.")
            await cb.message.edit_text(error_text, parse_mode="HTML")
        
        await state.clear()
        await cb.answer()
        
    except Exception as e:
        logger.error(f"Error in export format handler: {e}")
        error_text = ("❌ <b>Xatolik yuz berdi</b>\n\nIltimos, keyinroq urinib ko'ring." if lang == "uz" else "❌ <b>Произошла ошибка</b>\n\nПожалуйста, попробуйте позже.")
        await cb.message.edit_text(error_text, parse_mode="HTML")
        await cb.answer()

@router.callback_query(F.data == "ccs_export_back_types")
async def back_to_types(cb: CallbackQuery, state: FSMContext):
    """Handle back - go to time period selection or initial export types"""
    data = await state.get_data()
    export_type = data.get("export_type")
    time_period = data.get("time_period")
    lang = await get_user_language(cb.from_user.id) or "uz"
    
    # If we're coming from format selection (time_period is set) and it's not operators,
    # go back to time period selection
    if time_period and export_type and export_type != "operators":
        # Remove time_period from state to allow re-selection
        await state.update_data(time_period=None)
        
        keyboard = get_ccs_time_period_keyboard(lang)
        
        title_texts = {
            "operator_orders": ("Operatorlar ochgan arizalar", "Заявки операторов"),
            "statistics": ("Statistika", "Статистика")
        }
        
        title = title_texts.get(export_type, ("Export", "Экспорт"))
        text_title = title[0] if lang == "uz" else title[1]
        emoji = {"operator_orders": "📋", "statistics": "📊"}.get(export_type, "📤")
        
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
        await state.clear()
        await cb.message.edit_text(
            ("📤 <b>Call Center Supervisor eksportlari</b>\n\nKerakli bo'limni tanlang:" if lang == "uz" else "📤 <b>Экспорт супервайзера колл-центра</b>\n\nВыберите нужный раздел:"),
            reply_markup=get_ccs_export_types_keyboard(lang),
            parse_mode="HTML",
        )
        await cb.answer()

@router.callback_query(F.data == "ccs_export_end")
async def export_end(cb: CallbackQuery, state: FSMContext):
    """End export session"""
    await state.clear()
    lang = await get_user_language(cb.from_user.id) or "uz"
    end_text = ("✅ Eksport yakunlandi." if lang == "uz" else "✅ Экспорт завершен.")
    await cb.message.edit_text(end_text)
    await cb.answer()
