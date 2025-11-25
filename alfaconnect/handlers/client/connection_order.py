from datetime import datetime
import logging
import asyncio
from typing import Optional
import asyncpg
from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.exceptions import TelegramNetworkError, TelegramBadRequest

from keyboards.client_buttons import (
    get_client_main_menu,
    zayavka_type_keyboard,
    geolocation_keyboard,
    get_client_tariff_selection_keyboard,
    get_biznet_tariff_keyboard,
    get_tijorat_tariff_keyboard,
    B2C_PLANS,
    BIZNET_PRO_PLANS,
    TIJORAT_PLANS,
    confirmation_keyboard,
    get_client_regions_keyboard
)
from states.client_states import ConnectionOrderStates
from config import settings
from database.basic.user import ensure_user, get_user_by_telegram_id
from database.basic.tariff import get_or_create_tarif_by_code
from database.basic.language import get_user_language
from database.client.orders import create_connection_order
from loader import bot

logger = logging.getLogger(__name__)
router = Router()

# --- Lokalizatsiya helperlari ---
REGION_CODE_TO_UZ: dict = {
    "toshkent_city": "Toshkent shahri",
    "toshkent_region": "Toshkent viloyati",
    "andijon": "Andijon",
    "fergana": "Farg'ona",
    "namangan": "Namangan",
    "sirdaryo": "Sirdaryo",
    "jizzax": "Jizzax",
    "samarkand": "Samarqand",
    "bukhara": "Buxoro",
    "navoi": "Navoiy",
    "kashkadarya": "Qashqadaryo",
    "surkhandarya": "Surxondaryo",
    "khorezm": "Xorazm",
    "karakalpakstan": "Qoraqalpog'iston",
}
REGION_CODE_TO_RU: dict = {
    "toshkent_city": "г. Ташкент",
    "toshkent_region": "Ташкентская область",
    "andijon": "Андижан",
    "fergana": "Фергана",
    "namangan": "Наманган",
    "sirdaryo": "Сырдарья",
    "jizzax": "Джизак",
    "samarkand": "Самарканд",
    "bukhara": "Бухара",
    "navoi": "Навои",
    "kashkadarya": "Кашкадарья",
    "surkhandarya": "Сурхандарья",
    "khorezm": "Хорезм",
    "karakalpakstan": "Каракалпакстан",
}


def normalize_region(region_code: str, lang: str) -> str:
    if lang == "ru":
        return REGION_CODE_TO_RU.get(region_code, region_code)
    return REGION_CODE_TO_UZ.get(region_code, region_code)


def get_tariff_prompt(lang: str) -> str:
    return (
        "📋 <b>Tariflardan birini tanlang:</b>\n\n"
        if lang == "uz"
        else "📋 <b>Выберите тариф:</b>\n\n"
    )

# --- Tarif ko'rinish nomlari (UZ/RU)
_TARIFF_DISPLAY = {
    # B2C tariffs
    "b2c_plan_0": {"uz": "Oddiy-20", "ru": "Oddiy-20"},
    "b2c_plan_1": {"uz": "Oddiy-50", "ru": "Oddiy-50"},
    "b2c_plan_2": {"uz": "Oddiy-100", "ru": "Oddiy-100"},
    "b2c_plan_3": {"uz": "XIT-200", "ru": "XIT-200"},
    "b2c_plan_4": {"uz": "VIP-500", "ru": "VIP-500"},
    "b2c_plan_5": {"uz": "PREMIUM", "ru": "PREMIUM"},
    # BizNET-Pro tariffs
    "biznet_plan_0": {"uz": "BizNET-Pro-1", "ru": "BizNET-Pro-1"},
    "biznet_plan_1": {"uz": "BizNET-Pro-2", "ru": "BizNET-Pro-2"},
    "biznet_plan_2": {"uz": "BizNET-Pro-3", "ru": "BizNET-Pro-3"},
    "biznet_plan_3": {"uz": "BizNET-Pro-4", "ru": "BizNET-Pro-4"},
    "biznet_plan_4": {"uz": "BizNET-Pro-5", "ru": "BizNET-Pro-5"},
    "biznet_plan_5": {"uz": "BizNET-Pro-6", "ru": "BizNET-Pro-6"},
    "biznet_plan_6": {"uz": "BizNET-Pro-7+", "ru": "BizNET-Pro-7+"},
    # Tijorat tariffs
    "tijorat_plan_0": {"uz": "Tijorat-1", "ru": "Tijorat-1"},
    "tijorat_plan_1": {"uz": "Tijorat-2", "ru": "Tijorat-2"},
    "tijorat_plan_2": {"uz": "Tijorat-3", "ru": "Tijorat-3"},
    "tijorat_plan_3": {"uz": "Tijorat-4", "ru": "Tijorat-4"},
    "tijorat_plan_4": {"uz": "Tijorat-5", "ru": "Tijorat-5"},
    "tijorat_plan_5": {"uz": "Tijorat-100", "ru": "Tijorat-100"},
    "tijorat_plan_6": {"uz": "Tijorat-300", "ru": "Tijorat-300"},
    "tijorat_plan_7": {"uz": "Tijorat-500", "ru": "Tijorat-500"},
    "tijorat_plan_8": {"uz": "Tijorat-1000", "ru": "Tijorat-1000"},
}


def _normalize_tariff_code(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return code.replace("tariff_", "", 1) if code.startswith("tariff_") else code


def get_tariff_display_name(code: Optional[str], lang: str) -> Optional[str]:
    normalized = _normalize_tariff_code(code)
    if not normalized:
        return None
    display = _TARIFF_DISPLAY.get(normalized)
    if not display:
        return code
    return display.get(lang) or display.get("uz") or normalized

# ================== FLOW ==================

@router.message(F.text.in_(["🔌 Ulanish uchun ariza", "🔌 Заявка на подключение"]))
async def start_connection_order_client(message: Message, state: FSMContext):
    try:
        lang = await get_user_language(message.from_user.id) or "uz"

        # Clear state and set defaults for new order
        await state.clear()
        await state.update_data(lang=lang, connection_type='b2c')  # Force B2C for clients

        await message.answer(
            ("🔌 <b>Yangi ulanish arizasi</b>\n\n📍 Qaysi regionda ulanmoqchisiz?" if lang == "uz" else "🔌 <b>Новая заявка на подключение</b>\n\n📍 В каком регионе хотите подключиться?"),
            reply_markup=get_client_regions_keyboard(lang) if callable(get_client_regions_keyboard) else get_client_regions_keyboard(),
            parse_mode='HTML'
        )
        await state.set_state(ConnectionOrderStates.selecting_region)

    except Exception as e:
        logger.error(f"Error in start_connection_order_client: {e}")
        lang = await get_user_language(message.from_user.id) or "uz"
        await message.answer(
            "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."
            if lang == "uz" else
            "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз."
        )

@router.callback_query(F.data.startswith("region_"), StateFilter(ConnectionOrderStates.selecting_region))
async def select_region_old_client(callback: CallbackQuery, state: FSMContext):
    try:
        lang = (await state.get_data()).get("lang", "uz")
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)

        region_code = callback.data.replace("region_", "", 1)
        region_name = normalize_region(region_code, lang)
        await state.update_data(selected_region=region_name)

        await callback.message.answer(
            ("Ulanish turini tanlang:" if lang == "uz" else "Выберите тип подключения:"),
            reply_markup=zayavka_type_keyboard(lang) if callable(zayavka_type_keyboard) else zayavka_type_keyboard()
        )
        await state.set_state(ConnectionOrderStates.selecting_connection_type)

    except Exception as e:
        logger.error(f"Error in select_region_old_client: {e}")
        await callback.answer(("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз."), show_alert=True)

@router.callback_query(F.data.startswith("zayavka_type_"), StateFilter(ConnectionOrderStates.selecting_connection_type))
async def select_connection_type_client(callback: CallbackQuery, state: FSMContext):
    try:
        lang = (await state.get_data()).get("lang", "uz")
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)

        connection_type = callback.data.split("_")[-1]
        await state.update_data(connection_type=connection_type)

        # For B2C: send image and show plans
        if connection_type == "b2c":
            photo = FSInputFile("static/images/b2c.png")
            try:
                sent_message = await callback.message.answer_photo(
                    photo=photo,
                    caption=get_tariff_prompt(lang),
                    reply_markup=get_client_tariff_selection_keyboard(connection_type, lang),
                    parse_mode='HTML'
                )
                # Store photo message ID for back navigation
                await state.update_data(photo_message_id=sent_message.message_id)
            except Exception as img_error:
                logger.warning(f"Could not send tariff image: {img_error}")
                await callback.message.answer(
                    get_tariff_prompt(lang),
                    reply_markup=get_client_tariff_selection_keyboard(connection_type, lang),
                    parse_mode='HTML'
                )
        else:
            # For B2B: just show the text without image
            await callback.message.answer(
                get_tariff_prompt(lang),
                reply_markup=get_client_tariff_selection_keyboard(connection_type, lang),
                parse_mode='HTML'
            )
        await state.set_state(ConnectionOrderStates.selecting_tariff)

    except Exception as e:
        logger.error(f"Error in select_connection_type_client: {e}")
        await callback.answer(("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз."), show_alert=True)

# --- B2C Plan Selection (New) ---
@router.callback_query(F.data.startswith("b2c_plan_"), StateFilter(ConnectionOrderStates.selecting_tariff))
async def select_b2c_plan(callback: CallbackQuery, state: FSMContext):
    """Handle B2C plan selection"""
    try:
        plan_idx = int(callback.data.replace("b2c_plan_", ""))
        lang = (await state.get_data()).get("lang", "uz")
        
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)
        
        plan = B2C_PLANS[plan_idx]
        tariff_name = plan['name']
        
        await state.update_data(selected_tariff=f"b2c_plan_{plan_idx}")
        await callback.message.answer("📍 Manzilingizni kiriting:" if lang == "uz" else "📍 Введите ваш адрес:")
        await state.set_state(ConnectionOrderStates.entering_address)
    except Exception as e:
        logger.error(f"Error in select_b2c_plan: {e}")
        lang = (await state.get_data()).get("lang", "uz")
        await callback.answer(
            "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз.",
            show_alert=True
        )

# --- B2B BizNET-Pro Selection ---
@router.callback_query(F.data == "biznet_select", StateFilter(ConnectionOrderStates.selecting_tariff))
async def handle_biznet_select(callback: CallbackQuery, state: FSMContext):
    """Handle BizNET-Pro selection"""
    lang = (await state.get_data()).get("lang", "uz")
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Send image when BizNET-Pro is selected
    photo = FSInputFile("static/images/b2b-1.png")
    try:
        sent_message = await callback.message.answer_photo(photo=photo)
        # Store photo message ID for back navigation
        await state.update_data(photo_message_id=sent_message.message_id)
    except Exception:
        pass
    
    await callback.message.answer(
        "BizNET-Pro tarif rejalarni tanlang:\n(Yechilish tezligi kun va kechada bir xil)",
        reply_markup=get_biznet_tariff_keyboard(lang)
    )

@router.callback_query(F.data.startswith("biznet_plan_"), StateFilter(ConnectionOrderStates.selecting_tariff))
async def select_biznet_plan(callback: CallbackQuery, state: FSMContext):
    """Handle BizNET-Pro plan selection"""
    try:
        plan_idx = int(callback.data.replace("biznet_plan_", ""))
        lang = (await state.get_data()).get("lang", "uz")
        
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)
        
        plan = BIZNET_PRO_PLANS[plan_idx]
        tariff_name = plan['name']
        
        await state.update_data(selected_tariff=f"biznet_plan_{plan_idx}")
        await callback.message.answer("📍 Manzilingizni kiriting:" if lang == "uz" else "📍 Введите ваш адрес:")
        await state.set_state(ConnectionOrderStates.entering_address)
    except Exception as e:
        logger.error(f"Error in select_biznet_plan: {e}")
        lang = (await state.get_data()).get("lang", "uz")
        await callback.answer(
            "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз.",
            show_alert=True
        )

# --- B2B Tijorat Selection ---
@router.callback_query(F.data == "tijorat_select", StateFilter(ConnectionOrderStates.selecting_tariff))
async def handle_tijorat_select(callback: CallbackQuery, state: FSMContext):
    """Handle Tijorat selection"""
    lang = (await state.get_data()).get("lang", "uz")
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Send image when Tijorat is selected
    photo = FSInputFile("static/images/b2b-2.png")
    try:
        sent_message = await callback.message.answer_photo(photo=photo)
        # Store photo message ID for back navigation
        await state.update_data(photo_message_id=sent_message.message_id)
    except Exception:
        pass
    
    await callback.message.answer(
        "Tijorat tarif rejalarni tanlang:\n(Yechilish tezligi kun va kechada farqli)",
        reply_markup=get_tijorat_tariff_keyboard(lang)
    )

@router.callback_query(F.data.startswith("tijorat_plan_"), StateFilter(ConnectionOrderStates.selecting_tariff))
async def select_tijorat_plan(callback: CallbackQuery, state: FSMContext):
    """Handle Tijorat plan selection"""
    try:
        plan_idx = int(callback.data.replace("tijorat_plan_", ""))
        lang = (await state.get_data()).get("lang", "uz")
        
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)
        
        plan = TIJORAT_PLANS[plan_idx]
        tariff_name = plan['name']
        
        await state.update_data(selected_tariff=f"tijorat_plan_{plan_idx}")
        await callback.message.answer("📍 Manzilingizni kiriting:" if lang == "uz" else "📍 Введите ваш адрес:")
        await state.set_state(ConnectionOrderStates.entering_address)
    except Exception as e:
        logger.error(f"Error in select_tijorat_plan: {e}")
        lang = (await state.get_data()).get("lang", "uz")
        await callback.answer(
            "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз.",
            show_alert=True
        )

# --- Back Navigation Handlers ---
@router.callback_query(F.data == "back_to_tariff_selection", StateFilter(ConnectionOrderStates.selecting_tariff))
async def back_to_tariff_selection(callback: CallbackQuery, state: FSMContext):
    """Go back from BizNET-Pro/Tijorat plans to B2B selection"""
    try:
        lang = (await state.get_data()).get("lang", "uz")
        connection_type = (await state.get_data()).get("connection_type", "b2b")
        
        await callback.answer()
        
        # Delete photo message if exists
        photo_msg_id = (await state.get_data()).get("photo_message_id")
        if photo_msg_id:
            try:
                await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=photo_msg_id)
            except:
                pass
        
        # Delete current message with plan options
        try:
            await callback.message.delete()
        except:
            pass
        
        # Go back to B2B main selection
        await callback.message.answer(
            get_tariff_prompt(lang),
            reply_markup=get_client_tariff_selection_keyboard(connection_type, lang),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error in back_to_tariff_selection: {e}")
        lang = (await state.get_data()).get("lang", "uz")
        await callback.answer(
            "❌ Xatolik yuz berdi." if lang == "uz" else "❌ Произошла ошибка.",
            show_alert=True
        )

@router.callback_query(F.data == "back_to_connection_type", StateFilter(ConnectionOrderStates.selecting_tariff))
async def back_to_connection_type(callback: CallbackQuery, state: FSMContext):
    """Go back from tariff selection to connection type selection (Yuridik/Jismoniy)"""
    try:
        lang = (await state.get_data()).get("lang", "uz")
        region = (await state.get_data()).get("selected_region", "toshkent_city")
        
        await callback.answer()
        
        # Delete photo message if exists (for B2C, BizNET-Pro, Tijorat)
        photo_msg_id = (await state.get_data()).get("photo_message_id")
        if photo_msg_id:
            try:
                await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=photo_msg_id)
            except:
                pass
        
        # Delete current message
        try:
            await callback.message.delete()
        except:
            pass
        
        # Go back to connection type selection
        await callback.message.answer(
            ("Ulanish turini tanlang:" if lang == "uz" else "Выберите тип подключения:"),
            reply_markup=zayavka_type_keyboard(lang) if callable(zayavka_type_keyboard) else zayavka_type_keyboard()
        )
        await state.set_state(ConnectionOrderStates.selecting_connection_type)
    except Exception as e:
        logger.error(f"Error in back_to_connection_type: {e}")
        lang = (await state.get_data()).get("lang", "uz")
        await callback.answer(
            "❌ Xatolik yuz berdi." if lang == "uz" else "❌ Произошла ошибка.",
            show_alert=True
        )

# --- Legacy Tariff Handler (for backward compatibility with old orders) ---
@router.callback_query(F.data.in_(["tariff_xammasi_birga_4", "tariff_xammasi_birga_3_plus", "tariff_xammasi_birga_3", "tariff_xammasi_birga_2"]))
async def select_tariff_client(callback: CallbackQuery, state: FSMContext):
    lang = "uz"  # Default language
    try:
        lang = (await state.get_data()).get("lang", "uz")
        
        # Try to answer callback first with timeout handling
        try:
            await callback.answer()
        except (TelegramNetworkError, TelegramBadRequest, asyncio.TimeoutError) as e:
            logger.warning(f"Callback answer failed in select_tariff_client: {e}")
            # Continue execution even if callback answer fails
        
        # Try to edit reply markup with timeout handling
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except (TelegramNetworkError, TelegramBadRequest, asyncio.TimeoutError) as e:
            logger.warning(f"Edit reply markup failed in select_tariff_client: {e}")
            # Continue execution even if edit fails

        tariff_code = callback.data
        await state.update_data(selected_tariff=tariff_code)

        # Send new message instead of trying to edit old one
        try:
            await callback.message.answer("📍 Manzilingizni kiriting:" if lang == "uz" else "📍 Введите ваш адрес:")
        except (TelegramNetworkError, TelegramBadRequest, asyncio.TimeoutError) as e:
            logger.error(f"Failed to send address request message: {e}")
            return
            
        await state.set_state(ConnectionOrderStates.entering_address)

    except (TelegramNetworkError, TelegramBadRequest, asyncio.TimeoutError) as e:
        logger.error(f"Network/timeout error in select_tariff_client: {e}")
        # Don't try to answer callback on network/timeout errors
    except Exception as e:
        logger.error(f"Unexpected error in select_tariff_client: {e}")
        try:
            await callback.answer(("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз."), show_alert=True)
        except Exception:
            # If even error callback fails, just log it
            logger.error("Failed to send error message to user")

@router.message(StateFilter(ConnectionOrderStates.entering_address))
async def get_connection_address_client(message: Message, state: FSMContext):
    try:
        lang = (await state.get_data()).get("lang", "uz")
        await state.update_data(address=message.text)
        await message.answer(
            ("Geolokatsiya yuborasizmi?" if lang == "uz" else "Отправите геолокацию?"),
            reply_markup=geolocation_keyboard(lang) if callable(geolocation_keyboard) else geolocation_keyboard('uz')
        )
        await state.set_state(ConnectionOrderStates.asking_for_geo)

    except Exception as e:
        logger.error(f"Error in get_connection_address_client: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз.")

@router.callback_query(F.data.in_( ["send_location_yes", "send_location_no"]), StateFilter(ConnectionOrderStates.asking_for_geo))
async def ask_for_geo_client(callback: CallbackQuery, state: FSMContext):
    try:
        lang = (await state.get_data()).get("lang", "uz")
        await callback.answer()
        try:
            if callback.message.reply_markup is not None:
                await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest as e:
            if "not modified" in str(e).lower() or "message is not modified" in str(e).lower():
                # Ignore "message not modified" errors
                pass
            else:
                logger.warning(f"Failed to edit reply markup: {e}")
                # Continue execution even if we can't remove the markup

        if callback.data == "send_location_yes":
            location_keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📍 Joylashuvni yuborish" if lang == "uz" else "📍 Отправить локацию", request_location=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await callback.message.answer(("📍 Joylashuvingizni yuboring:" if lang == "uz" else "📍 Отправьте свою локацию:"), reply_markup=location_keyboard)
            await state.set_state(ConnectionOrderStates.waiting_for_geo)
        else:
            await finish_connection_order_client(callback, state, geo=None)

    except Exception as e:
        logger.error(f"Error in ask_for_geo_client: {e}")
        await callback.answer(("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if (await state.get_data()).get("lang", "uz") == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз."), show_alert=True)

@router.message(StateFilter(ConnectionOrderStates.waiting_for_geo), F.location)
async def get_geo_client(message: Message, state: FSMContext):
    try:
        lang = (await state.get_data()).get("lang", "uz")
        await state.update_data(geo=message.location)
        await message.answer(("✅ Joylashuv qabul qilindi!" if lang == "uz" else "✅ Геолокация получена!"), reply_markup=ReplyKeyboardRemove())
        await finish_connection_order_client(message, state, geo=message.location)

    except Exception as e:
        logger.error(f"Error in get_geo_client: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз.")

async def finish_connection_order_client(message_or_callback, state: FSMContext, geo=None):
    """Client uchun complete connection request submission"""
    try:
        data = await state.get_data()
        lang = data.get("lang", "uz")

        region = data.get('selected_region', data.get('region', 'toshkent shahri'))
        connection_type = data.get('connection_type', 'b2c')
        tariff_code = data.get('selected_tariff', 'tariff_b2c_plan_0')
        tariff_display = get_tariff_display_name(tariff_code, lang) or tariff_code
        address = data.get('address', '-')

        text = (
            (f"🏛️ <b>Hudud:</b> {region}\n" if lang == "uz" else f"🏛️ <b>Регион:</b> {region}\n") +
            (f"🔌 <b>Ulanish turi:</b> {connection_type.upper()}\n" if lang == "uz" else f"🔌 <b>Тип подключения:</b> {connection_type.upper()}\n") +
            (f"💳 <b>Tarif:</b> {tariff_display}\n" if lang == "uz" else f"💳 <b>Тариф:</b> {tariff_display}\n") +
            (f"🏠 <b>Manzil:</b> {address}\n" if lang == "uz" else f"🏠 <b>Адрес:</b> {address}\n") +
            (f"📍 <b>Geolokatsiya:</b> {'✅ Yuborilgan' if geo else '❌ Yuborilmagan'}\n\n" if lang == "uz" else f"📍 <b>Геолокация:</b> {'✅ Отправлена' if geo else '❌ Не отправлена'}\n\n") +
            ("Ma'lumotlar to'g'rimi?" if lang == "uz" else "Данные верны?")
        )

        if hasattr(message_or_callback, "message"):
            await message_or_callback.message.answer(text, parse_mode='HTML', reply_markup=confirmation_keyboard(lang) if callable(confirmation_keyboard) else confirmation_keyboard())
        else:
            await message_or_callback.answer(text, parse_mode='HTML', reply_markup=confirmation_keyboard(lang) if callable(confirmation_keyboard) else confirmation_keyboard())

        await state.set_state(ConnectionOrderStates.confirming_connection)

    except Exception as e:
        logger.error(f"Error in finish_connection_order_client: {e}")
        msg = ("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if (await state.get_data()).get("lang", "uz") == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз.")
        if hasattr(message_or_callback, "message"):
            await message_or_callback.message.answer(msg)
        else:
            await message_or_callback.answer(msg)

@router.callback_query(F.data == "confirm_zayavka", StateFilter(ConnectionOrderStates.confirming_connection))
async def confirm_connection_order_client(callback: CallbackQuery, state: FSMContext):
    """Client zayavkasini tasdiqlash va database'ga yozish"""
    try:
        data = await state.get_data()
        lang = data.get("lang", "uz")

        # Handle callback query
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("⏳ Zayavka yaratilmoaqda..." if lang == "uz" else "⏳ Заявка создаётся...")

        region = (data.get('selected_region') or data.get('region') or 'toshkent shahri')
        
        # Get user from callback
        user_telegram_id = callback.from_user.id
        user_full_name = callback.from_user.full_name
        user_username = callback.from_user.username
        
        user_row = await ensure_user(user_telegram_id, user_full_name, user_username)
        user_id = user_row["id"]
        user_phone = user_row.get("phone") if isinstance(user_row, dict) else user_row["phone"]

        tariff_code = data.get('selected_tariff')
        tarif_id = await get_or_create_tarif_by_code(tariff_code) if tariff_code else None
        tariff_name = get_tariff_display_name(tariff_code, lang)

        if tariff_code and not tarif_id:
            await callback.message.answer(
                ("❌ Tanlangan tarif topilmadi. Iltimos, quyidagi ro'yxatdan tarifni qayta tanlang." if lang == "uz" else "❌ Выбранный тариф не найден. Пожалуйста, выберите тариф заново из списка ниже."),
                reply_markup=get_client_tariff_selection_keyboard(lang) if callable(get_client_tariff_selection_keyboard) else get_client_tariff_selection_keyboard()
            )
            await state.set_state(ConnectionOrderStates.selecting_tariff)
            return

        geo_data = data.get('geo')
        latitude = getattr(geo_data, 'latitude', None) if geo_data else None
        longitude = getattr(geo_data, 'longitude', None) if geo_data else None

        connection_type = data.get('connection_type', 'b2c')

        if connection_type != 'b2b':
            connection_type = 'b2c'

        business_type = connection_type.upper()
        
        
        request_id = await create_connection_order(
            user_id=user_id,
            region=region.lower(),
            address=data.get('address', 'Kiritilmagan' if lang == "uz" else "Не указано"),
            tarif_id=tarif_id,
            latitude=latitude,
            longitude=longitude,
            business_type=business_type
        )

        conn = await asyncpg.connect(settings.DB_URL)
        try:
            result = await conn.fetchrow(
                "SELECT application_number FROM connection_orders WHERE id = $1", 
                request_id
            )
            app_number = result['application_number'] if result else f"CONN-{request_id:04d}"
            
            await conn.execute(
                """
                INSERT INTO connections (
                    application_number,
                    sender_id,
                    recipient_id,
                    sender_status,
                    recipient_status,
                    created_at,
                    updated_at
                )
                VALUES ($1, $2, $2, 'client_created', 'in_controller', NOW(), NOW())
                """,
                app_number, user_id  
            )
        except Exception as e:
            logger.error(f"Error fetching application number or creating connection record: {e}")
            app_number = f"CONN-{request_id:04d}"
        finally:
            await conn.close()

        if settings.ZAYAVKA_GROUP_ID:
            try:
                logger.info(f"Sending group notification for client connection order {app_number}")
                # Mijoz ma'lumotlarini bazadan olish
                user_info = await get_user_by_telegram_id(user_telegram_id)
                default_name = "Noma'lum"
                client_name = user_info.get('full_name') if user_info else user_full_name or default_name
                
                geo_text = ""
                if geo_data:
                    geo_text = f"\n📍 <b>Lokatsiya:</b> <a href='https://maps.google.com/?q={geo_data.latitude},{geo_data.longitude}'>Google Maps</a>"
                phone_for_msg = data.get('phone') or user_phone or '-'
                group_msg = (
                    f"🔌 <b>YANGI ULANISH ARIZASI</b>\n" 
                    f"{'='*30}\n"
                    f"🆔 <b>ID:</b> <code>{app_number}</code>\n"
                    f"👤 <b>Mijoz:</b> {client_name}\n"
                    f"📞 <b>Tel:</b> {phone_for_msg}\n"
                    f"🏢 <b>Region:</b> {region}\n"
                    f"💳 <b>Tarif:</b> {tariff_name}\n"
                    f"📍 <b>Manzil:</b> {data.get('address')}"
                    f"{geo_text}\n"
                    f"🕐 <b>Vaqt:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                    f"{'='*30}"
                )
                logger.info(f"Sending message to group {settings.ZAYAVKA_GROUP_ID}")
                await bot.send_message(chat_id=settings.ZAYAVKA_GROUP_ID, text=group_msg, parse_mode='HTML')
                logger.info(f"Group notification sent successfully for client connection order {app_number}")
            except Exception as e:
                logger.error(f"Failed to send group notification for client connection order: {e}")

        # Yuborish muvaffaqiyatli bo'lsa, foydalanuvchiga xabar bering
        success_msg = (
            f"✅ {'<b>Arizangiz muvaffaqiyatli qabul qilindi!</b>' if lang == 'uz' else '<b>Ваша заявка успешно принята!</b>'}\n\n"
            f"🆔 {'Ariza raqami' if lang == 'uz' else 'Номер заявки'}: {app_number}\n"
            f"📍 {'Hudud' if lang == 'uz' else 'Регион'}: {normalize_region(region, lang)}\n"
            f"💳 {'Tarif' if lang == 'uz' else 'Тариф'}: {tariff_name}\n"
            f"📞 {'Telefon' if lang == 'uz' else 'Телефон'}: {user_phone or '-'}\n"
            f"📍 {'Manzil' if lang == 'uz' else 'Адрес'}: {data.get('address', '-')}\n\n"
        )
        
        # Message text alohida o'zgaruvchiga
        if lang == 'uz':
            manager_msg = "Menejerlarimiz tez orada siz bilan bog'lanadi!"
        else:
            manager_msg = "Наши менеджеры свяжутся с вами в ближайшее время!"
        
        success_msg += f"⏰ {manager_msg}"
        
        # Send the success message
        await callback.message.answer(
            success_msg,
            reply_markup=get_client_main_menu(lang) if callable(get_client_main_menu) else get_client_main_menu('uz')
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Error in confirm_connection_order_client: {e}")
        await callback.message.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if (await state.get_data()).get("lang", "uz") == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз.")

@router.callback_query(F.data == "resend_zayavka", StateFilter(ConnectionOrderStates.confirming_connection))
async def resend_connection_order_client(callback: CallbackQuery, state: FSMContext):
    """Client zayavkasini qayta yuborish"""
    try:
        lang = (await state.get_data()).get("lang", "uz")
        await callback.answer("..." if lang == "ru" else "Qayta yuborish...")
        await callback.message.edit_reply_markup(reply_markup=None)

        await state.clear()
        await state.update_data(lang=lang)  # tilni saqlab qo'yamiz

        await callback.message.answer(
            ("🔌 <b>Yangi ulanish arizasi</b>\n\n📍 Qaysi regionda ulanmoqchisiz?" if lang == "uz" else "🔌 <b>Новая заявка на подключение</b>\n\n📍 В каком регионе хотите подключиться?"),
            reply_markup=get_client_regions_keyboard(lang) if callable(get_client_regions_keyboard) else get_client_regions_keyboard(),
            parse_mode='HTML'
        )
        await state.set_state(ConnectionOrderStates.selecting_region)

    except Exception as e:
        logger.error(f"Error in resend_connection_order_client: {e}")
        await callback.answer(("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring." if (await state.get_data()).get("lang", "uz") == "uz" else "❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз."), show_alert=True)
