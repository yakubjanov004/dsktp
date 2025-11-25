# handlers/controller/technician_order.py

from datetime import datetime
import re
import logging
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
import html

# === Keyboards ===
from keyboards.controllers_buttons import (
    get_controller_main_menu,
    get_controller_regions_keyboard,
    controller_confirmation_keyboard_tech_service,
)

# === States ===
from states.controller_states import ControllerTechnicianOrderStates

# === DB functions ===
from database.controller.orders import (
    staff_orders_technician_create,
    ensure_user_controller,
)
from database.basic.user import get_user_by_telegram_id, find_user_by_phone
from database.basic.region import normalize_region_code

# === Role filter ===
from filters.role_filter import RoleFilter

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(RoleFilter("controller"))
router.callback_query.filter(RoleFilter("controller"))

# -------------------------------------------------------
# 🔧 Telefon raqam normalizatsiyasi
# -------------------------------------------------------
PHONE_RE = re.compile(r"^\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$|^\+?998\d{9}$|^\d{9,12}$")

def normalize_phone(phone_raw: str) -> str | None:
    phone_raw = (phone_raw or "").strip()
    if not PHONE_RE.match(phone_raw):
        return None
    digits = re.sub(r"\D", "", phone_raw)
    if digits.startswith("998") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 9:
        return "+998" + digits
    return phone_raw if phone_raw.startswith("+") else ("+" + digits if digits else None)

def esc(x: str | None) -> str:
    return html.escape(x or "-", quote=False)

def normalize_lang(lang: str | None) -> str:
    if not lang:
        return "uz"
    lang = lang.strip().lower()
    if lang in {"ru", "rus", "russian", "ru-ru", "ru_ru"}:
        return "ru"
    return "uz"

def region_display(lang: str, region_code: str) -> str:
    """Region code dan display name ga o'tkazish"""
    mapping = {
        'toshkent_city': {'uz': 'Toshkent shahri', 'ru': 'г. Ташкент'},
        'tashkent_city': {'uz': 'Toshkent shahri', 'ru': 'г. Ташкент'},
        'toshkent_region': {'uz': 'Toshkent viloyati', 'ru': 'Ташкентская область'},
        'andijon': {'uz': 'Andijon', 'ru': 'Андижан'},
        'fergana': {'uz': 'Farg\'ona', 'ru': 'Фергана'},
        'namangan': {'uz': 'Namangan', 'ru': 'Наманган'},
        'sirdaryo': {'uz': 'Sirdaryo', 'ru': 'Сырдарья'},
        'jizzax': {'uz': 'Jizzax', 'ru': 'Джизак'},
        'samarkand': {'uz': 'Samarqand', 'ru': 'Самарканд'},
        'bukhara': {'uz': 'Buxoro', 'ru': 'Бухара'},
        'navoi': {'uz': 'Navoiy', 'ru': 'Навои'},
        'kashkadarya': {'uz': 'Qashqadaryo', 'ru': 'Кашкадарья'},
        'surkhandarya': {'uz': 'Surxondaryo', 'ru': 'Сурхандарья'},
        'khorezm': {'uz': 'Xorazm', 'ru': 'Хорезм'},
        'karakalpakstan': {'uz': 'Qoraqalpog\'iston', 'ru': 'Каракалпакстан'},
    }
    return mapping.get(region_code.lower(), {}).get(lang, region_code)

def back_to_phone_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga" if lang == "uz" else "⬅️ Назад", callback_data="controller_tech_back_to_phone")]
    ])

# ======================= ENTRY (reply buttons) =======================
ENTRY_TEXTS_TECH = [
    "🔧 Texnik xizmat yaratish",  # UZ tugma
    "🔧 Создать заявку на тех. обслуживание",  # RU tugma
]

# ======================= ENTRY (reply buttons) =======================
@router.message(F.text.in_(ENTRY_TEXTS_TECH))
async def controller_start_tech(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ControllerTechnicianOrderStates.waiting_client_phone)

    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await msg.answer(
        "📞 Mijoz telefon raqamini kiriting:" if lang == "uz" else "📞 Введите номер телефона клиента:",
        reply_markup=ReplyKeyboardRemove(),
    )

# ======================= STEP 1: phone lookup =======================
@router.message(StateFilter(ControllerTechnicianOrderStates.waiting_client_phone))
async def controller_get_phone_tech(msg: Message, state: FSMContext):
    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    phone_raw = msg.text.strip()
    phone_normalized = normalize_phone(phone_raw)

    if not phone_normalized:
        await msg.answer(
            "❌ Noto'g'ri telefon raqam format!" if lang == "uz" else "❌ Неверный формат номера телефона!",
            reply_markup=back_to_phone_kb(lang)
        )
        return

    # Mijozni topish
    client_user = await find_user_by_phone(phone_normalized)
    if not client_user:
        await msg.answer(
            f"❌ Telefon raqam {esc(phone_normalized)} topilmadi!" if lang == "uz" else f"❌ Номер телефона {esc(phone_normalized)} не найден!",
            reply_markup=back_to_phone_kb(lang)
        )
        return

    await state.update_data(acting_client=dict(client_user))
    await state.set_state(ControllerTechnicianOrderStates.selecting_region)

    await msg.answer(
        f"✅ Mijoz topildi: {esc(client_user.get('full_name', '-'))}" if lang == "uz" else f"✅ Клиент найден: {esc(client_user.get('full_name', '-'))}",
        reply_markup=get_controller_regions_keyboard(lang)
    )

# ======================= STEP 2: region selection =======================
@router.callback_query(F.data.startswith("region_"), StateFilter(ControllerTechnicianOrderStates.selecting_region))
async def controller_select_region_tech(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    region_code = callback.data.replace("region_", "")
    await state.update_data(selected_region=region_code)
    await state.set_state(ControllerTechnicianOrderStates.problem_description)

    region_name = region_display(lang, region_code)
    await callback.message.edit_text(
        f"✅ Hudud tanlandi: {esc(region_name)}\n\n" +
        ("Muammoni batafsil tasvirlab bering:" if lang == "uz" else "Опишите проблему подробно:"),
    )

# ======================= STEP 3: problem description =======================
@router.message(StateFilter(ControllerTechnicianOrderStates.description))
async def controller_get_description(msg: Message, state: FSMContext):
    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await state.update_data(description=msg.text.strip())
    await state.set_state(ControllerTechnicianOrderStates.entering_address)

    await msg.answer(
        "📍 Manzilni kiriting:" if lang == "uz" else "📍 Введите адрес:",
    )

# ======================= STEP 4: address input =======================
@router.message(StateFilter(ControllerTechnicianOrderStates.entering_address))
async def controller_get_address_tech(msg: Message, state: FSMContext):
    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await state.update_data(address=msg.text.strip())
    await controller_show_summary_tech(msg, state)

# ======================= STEP 5: summary and confirmation =======================
async def controller_show_summary_tech(target, state: FSMContext):
    u = await get_user_by_telegram_id(target.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    data = await state.get_data()
    acting_client = data.get("acting_client", {})
    region_code = data.get("selected_region", "toshkent_city")
    description = data.get("description", "")
    address = data.get("address", "")

    region_name = region_display(lang, region_code)

    summary_text = (
        f"📋 <b>Texnik xizmat arizasi ma'lumotlari:</b>\n\n" if lang == "uz" else f"📋 <b>Данные заявки на техобслуживание:</b>\n\n"
    ) + (
        f"👤 <b>Mijoz:</b> {esc(acting_client.get('full_name', '-'))}\n"
        f"📱 <b>Telefon:</b> {esc(acting_client.get('phone', '-'))}\n"
        f"📍 <b>Hudud:</b> {esc(region_name)}\n"
        f"🔧 <b>Muammo:</b> {esc(description)}\n"
        f"🏠 <b>Manzil:</b> {esc(address)}\n\n"
        f"Ma'lumotlar to'g'rimi?" if lang == "uz" else
        f"👤 <b>Клиент:</b> {esc(acting_client.get('full_name', '-'))}\n"
        f"📱 <b>Телефон:</b> {esc(acting_client.get('phone', '-'))}\n"
        f"📍 <b>Регион:</b> {esc(region_name)}\n"
        f"🔧 <b>Проблема:</b> {esc(description)}\n"
        f"🏠 <b>Адрес:</b> {esc(address)}\n\n"
        f"Все верно?"
    )

    await target.answer(
        summary_text,
        reply_markup=controller_confirmation_keyboard_tech_service(lang),
        parse_mode="HTML"
    )

    await state.set_state(ControllerTechnicianOrderStates.confirming_connection)

# ======================= STEP 6: confirm / resend =======================
@router.callback_query(F.data == "confirm_zayavka_call_center_tech_service", StateFilter(ControllerTechnicianOrderStates.confirming_connection))
async def controller_confirm_tech(callback: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    try:
        await callback.message.edit_reply_markup()
        data = await state.get_data()

        acting_client = data.get("acting_client")
        if not acting_client:
            return await callback.answer("❌ Mijoz ma'lumotlari topilmadi!" if lang == "uz" else "❌ Данные клиента не найдены!", show_alert=True)

        # Yaratayotgan Controller foydalanuvchi (DB dagi id)
        user_row = await ensure_user_controller(callback.from_user.id, callback.from_user.full_name, callback.from_user.username)
        controller_user_id = user_row["id"]

        client_user_id = acting_client["id"]

        region_code = normalize_region_code((data.get("selected_region") or "toshkent_city")) or "toshkent_city"

        result = await staff_orders_technician_create(
            user_id=controller_user_id,
            phone=acting_client.get("phone"),
            abonent_id=str(client_user_id),
            region=region_code,
            address=data.get("address", "Kiritilmagan" if lang == "uz" else "Не указан"),
            description=data.get("description", "Kiritilmagan" if lang == "uz" else "Не указан"),
            business_type="B2C",
            created_by_role="controller",
        )

        # Guruhga xabar yuborish
        try:
            from loader import bot
            from utils.notification_service import send_group_notification_for_staff_order
            
            region_name = region_display(lang, region_code)
            
            # Bazadan xodim ma'lumotlarini olish
            creator_user = await get_user_by_telegram_id(callback.from_user.id)
            creator_name = creator_user.get('full_name', callback.from_user.full_name) if creator_user else callback.from_user.full_name
            
            await send_group_notification_for_staff_order(
                bot=bot,
                order_id=result['application_number'],
                order_type="technician",
                client_name=acting_client.get('full_name', 'Noma\'lum'),
                client_phone=acting_client.get('phone', '-'),
                creator_name=creator_name,
                creator_role='controller',
                region=region_name,
                address=data.get("address", "Kiritilmagan" if lang == "uz" else "Не указан"),
                tariff_name=None,  # Texnik xizmatda tarif yo'q
                description=data.get("description", "Kiritilmagan" if lang == "uz" else "Не указан"),
                business_type="B2C"
            )
        except Exception as group_error:
            logger.error(f"Failed to send group notification for Controller technician order: {group_error}")

        inbox_msg = '📤 Controller inboxga qo\'shildi!' if lang == 'uz' else '📤 Добавлено в inbox контроллера!'
        await callback.message.answer(
            (
                f"{('✅ Texnik xizmat arizasi yaratildi!' if lang == 'uz' else '✅ Заявка на техобслуживание создана!')}\n\n"
                f"{('🆔 Ariza raqami:' if lang == 'uz' else '🆔 Номер заявки:')} <code>{result['application_number']}</code>\n"
                f"{('📍 Viloyat:' if lang == 'uz' else '📍 Регион:')} {region_display(lang, region_code)}\n"
                f"{('🔧 Muammo:' if lang == 'uz' else '🔧 Проблема:')} {esc(data.get('description','-'))}\n"
                f"{('📱 Telefon:' if lang == 'uz' else '📱 Телефон:')} {esc(acting_client.get('phone','-'))}\n"
                f"{('🏠 Manzil:' if lang == 'uz' else '🏠 Адрес:')} {esc(data.get('address','-'))}\n"
                f"{inbox_msg}"
            ),
            reply_markup=get_controller_main_menu(lang),
            parse_mode="HTML",
        )
        await state.clear()
    except Exception as e:
        logger.exception("Controller confirm tech error: %s", e)
        await callback.answer("❌ Xatolik yuz berdi!" if lang == "uz" else "❌ Произошла ошибка!", show_alert=True)

@router.callback_query(F.data == "resend_zayavka_call_center_tech_service", StateFilter(ControllerTechnicianOrderStates.confirming_connection))
async def controller_resend_tech(callback: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await callback.answer()
    await callback.message.edit_reply_markup()
    
    await callback.message.answer(
        "🔄 Ariza qayta boshlanmoqda...\n\nTelefon raqamini kiriting:" if lang == "uz" else "🔄 Заявка начинается заново...\n\nВведите номер телефона:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()
    await state.set_state(ControllerTechnicianOrderStates.waiting_client_phone)

# ======================= BACK TO PHONE =======================
@router.callback_query(F.data == "controller_tech_back_to_phone", StateFilter(ControllerTechnicianOrderStates.selecting_region))
async def controller_back_to_phone_tech(callback: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await callback.answer()
    await callback.message.edit_text(
        "📞 Mijoz telefon raqamini kiriting:" if lang == "uz" else "📞 Введите номер телефона клиента:",
    )
    await state.set_state(ControllerTechnicianOrderStates.waiting_client_phone)
