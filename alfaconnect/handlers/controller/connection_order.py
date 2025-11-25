# handlers/controller/connection_order.py

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
    controller_zayavka_type_keyboard,
    controller_confirmation_keyboard,
    get_controller_regions_keyboard,
)
from keyboards.shared_staff_tariffs import (
    get_staff_b2c_tariff_keyboard,
    get_staff_tariff_category_keyboard,
    get_staff_biznet_tariff_keyboard,
    get_staff_tijorat_tariff_keyboard,
)

# === States ===
from states.controller_states import ControllerConnectionOrderStates

# === DB functions ===
from database.controller.orders import (
    staff_orders_create,
    ensure_user_controller,
)
from database.basic.user import get_user_by_telegram_id, find_user_by_phone
from database.basic.tariff import get_or_create_tarif_by_code
from database.basic.region import normalize_region_code

from utils.tariff_helpers import (
    resolve_tariff_code_from_callback,
    get_tariff_display_label,
)

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

# -------------------------------------------------------
# 🔧 Tariff display mapping
# -------------------------------------------------------
TARIFF_DISPLAY = {
    'uz': {
        # B2C Plans
        'tariff_b2c_plan_0': 'Oddiy-20',
        'tariff_b2c_plan_1': 'Oddiy-50',
        'tariff_b2c_plan_2': 'Oddiy-100',
        'tariff_b2c_plan_3': 'XIT-200',
        'tariff_b2c_plan_4': 'VIP-500',
        'tariff_b2c_plan_5': 'PREMIUM',
        # BizNET-Pro Plans
        'tariff_biznet_plan_0': 'BizNET-Pro-1',
        'tariff_biznet_plan_1': 'BizNET-Pro-2',
        'tariff_biznet_plan_2': 'BizNET-Pro-3',
        'tariff_biznet_plan_3': 'BizNET-Pro-4',
        'tariff_biznet_plan_4': 'BizNET-Pro-5',
        'tariff_biznet_plan_5': 'BizNET-Pro-6',
        'tariff_biznet_plan_6': 'BizNET-Pro-7+',
        # Tijorat Plans
        'tariff_tijorat_plan_0': 'Tijorat-1',
        'tariff_tijorat_plan_1': 'Tijorat-2',
        'tariff_tijorat_plan_2': 'Tijorat-3',
        'tariff_tijorat_plan_3': 'Tijorat-4',
        'tariff_tijorat_plan_4': 'Tijorat-5',
        'tariff_tijorat_plan_5': 'Tijorat-100',
        'tariff_tijorat_plan_6': 'Tijorat-300',
        'tariff_tijorat_plan_7': 'Tijorat-500',
        'tariff_tijorat_plan_8': 'Tijorat-1000',
    },
    'ru': {
        # B2C Plans
        'tariff_b2c_plan_0': 'Oddiy-20',
        'tariff_b2c_plan_1': 'Oddiy-50',
        'tariff_b2c_plan_2': 'Oddiy-100',
        'tariff_b2c_plan_3': 'XIT-200',
        'tariff_b2c_plan_4': 'VIP-500',
        'tariff_b2c_plan_5': 'PREMIUM',
        # BizNET-Pro Plans
        'tariff_biznet_plan_0': 'BizNET-Pro-1',
        'tariff_biznet_plan_1': 'BizNET-Pro-2',
        'tariff_biznet_plan_2': 'BizNET-Pro-3',
        'tariff_biznet_plan_3': 'BizNET-Pro-4',
        'tariff_biznet_plan_4': 'BizNET-Pro-5',
        'tariff_biznet_plan_5': 'BizNET-Pro-6',
        'tariff_biznet_plan_6': 'BizNET-Pro-7+',
        # Tijorat Plans
        'tariff_tijorat_plan_0': 'Tijorat-1',
        'tariff_tijorat_plan_1': 'Tijorat-2',
        'tariff_tijorat_plan_2': 'Tijorat-3',
        'tariff_tijorat_plan_3': 'Tijorat-4',
        'tariff_tijorat_plan_4': 'Tijorat-5',
        'tariff_tijorat_plan_5': 'Tijorat-100',
        'tariff_tijorat_plan_6': 'Tijorat-300',
        'tariff_tijorat_plan_7': 'Tijorat-500',
        'tariff_tijorat_plan_8': 'Tijorat-1000',
    }
}

def back_to_phone_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga" if lang == "uz" else "⬅️ Назад", callback_data="controller_conn_back_to_phone")]
    ])

# ======================= ENTRY (reply buttons) =======================
ENTRY_TEXTS_CONN = [
    "🔌 Ulanish arizasi yaratish",  # UZ tugma
    "🔌 Создать заявку",            # RU tugma
]

# ======================= ENTRY (reply buttons) =======================
@router.message(F.text.in_(ENTRY_TEXTS_CONN))
async def controller_start_text(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ControllerConnectionOrderStates.waiting_client_phone)

    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await msg.answer(
        "📱 Mijozning telefon raqamini kiriting:" if lang == "uz" else "📱 Введите номер телефона клиента:",
        reply_markup=ReplyKeyboardRemove(),
    )

# ======================= STEP 1: phone lookup =======================
@router.message(StateFilter(ControllerConnectionOrderStates.waiting_client_phone))
async def controller_get_phone(msg: Message, state: FSMContext):
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
    await state.set_state(ControllerConnectionOrderStates.selecting_region)

    await msg.answer(
        f"✅ Mijoz topildi: {esc(client_user.get('full_name', '-'))}" if lang == "uz" else f"✅ Клиент найден: {esc(client_user.get('full_name', '-'))}",
        reply_markup=get_controller_regions_keyboard(lang)
    )

# ======================= STEP 2: region selection =======================
@router.callback_query(F.data.startswith("region_"), StateFilter(ControllerConnectionOrderStates.selecting_region))
async def controller_select_region(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    region_code = callback.data.replace("region_", "")
    await state.update_data(selected_region=region_code)
    await state.set_state(ControllerConnectionOrderStates.selecting_connection_type)

    region_name = region_display(lang, region_code)
    await callback.message.edit_text(
        f"✅ Hudud tanlandi: {esc(region_name)}\n\n" +
        ("Ulanish turini tanlang:" if lang == "uz" else "Выберите тип подключения:"),
        reply_markup=controller_zayavka_type_keyboard(lang)
    )

# ======================= STEP 3: connection type selection =======================
@router.callback_query(F.data.startswith("zayavka_type_"), StateFilter(ControllerConnectionOrderStates.selecting_connection_type))
async def controller_select_connection_type(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    connection_type = callback.data.replace("zayavka_type_", "")
    await state.update_data(connection_type=connection_type)
    await state.set_state(ControllerConnectionOrderStates.selecting_tariff)

    type_name = "Jismoniy shaxs" if connection_type == "b2c" else "Yuridik shaxs"
    if lang == "ru":
        type_name = "Физ. лицо" if connection_type == "b2c" else "Юр. лицо"

    if connection_type == "b2c":
        text = (
            f"✅ Ulanish turi tanlandi: {esc(type_name)}\n\n" +
            ("Tarifni tanlang:" if lang == "uz" else "Выберите тариф:")
        )
        keyboard = get_staff_b2c_tariff_keyboard(prefix="op_tariff", lang=lang)
    else:
        text = (
            f"✅ Ulanish turi tanlandi: {esc(type_name)}\n\n" +
            ("Tarif toifasini tanlang:" if lang == "uz" else "Выберите категорию тарифов:")
        )
        keyboard = get_staff_tariff_category_keyboard(prefix="op_tariff", lang=lang)

    await callback.message.edit_text(text, reply_markup=keyboard)

# ======================= STEP 4: tariff selection =======================
@router.callback_query(F.data.startswith("op_tariff_"), StateFilter(ControllerConnectionOrderStates.selecting_tariff))
async def controller_select_tariff(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    data = callback.data

    if data == "op_tariff_back_to_type":
        try:
            await callback.message.edit_reply_markup()
        except Exception:
            pass
        await state.update_data(selected_tariff=None, connection_type=None)
        await callback.message.answer(
            "🔌 Ulanish turini tanlang:" if lang == "uz" else "🔌 Выберите тип подключения:",
            reply_markup=controller_zayavka_type_keyboard(lang)
        )
        await state.set_state(ControllerConnectionOrderStates.selecting_connection_type)
        return

    if data == "op_tariff_back_to_categories":
        try:
            await callback.message.edit_reply_markup()
        except Exception:
            pass
        await callback.message.answer(
            "📋 Tarif toifasini tanlang:" if lang == "uz" else "📋 Выберите категорию тарифов:",
            reply_markup=get_staff_tariff_category_keyboard(prefix="op_tariff", lang=lang)
        )
        return

    if data in {"op_tariff_category_biznet", "op_tariff_category_tijorat"}:
        try:
            await callback.message.edit_reply_markup()
        except Exception:
            pass
        if data.endswith("biznet"):
            keyboard = get_staff_biznet_tariff_keyboard(prefix="op_tariff", lang=lang)
            text = "📋 BizNET-Pro tariflari:" if lang == "uz" else "📋 Тарифы BizNET-Pro:"
        else:
            keyboard = get_staff_tijorat_tariff_keyboard(prefix="op_tariff", lang=lang)
            text = "📋 Tijorat tariflari:" if lang == "uz" else "📋 Тарифы Tijorat:"
        await callback.message.answer(text, reply_markup=keyboard)
        return

    normalized_code = resolve_tariff_code_from_callback(data)
    if not normalized_code:
        return

    try:
        await callback.message.edit_reply_markup()
    except Exception:
        pass

    await state.update_data(selected_tariff=normalized_code)
    await state.set_state(ControllerConnectionOrderStates.entering_address)

    tariff_label = get_tariff_display_label(normalized_code, lang) or "-"
    await callback.message.answer(
        f"✅ Tarif tanlandi: {esc(tariff_label)}\n\n" +
        ("Manzilni kiriting:" if lang == "uz" else "Введите адрес:"),
    )

# ======================= STEP 5: address input =======================
@router.message(StateFilter(ControllerConnectionOrderStates.entering_address))
async def controller_get_address(msg: Message, state: FSMContext):
    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await state.update_data(address=msg.text.strip())
    await controller_show_summary(msg, state)

# ======================= STEP 6: summary and confirmation =======================
async def controller_show_summary(target, state: FSMContext):
    u = await get_user_by_telegram_id(target.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    data = await state.get_data()
    acting_client = data.get("acting_client", {})
    region_code = data.get("selected_region", "toshkent_city")
    connection_type = data.get("connection_type", "b2c")
    tariff_code = data.get("selected_tariff", "")
    address = data.get("address", "")

    region_name = region_display(lang, region_code)
    type_name = "Jismoniy shaxs" if connection_type == "b2c" else "Yuridik shaxs"
    if lang == "ru":
        type_name = "Физ. лицо" if connection_type == "b2c" else "Юр. лицо"
    tariff_map = TARIFF_DISPLAY.get(lang, {})
    tariff_label = tariff_map.get(tariff_code, None) or get_tariff_display_label(tariff_code, lang) or "-"

    summary_text = (
        f"📋 <b>Ulanish arizasi ma'lumotlari:</b>\n\n" if lang == "uz" else f"📋 <b>Данные заявки на подключение:</b>\n\n"
    ) + (
        f"👤 <b>Mijoz:</b> {esc(acting_client.get('full_name', '-'))}\n"
        f"📱 <b>Telefon:</b> {esc(acting_client.get('phone', '-'))}\n"
        f"📍 <b>Hudud:</b> {esc(region_name)}\n"
        f"🏢 <b>Ulanish turi:</b> {esc(type_name)}\n"
        f"📊 <b>Tarif:</b> {esc(tariff_label)}\n"
        f"🏠 <b>Manzil:</b> {esc(address)}\n\n"
        f"Ma'lumotlar to'g'rimi?" if lang == "uz" else
        f"👤 <b>Клиент:</b> {esc(acting_client.get('full_name', '-'))}\n"
        f"📱 <b>Телефон:</b> {esc(acting_client.get('phone', '-'))}\n"
        f"📍 <b>Регион:</b> {esc(region_name)}\n"
        f"🏢 <b>Тип подключения:</b> {esc(type_name)}\n"
        f"📊 <b>Тариф:</b> {esc(tariff_label)}\n"
        f"🏠 <b>Адрес:</b> {esc(address)}\n\n"
        f"Все верно?"
    )

    await target.answer(
        summary_text,
        reply_markup=controller_confirmation_keyboard(lang),
        parse_mode="HTML"
    )

    await state.set_state(ControllerConnectionOrderStates.confirming_connection)

# ======================= STEP 7: confirm / resend =======================
@router.callback_query(F.data == "confirm_zayavka_call_center", StateFilter(ControllerConnectionOrderStates.confirming_connection))
async def controller_confirm(callback: CallbackQuery, state: FSMContext):
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

        tariff_code = data.get("selected_tariff")  # tariff_* bo'lib keladi
        tarif_id = await get_or_create_tarif_by_code(tariff_code) if tariff_code else None
        tariff_map = TARIFF_DISPLAY.get(lang, {})
        tariff_label = tariff_map.get(tariff_code or "", None) or get_tariff_display_label(tariff_code, lang) or "-"

        result = await staff_orders_create(
            user_id=controller_user_id,
            phone=acting_client.get("phone"),
            abonent_id=str(client_user_id),
            region=region_code,
            address=data.get("address", "Kiritilmagan" if lang == "uz" else "Не указан"),
            tarif_id=tarif_id,
            business_type=data.get("connection_type", "B2C").upper(),
        )

        # Guruhga xabar yuborish
        try:
            from loader import bot
            from utils.notification_service import send_group_notification_for_staff_order
            
            tariff_name = tariff_label if tariff_label != "-" else None
            region_name = region_display(lang, region_code)
            
            await send_group_notification_for_staff_order(
                bot=bot,
                order_id=result['application_number'],
                order_type="connection",
                client_name=acting_client.get('full_name', 'Noma\'lum'),
                client_phone=acting_client.get('phone', '-'),
                creator_name=callback.from_user.full_name,
                creator_role='controller',
                region=region_name,
                address=data.get("address", "Kiritilmagan" if lang == "uz" else "Не указан"),
                tariff_name=tariff_name,
                business_type=data.get("connection_type", "B2C").upper()
            )
        except Exception as group_error:
            logger.error(f"Failed to send group notification for Controller order: {group_error}")

        await callback.message.answer(
            (
                f"{('✅ Ulanish arizasi yaratildi!' if lang == 'uz' else '✅ Заявка на подключение создана!')}\n\n"
                f"{('🆔 Ariza raqami:' if lang == 'uz' else '🆔 Номер заявки:')} <code>{result['application_number']}</code>\n"
                f"{('📍 Viloyat:' if lang == 'uz' else '📍 Регион:')} {region_display(lang, region_code)}\n"
                f"{('📋 Tarif:' if lang == 'uz' else '📋 Тариф:')} {esc(tariff_label)}\n"
                f"{('📱 Telefon:' if lang == 'uz' else '📱 Телефон:')} {esc(acting_client.get('phone','-'))}\n"
                f"{('🏠 Manzil:' if lang == 'uz' else '🏠 Адрес:')} {esc(data.get('address','-'))}\n"
                f"{('📤 Menejerga yuborildi!' if lang == 'uz' else '📤 Отправлено менеджеру!')}"
            ),
            reply_markup=get_controller_main_menu(lang),
            parse_mode="HTML",
        )
        await state.clear()
    except Exception as e:
        logger.exception("Controller confirm error: %s", e)
        await callback.answer("❌ Xatolik yuz berdi!" if lang == "uz" else "❌ Произошла ошибка!", show_alert=True)

@router.callback_query(F.data == "resend_zayavka_call_center", StateFilter(ControllerConnectionOrderStates.confirming_connection))
async def controller_resend(callback: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await callback.answer()
    await callback.message.edit_reply_markup()
    
    await callback.message.answer(
        "🔄 Ariza qayta boshlanmoqda...\n\nTelefon raqamini kiriting:" if lang == "uz" else "🔄 Заявка начинается заново...\n\nВведите номер телефона:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()
    await state.set_state(ControllerConnectionOrderStates.waiting_client_phone)

# ======================= BACK TO PHONE =======================
@router.callback_query(F.data == "controller_conn_back_to_phone", StateFilter(ControllerConnectionOrderStates.selecting_region))
async def controller_back_to_phone(callback: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await callback.answer()
    await callback.message.edit_text(
        "📱 Mijozning telefon raqamini kiriting:" if lang == "uz" else "📱 Введите номер телефона клиента:",
    )
    await state.set_state(ControllerConnectionOrderStates.waiting_client_phone)
