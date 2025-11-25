# handlers/junior_manager/connection_order_jm.py

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

# === Keyboards (i18n) ===
from keyboards.junior_manager_buttons import (
    get_junior_manager_main_menu,            # lang qo'llab-quvvatlaydi
    zayavka_type_keyboard,                   # lang qo'llab-quvvatlaydi (UZ/RU)
    get_client_regions_keyboard,             # lang param bor
    confirmation_keyboard,                   # lang qo'llab-quvvatlaydi (UZ/RU)
)
from keyboards.shared_staff_tariffs import (
    get_staff_b2c_tariff_keyboard,
    get_staff_tariff_category_keyboard,
    get_staff_biznet_tariff_keyboard,
    get_staff_tijorat_tariff_keyboard,
)

# === States ===
from states.junior_manager_states import staffConnectionOrderStates

# === DB functions ===
# !!! Import yo'lini loyihangizga moslang (oldin "conection" deb yozilgan bo'lishi mumkin).
from database.junior_manager.orders import (
    staff_orders_create,
    ensure_user_junior_manager,
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
router.message.filter(RoleFilter("junior_manager"))
router.callback_query.filter(RoleFilter("junior_manager"))

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

def normalize_lang(v: str | None) -> str:
    if not v:
        return "uz"
    s = v.strip().lower()
    if s in {"ru", "rus", "russian", "ru-ru", "ru_ru"}:
        return "ru"
    if s in {"uz", "uzb", "uzbek", "uz-uz", "uz_uz", "o'z", "oz"}:
        return "uz"
    return "uz"

def conn_type_display(lang: str, ctype: str | None) -> str:
    lang = normalize_lang(lang)
    key = (ctype or "b2c").lower()
    if lang == "ru":
        return "Физическое лицо" if key == "b2c" else "Юридическое лицо"
    return "Jismoniy shaxs" if key == "b2c" else "Yuridik shaxs"
REGION_CODE_TO_ID: dict[str, int] = {
    "toshkent_city": 1,
    "toshkent_region": 2,
    "andijon": 3,
    "fergana": 4,
    "namangan": 5,
    "sirdaryo": 6,
    "jizzax": 7,
    "samarkand": 8,
    "bukhara": 9,
    "navoi": 10,
    "kashkadarya": 11,
    "surkhandarya": 12,
    "khorezm": 13,
    "karakalpakstan": 14,
}
REGION_CODE_TO_NAME = {
    "uz": {
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
    },
    "ru": {
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
}

def region_display(lang: str, region_code: str | None) -> str:
    lang = normalize_lang(lang)
    return REGION_CODE_TO_NAME.get(lang, {}).get(region_code or "", region_code or "-")
TARIFF_DISPLAY = {
    "uz": {
        # B2C Plans
        "tariff_b2c_plan_0": "Oddiy-20",
        "tariff_b2c_plan_1": "Oddiy-50",
        "tariff_b2c_plan_2": "Oddiy-100",
        "tariff_b2c_plan_3": "XIT-200",
        "tariff_b2c_plan_4": "VIP-500",
        "tariff_b2c_plan_5": "PREMIUM",
        # BizNET-Pro Plans
        "tariff_biznet_plan_0": "BizNET-Pro-1",
        "tariff_biznet_plan_1": "BizNET-Pro-2",
        "tariff_biznet_plan_2": "BizNET-Pro-3",
        "tariff_biznet_plan_3": "BizNET-Pro-4",
        "tariff_biznet_plan_4": "BizNET-Pro-5",
        "tariff_biznet_plan_5": "BizNET-Pro-6",
        "tariff_biznet_plan_6": "BizNET-Pro-7+",
        # Tijorat Plans
        "tariff_tijorat_plan_0": "Tijorat-1",
        "tariff_tijorat_plan_1": "Tijorat-2",
        "tariff_tijorat_plan_2": "Tijorat-3",
        "tariff_tijorat_plan_3": "Tijorat-4",
        "tariff_tijorat_plan_4": "Tijorat-5",
        "tariff_tijorat_plan_5": "Tijorat-100",
        "tariff_tijorat_plan_6": "Tijorat-300",
        "tariff_tijorat_plan_7": "Tijorat-500",
        "tariff_tijorat_plan_8": "Tijorat-1000",
    },
    "ru": {
        # B2C Plans
        "tariff_b2c_plan_0": "Oddiy-20",
        "tariff_b2c_plan_1": "Oddiy-50",
        "tariff_b2c_plan_2": "Oddiy-100",
        "tariff_b2c_plan_3": "XIT-200",
        "tariff_b2c_plan_4": "VIP-500",
        "tariff_b2c_plan_5": "PREMIUM",
        # BizNET-Pro Plans
        "tariff_biznet_plan_0": "BizNET-Pro-1",
        "tariff_biznet_plan_1": "BizNET-Pro-2",
        "tariff_biznet_plan_2": "BizNET-Pro-3",
        "tariff_biznet_plan_3": "BizNET-Pro-4",
        "tariff_biznet_plan_4": "BizNET-Pro-5",
        "tariff_biznet_plan_5": "BizNET-Pro-6",
        "tariff_biznet_plan_6": "BizNET-Pro-7+",
        # Tijorat Plans
        "tariff_tijorat_plan_0": "Tijorat-1",
        "tariff_tijorat_plan_1": "Tijorat-2",
        "tariff_tijorat_plan_2": "Tijorat-3",
        "tariff_tijorat_plan_3": "Tijorat-4",
        "tariff_tijorat_plan_4": "Tijorat-5",
        "tariff_tijorat_plan_5": "Tijorat-100",
        "tariff_tijorat_plan_6": "Tijorat-300",
        "tariff_tijorat_plan_7": "Tijorat-500",
        "tariff_tijorat_plan_8": "Tijorat-1000",
    }
}

def strip_op_prefix_to_tariff(code: str | None) -> str | None:
    return resolve_tariff_code_from_callback(code)

def back_to_phone_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga" if lang == "uz" else "⬅️ Назад", callback_data="jm_conn_back_to_phone")]]
    )

# ======================= ENTRY (reply buttons) =======================
# ❗️ Triggerlarni tugmalarga aynan mos qilib qo'ydik
ENTRY_TEXTS_CONN = [
    "🔌 Ulanish arizasi yaratish",  # UZ tugma
    "🔌 Создать заявку",            # RU tugma
]

# ======================= ENTRY (reply buttons) =======================
@router.message(F.text.in_(ENTRY_TEXTS_CONN))
async def jm_start_text(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(staffConnectionOrderStates.waiting_client_phone)

    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await msg.answer(
        "📱 Mijozning telefon raqamini kiriting:" if lang == "uz" else "📱 Введите номер телефона клиента:",
        reply_markup=ReplyKeyboardRemove(),
    )

# ======================= STEP 1: phone lookup =======================
@router.message(StateFilter(staffConnectionOrderStates.waiting_client_phone))
async def jm_get_phone(msg: Message, state: FSMContext):
    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    phone_n = normalize_phone(msg.text)
    if not phone_n:
        return await msg.answer(
            "❌ Telefon raqam noto'g'ri formatda!" if lang == "uz" else "❌ Неверный формат номера телефона!",
            reply_markup=back_to_phone_kb(lang)
        )

    client = await find_user_by_phone(phone_n)
    if not client:
        return await msg.answer(
            "❌ Bu telefon raqam bilan mijoz topilmadi!" if lang == "uz" else "❌ Клиент с таким номером телефона не найден!",
            reply_markup=back_to_phone_kb(lang)
        )

    await state.update_data(acting_client=client)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Davom etish" if lang == "uz" else "✅ Продолжить", callback_data="jm_conn_continue"),
            InlineKeyboardButton(text="⬅️ Orqaga" if lang == "uz" else "⬅️ Назад",     callback_data="jm_conn_back_to_phone"),
        ]
    ])
    text = (
        f"{('✅ Mijoz topildi:' if lang == 'uz' else '✅ Клиент найден:')}\n"
        f"• ID: <b>{esc(str(client.get('id','')))}</b>\n"
        f"• F.I.Sh: <b>{esc(client.get('full_name',''))}</b>\n"
        f"• Tel: <b>{esc(client.get('phone',''))}</b>\n\n"
        f"{('✅ Davom etish' if lang == 'uz' else '✅ Продолжить')} / {('⬅️ Orqaga' if lang == 'uz' else '⬅️ Назад')}"
    )
    await msg.answer(text, parse_mode="HTML", reply_markup=kb)

# === Orqaga: telefon bosqichiga qaytarish
@router.callback_query(F.data == "jm_conn_back_to_phone")
async def jm_back_to_phone(cq: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(cq.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await cq.answer("📱 Telefon raqamni qaytadan kiriting" if lang == "uz" else "📱 Введите номер телефона заново")
    try:
        await cq.message.edit_reply_markup()
    except Exception:
        pass
    # acting_client ni ham tozalaymiz — toza boshlash uchun
    await state.clear()
    await state.set_state(staffConnectionOrderStates.waiting_client_phone)
    await cq.message.answer(
        "📱 Mijozning telefon raqamini kiriting:" if lang == "uz" else "📱 Введите номер телефона клиента:",
        reply_markup=ReplyKeyboardRemove(),
    )

# ======================= STEP 2: region =======================
@router.callback_query(StateFilter(staffConnectionOrderStates.waiting_client_phone), F.data == "jm_conn_continue")
async def jm_after_confirm_user(cq: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(cq.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await cq.message.edit_reply_markup()
    await cq.message.answer("📍 Viloyatni tanlang:" if lang == "uz" else "📍 Выберите регион:", reply_markup=get_client_regions_keyboard(lang=lang))
    await state.set_state(staffConnectionOrderStates.selecting_region)
    await cq.answer()

@router.callback_query(F.data.startswith("region_"), StateFilter(staffConnectionOrderStates.selecting_region))
async def jm_select_region(callback: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await callback.answer()
    await callback.message.edit_reply_markup()

    region_code = callback.data.replace("region_", "", 1)
    await state.update_data(selected_region=region_code)

    await callback.message.answer("🔌 Ulanish turini tanlang:" if lang == "uz" else "🔌 Выберите тип подключения:", reply_markup=zayavka_type_keyboard(lang))
    await state.set_state(staffConnectionOrderStates.selecting_connection_type)

# ======================= STEP 3: connection type =======================
@router.callback_query(F.data.startswith("zayavka_type_"), StateFilter(staffConnectionOrderStates.selecting_connection_type))
async def jm_select_connection_type(callback: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await callback.answer()
    await callback.message.edit_reply_markup()

    connection_type = callback.data.split("_")[-1]  # 'b2c' or 'b2b'
    await state.update_data(connection_type=connection_type)

    if connection_type == "b2c":
        text = "📋 Tarifni tanlang:" if lang == "uz" else "📋 Выберите тариф:"
        keyboard = get_staff_b2c_tariff_keyboard(lang=lang)
    else:
        text = "📋 Tarif toifasini tanlang:" if lang == "uz" else "📋 Выберите категорию тарифов:"
        keyboard = get_staff_tariff_category_keyboard(lang=lang)

    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(staffConnectionOrderStates.selecting_tariff)

# ======================= STEP 4: tariff =======================
@router.callback_query(StateFilter(staffConnectionOrderStates.selecting_tariff), F.data.startswith("op_tariff_"))
async def jm_tariff_flow(callback: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    data = callback.data

    if data == "op_tariff_back_to_type":
        await callback.answer()
        try:
            await callback.message.edit_reply_markup()
        except Exception:
            pass
        await state.update_data(selected_tariff=None, connection_type=None)
        await callback.message.answer(
            "🔌 Ulanish turini tanlang:" if lang == "uz" else "🔌 Выберите тип подключения:",
            reply_markup=zayavka_type_keyboard(lang),
        )
        await state.set_state(staffConnectionOrderStates.selecting_connection_type)
        return

    if data == "op_tariff_back_to_categories":
        await callback.answer()
        try:
            await callback.message.edit_reply_markup()
        except Exception:
            pass
        await callback.message.answer(
            "📋 Tarif toifasini tanlang:" if lang == "uz" else "📋 Выберите категорию тарифов:",
            reply_markup=get_staff_tariff_category_keyboard(lang=lang),
            parse_mode="HTML",
        )
        return

    if data in {"op_tariff_category_biznet", "op_tariff_category_tijorat"}:
        await callback.answer()
        try:
            await callback.message.edit_reply_markup()
        except Exception:
            pass

        if data.endswith("biznet"):
            text = "📋 BizNET-Pro tariflari:" if lang == "uz" else "📋 Тарифы BizNET-Pro:"
            keyboard = get_staff_biznet_tariff_keyboard(lang=lang)
        else:
            text = "📋 Tijorat tariflari:" if lang == "uz" else "📋 Тарифы Tijorat:"
            keyboard = get_staff_tijorat_tariff_keyboard(lang=lang)

        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return

    normalized_code = strip_op_prefix_to_tariff(data)
    if not normalized_code:
        await callback.answer()
        return

    await callback.answer()
    try:
        await callback.message.edit_reply_markup()
    except Exception:
        pass

    await state.update_data(selected_tariff=normalized_code)

    await callback.message.answer("🏠 Manzilni kiriting:" if lang == "uz" else "🏠 Введите адрес:")
    await state.set_state(staffConnectionOrderStates.entering_address)

# ======================= STEP 5: address =======================
@router.message(StateFilter(staffConnectionOrderStates.entering_address))
async def jm_get_address(msg: Message, state: FSMContext):
    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    address = (msg.text or "").strip()
    if not address:
        return await msg.answer("❌ Manzil kiritish majburiy!" if lang == "uz" else "❌ Адрес обязателен!")
    await state.update_data(address=address)
    await jm_show_summary(msg, state)

# ======================= STEP 6: summary =======================
async def jm_show_summary(target, state: FSMContext):
    u = await get_user_by_telegram_id(target.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    data = await state.get_data()
    region_code = data.get("selected_region", "-")
    ctype = (data.get("connection_type") or "b2c")
    tariff_code = data.get("selected_tariff")
    address = data.get("address", "-")

    display_map = TARIFF_DISPLAY.get(lang, {})
    tariff_label = display_map.get(tariff_code or "", None) or get_tariff_display_label(tariff_code, lang) or "-"

    text = (
        f"{('📍 Viloyat:' if lang == 'uz' else '📍 Регион:')} {region_display(lang, region_code)}\n"
        f"{('🔌 Tur:' if lang == 'uz' else '🔌 Тип:')} {conn_type_display(lang, ctype)}\n"
        f"{('📋 Tarif:' if lang == 'uz' else '📋 Тариф:')} {esc(tariff_label)}\n"
        f"{('🏠 Manzil:' if lang == 'uz' else '🏠 Адрес:')} {esc(address)}\n\n"
    )
    
    # Text for confirmation question
    if lang == 'uz':
        confirmation_text = "✅ Ma'lumotlar to'g'rimi?"
    else:
        confirmation_text = "✅ Данные верны?"
    
    text += confirmation_text

    kb = confirmation_keyboard(lang)
    if hasattr(target, "answer"):
        await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.message.answer(text, parse_mode="HTML", reply_markup=kb)

    await state.set_state(staffConnectionOrderStates.confirming_connection)

# ======================= STEP 7: confirm / resend =======================
@router.callback_query(F.data == "confirm_zayavka_call_center", StateFilter(staffConnectionOrderStates.confirming_connection))
async def jm_confirm(callback: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    try:
        await callback.message.edit_reply_markup()
        data = await state.get_data()

        acting_client = data.get("acting_client")
        if not acting_client:
            return await callback.answer("❌ Mijoz ma'lumotlari topilmadi!" if lang == "uz" else "❌ Данные клиента не найдены!", show_alert=True)

        # Yaratayotgan JM foydalanuvchi (DB dagi id)
        user_row = await ensure_user_junior_manager(callback.from_user.id, callback.from_user.full_name, callback.from_user.username)
        jm_user_id = user_row["id"]

        client_user_id = acting_client["id"]

        region_code = normalize_region_code((data.get("selected_region") or "toshkent_city")) or "toshkent_city"

        tariff_code = data.get("selected_tariff")  
        tarif_id = await get_or_create_tarif_by_code(tariff_code) if tariff_code else None
        display_map = TARIFF_DISPLAY.get(lang, {})
        tariff_label = display_map.get(tariff_code or "", None) or get_tariff_display_label(tariff_code, lang) or "-"

        result = await staff_orders_create(
            user_id=jm_user_id,  # YARATUVCHI xodim (Junior Manager) ID
            phone=acting_client.get("phone"),
            abonent_id=str(client_user_id),  # MIJOZ (Client) ID
            region=region_code,
            address=data.get("address", "Kiritilmagan" if lang == "uz" else "Не указан"),
            tarif_id=tarif_id,
            business_type=data.get("connection_type", "B2C").upper(),
            created_by_role="junior_manager",
        )

        # Guruhga xabar yuborish
        try:
            from loader import bot
            from utils.notification_service import send_group_notification_for_staff_order
            
            tariff_name = tariff_label if tariff_label != "-" else None
            region_name = region_display(lang, region_code)
            
            # Bazadan xodim ma'lumotlarini olish
            creator_user = await get_user_by_telegram_id(callback.from_user.id)
            creator_name = creator_user.get('full_name', callback.from_user.full_name) if creator_user else callback.from_user.full_name
            
            await send_group_notification_for_staff_order(
                bot=bot,
                order_id=result['application_number'],
                order_type="connection",
                client_name=acting_client.get('full_name', 'Noma\'lum'),
                client_phone=acting_client.get('phone', '-'),
                creator_name=creator_name,
                creator_role='junior_manager',
                region=region_name,
                address=data.get("address", "Kiritilmagan" if lang == "uz" else "Не указан"),
                tariff_name=tariff_name,
                business_type=data.get("connection_type", "B2C").upper()
            )
        except Exception as group_error:
            logger.error(f"Failed to send group notification for JM order: {group_error}")

        await callback.message.answer(
            (
                f"{('✅ Ulanish arizasi yaratildi!' if lang == 'uz' else '✅ Заявка на подключение создана!')}\n\n"
                f"{('🆔 Ariza raqami:' if lang == 'uz' else '🆔 Номер заявки:')} <code>{result['application_number']}</code>\n"
                f"{('📍 Viloyat:' if lang == 'uz' else '📍 Регион:')} {region_display(lang, region_code)}\n"
                f"{('📋 Tarif:' if lang == 'uz' else '📋 Тариф:')} {esc(tariff_label)}\n"
                f"{('📱 Telefon:' if lang == 'uz' else '📱 Телефон:')} {esc(acting_client.get('phone','-'))}\n"
                f"{('🏠 Manzil:' if lang == 'uz' else '🏠 Адрес:')} {esc(data.get('address','-'))}\n"
            ),
            reply_markup=get_junior_manager_main_menu(lang),
            parse_mode="HTML",
        )
        await state.clear()
    except Exception as e:
        logger.exception("JM confirm error: %s", e)
        await callback.answer("❌ Xatolik yuz berdi!" if lang == "uz" else "❌ Произошла ошибка!", show_alert=True)

@router.callback_query(F.data == "resend_zayavka_call_center", StateFilter(staffConnectionOrderStates.confirming_connection))
async def jm_resend(callback: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await callback.answer("🔄 Qaytadan boshlash" if lang == "uz" else "🔄 Начать заново")
    try:
        await callback.message.edit_reply_markup()
    except Exception:
        pass

    data = await state.get_data()
    acting_client = data.get("acting_client")
    await state.clear()
    if acting_client:
        await state.update_data(acting_client=acting_client)

    await state.set_state(staffConnectionOrderStates.selecting_region)
    await callback.message.answer("📍 Viloyatni tanlang:" if lang == "uz" else "📍 Выберите регион:", reply_markup=get_client_regions_keyboard(lang=lang))
