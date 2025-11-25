# handlers/controller/connection_order_controller.py

import re
import html
import logging
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.exceptions import TelegramBadRequest

# ==== Controller tugmalari (HAMMASI) ====
from keyboards.controllers_buttons import (
    get_controller_main_menu,
    controller_zayavka_type_keyboard,
    get_controller_regions_keyboard,
    controller_confirmation_keyboard,
    get_controller_tariff_selection_keyboard,
)

# === States ===
from states.controller_states import ControllerConnectionOrderStates

# === DB ===
from database.basic.user import ensure_user, get_user_by_telegram_id
from database.controller.orders import (
    staff_orders_create,
)
from database.basic.tariff import get_or_create_tarif_by_code
from database.basic.phone import find_user_by_phone

# === Role filter ===
from filters.role_filter import RoleFilter


logger = logging.getLogger(__name__)

router = Router()
router.message.filter(RoleFilter("controller"))
router.callback_query.filter(RoleFilter("controller"))

# -------------------------------------------------------
# I18N + helpers
# -------------------------------------------------------
T = {
    "entry_uz": "🔌 Ulanish arizasi yaratish",
    "entry_ru": "🔌 Создать заявку на подключение",

    "phone_prompt": {
        "uz": "📞 Mijoz telefon raqamini kiriting (masalan, +998901234567):",
        "ru": "📞 Введите номер телефона клиента (например, +998901234567):",
    },
    "phone_bad_format": {
        "uz": "❗️ Noto'g'ri format. Masalan: +998901234567",
        "ru": "❗️ Неверный формат. Например: +998901234567",
    },
    "user_not_found": {
        "uz": "❌ Bu raqam bo'yicha foydalanuvchi topilmadi. To'g'ri raqam yuboring.",
        "ru": "❌ Клиент с таким номером не найден. Отправьте корректный номер.",
    },
    "client_found": {"uz": "👤 Mijoz topildi:", "ru": "👤 Клиент найден:"},
    "continue": {"uz": "Davom etish ▶️", "ru": "Продолжить ▶️"},
    "back": {"uz": "🔙 Orqaga", "ru": "🔙 Назад"},
    "back_to_phone_notice": {"uz": "Telefon bosqichiga qaytdik", "ru": "Вернулись к вводу телефона"},

    "choose_region": {"uz": "🌍 Regionni tanlang:", "ru": "🌍 Выберите регион:"},
    "choose_conn_type": {"uz": "🔌 Ulanish turini tanlang:", "ru": "🔌 Выберите тип подключения:"},
    "choose_tariff": {"uz": "📋 <b>Tariflardan birini tanlang:</b>", "ru": "📋 <b>Выберите один из тарифов:</b>"},
    "enter_address": {"uz": "🏠 Manzilingizni kiriting:", "ru": "🏠 Введите адрес:"},
    "address_required": {"uz": "❗️ Iltimos, manzilni kiriting.", "ru": "❗️ Пожалуйста, введите адрес."},

    "summary_region": {"uz": "🗺️ <b>Hudud:</b>", "ru": "🗺️ <b>Регион:</b>"},
    "summary_type": {"uz": "🔌 <b>Ulanish turi:</b>", "ru": "🔌 <b>Тип подключения:</b>"},
    "summary_tariff": {"uz": "💳 <b>Tarif:</b>", "ru": "💳 <b>Тариф:</b>"},
    "summary_addr": {"uz": "🏠 <b>Manzil:</b>", "ru": "🏠 <b>Адрес:</b>"},
    "summary_ok": {"uz": "Ma'lumotlar to‘g‘rimi?", "ru": "Данные верны?"},

    "no_client": {"uz": "Mijoz tanlanmagan", "ru": "Клиент не выбран"},
    "error_generic": {"uz": "Xatolik yuz berdi", "ru": "Произошла ошибка"},
    "resend_restart": {"uz": "🔄 Qaytadan boshladik", "ru": "🔄 Начали заново"},

    "ok_created_title": {
        "uz": "✅ <b>Ariza yaratildi (controller → staff_orders)</b>",
        "ru": "✅ <b>Заявка создана (контроллер → staff_orders)</b>",
    },
    "lbl_req_id": {"uz": "🆔 Ariza raqami:", "ru": "🆔 Номер заявки:"},
    "lbl_region": {"uz": "📍 Region:", "ru": "📍 Регион:"},
    "lbl_tariff": {"uz": "💳 Tarif:", "ru": "💳 Тариф:"},
    "lbl_phone": {"uz": "📞 Tel:", "ru": "📞 Телефон:"},
    "lbl_addr": {"uz": "🏠 Manzil:", "ru": "🏠 Адрес:"},
}

def normalize_lang(v: str | None) -> str:
    if not v: return "uz"
    s = v.strip().lower()
    if s in {"ru","rus","russian","ru-ru","ru_ru"}: return "ru"
    return "uz"

def t(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    val = T.get(key)
    return val.get(lang, val.get("uz", key)) if isinstance(val, dict) else val

def esc(x) -> str:
    return html.escape(x or "-", quote=False)

# Region ko'rsatkichlari
REGION_CODE_TO_ID = {
    "toshkent_city": 1, "tashkent_city": 1, "toshkent_region": 2, "andijon": 3, "fergana": 4, "namangan": 5,
    "sirdaryo": 6, "jizzax": 7, "samarkand": 8, "bukhara": 9, "navoi": 10,
    "kashkadarya": 11, "surkhandarya": 12, "khorezm": 13, "karakalpakstan": 14,
}
REGION_CODE_TO_NAME = {
    "uz": {"toshkent_city":"Toshkent shahri","tashkent_city":"Toshkent shahri","toshkent_region":"Toshkent viloyati","andijon":"Andijon","fergana":"Farg'ona","namangan":"Namangan","sirdaryo":"Sirdaryo","jizzax":"Jizzax","samarkand":"Samarqand","bukhara":"Buxoro","navoi":"Navoiy","kashkadarya":"Qashqadaryo","surkhandarya":"Surxondaryo","khorezm":"Xorazm","karakalpakstan":"Qoraqalpog'iston"},
    "ru": {"toshkent_city":"г. Ташкент","tashkent_city":"г. Ташкент","toshkent_region":"Ташкентская область","andijon":"Андижан","fergana":"Фергана","namangan":"Наманган","sirdaryo":"Сырдарья","jizzax":"Джизак","samarkand":"Самарканд","bukhara":"Бухара","navoi":"Навои","kashkadarya":"Кашкадарья","surkhandarya":"Сурхандарья","khorezm":"Хорезм","karakalpakstan":"Каракалпакстан"},
}
def region_display(lang: str, code: str | None) -> str:
    lang = normalize_lang(lang)
    return REGION_CODE_TO_NAME.get(lang, {}).get(code or "", code or "-")

def conn_type_display(lang: str, ctype: str | None) -> str:
    lang = normalize_lang(lang)
    k = (ctype or "b2c").lower()
    if lang == "ru":
        return "Юридическое лицо" if k == "b2b" else "Физическое лицо"
    return "Yuridik shaxs" if k == "b2b" else "Jismoniy shaxs"

# Tarif ko'rsatuvchi
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
def tariff_display(lang: str, code: str | None) -> str:
    lang = normalize_lang(lang)
    if not code:
        return "-"
    return TARIFF_DISPLAY.get(lang, {}).get(code, code)

# Tel normalizatsiya
PHONE_RE = re.compile(r"^\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$|^\+?998\d{9}$|^\d{9,12}$")
def normalize_phone(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not PHONE_RE.match(raw): return None
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("998") and len(digits) == 12: return "+" + digits
    if len(digits) == 9: return "+998" + digits
    return raw if raw.startswith("+") else ("+" + digits if digits else None)

def strip_tariff_from_callback(cb_data: str) -> str | None:
    # ctrl_tariff_* yoki op_tariff_* -> tariff_*
    if cb_data.startswith("ctrl_tariff_"):
        return "tariff_" + cb_data[len("ctrl_tariff_"):]
    if cb_data.startswith("op_tariff_"):
        return "tariff_" + cb_data[len("op_tariff_"):]
    return None

def back_to_phone_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(
            text=("🔙 Назад" if normalize_lang(lang) == "ru" else "🔙 Orqaga"),
            callback_data="ctrl_conn_back_to_phone"
        )]]
    )

async def safe_clear_kb(message):
    # Inline markup bor bo‘lsa, xatoliksiz olib tashlaydi
    if not getattr(message, "reply_markup", None):
        return
    try:
        await message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise

# ======================= ENTRY =======================
@router.message(F.text.in_([T["entry_uz"], T["entry_ru"]]))
async def ctrl_start_text(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ControllerConnectionOrderStates.waiting_client_phone)
    user = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    await msg.answer(t(lang, "phone_prompt"), reply_markup=ReplyKeyboardRemove())

# ======================= STEP 1: phone lookup =======================
@router.message(StateFilter(ControllerConnectionOrderStates.waiting_client_phone))
async def ctrl_get_phone(msg: Message, state: FSMContext):
    user = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")

    phone_n = normalize_phone(msg.text)
    if not phone_n:
        return await msg.answer(t(lang, "phone_bad_format"), reply_markup=back_to_phone_kb(lang))

    user_row = await find_user_by_phone(phone_n)
    if not user_row:
        return await msg.answer(t(lang, "user_not_found"), reply_markup=back_to_phone_kb(lang))

    await state.update_data(acting_client=user_row)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=t(lang, "continue"), callback_data="ctrl_conn_continue"),
            InlineKeyboardButton(text=t(lang, "back"),     callback_data="ctrl_conn_back_to_phone"),
        ]]
    )
    text = (
        f"{t(lang,'client_found')}\n"
        f"• ID: <b>{esc(str(user_row.get('id','')))}</b>\n"
        f"• F.I.Sh: <b>{esc(user_row.get('full_name',''))}</b>\n"
        f"• Tel: <b>{esc(user_row.get('phone',''))}</b>\n\n"
        f"{t(lang,'continue')} / {t(lang,'back')}"
    )
    await msg.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "ctrl_conn_back_to_phone")
async def ctrl_back_to_phone(cq: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(cq.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    await cq.answer(t(lang, "back_to_phone_notice"))
    await safe_clear_kb(cq.message)
    await state.clear()
    await state.set_state(ControllerConnectionOrderStates.waiting_client_phone)
    await cq.message.answer(t(lang, "phone_prompt"), reply_markup=ReplyKeyboardRemove())

# ======================= STEP 2: region =======================
@router.callback_query(StateFilter(ControllerConnectionOrderStates.waiting_client_phone), F.data == "ctrl_conn_continue")
async def ctrl_after_confirm_user(cq: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(cq.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    await safe_clear_kb(cq.message)
    await cq.message.answer(t(lang, "choose_region"), reply_markup=get_controller_regions_keyboard(lang=lang))
    await state.set_state(ControllerConnectionOrderStates.selecting_region)
    await cq.answer()

@router.callback_query(F.data.startswith("region_"), StateFilter(ControllerConnectionOrderStates.selecting_region))
async def ctrl_select_region(callback: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    await callback.answer()
    await safe_clear_kb(callback.message)

    region_code = callback.data.replace("region_", "", 1)
    await state.update_data(selected_region=region_code)

    await callback.message.answer(
        t(lang, "choose_conn_type"),
        reply_markup=controller_zayavka_type_keyboard(lang)
    )
    await state.set_state(ControllerConnectionOrderStates.selecting_connection_type)

# ======================= STEP 3: connection type =======================
@router.callback_query(F.data.startswith("zayavka_type_"), StateFilter(ControllerConnectionOrderStates.selecting_connection_type))
async def ctrl_select_connection_type(callback: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    await callback.answer()
    await safe_clear_kb(callback.message)

    connection_type = callback.data.split("_")[-1]  # 'b2c' | 'b2b'
    await state.update_data(connection_type=connection_type)

    await callback.message.answer(
        t(lang, "choose_tariff"),
        reply_markup=get_controller_tariff_selection_keyboard(),  # controller klaviaturasi
        parse_mode="HTML",
    )
    await state.set_state(ControllerConnectionOrderStates.selecting_tariff)

# ======================= STEP 4: tariff =======================
@router.callback_query(StateFilter(ControllerConnectionOrderStates.selecting_tariff),
                       F.data.startswith("ctrl_tariff_"))
async def ctrl_select_tariff_ctrl(callback: CallbackQuery, state: FSMContext):
    await _handle_tariff_pick(callback, state)

@router.callback_query(StateFilter(ControllerConnectionOrderStates.selecting_tariff),
                       F.data.startswith("op_tariff_"))
async def ctrl_select_tariff_op(callback: CallbackQuery, state: FSMContext):
    # Ehtiyot uchun: eski operator klaviaturasi bilan ham ishlasin
    await _handle_tariff_pick(callback, state)

async def _handle_tariff_pick(callback: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    await callback.answer()
    await safe_clear_kb(callback.message)

    normalized_code = strip_tariff_from_callback(callback.data)
    if not normalized_code:
        normalized_code = callback.data  # fallback, lekin odatda kerak bo‘lmaydi
    await state.update_data(selected_tariff=normalized_code)

    await callback.message.answer(t(lang, "enter_address"))
    await state.set_state(ControllerConnectionOrderStates.entering_address)

# ======================= STEP 5: address =======================
@router.message(StateFilter(ControllerConnectionOrderStates.entering_address))
async def ctrl_get_address(msg: Message, state: FSMContext):
    user = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")

    address = (msg.text or "").strip()
    if not address:
        return await msg.answer(t(lang, "address_required"))
    await state.update_data(address=address)
    await ctrl_show_summary(msg, state)

# ======================= STEP 6: summary =======================
async def ctrl_show_summary(target, state: FSMContext):
    user = await get_user_by_telegram_id(target.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")

    data = await state.get_data()
    region_code  = data.get("selected_region", "-")
    ctype        = (data.get("connection_type") or "b2c")
    tariff_code  = data.get("selected_tariff")
    address      = data.get("address", "-")

    text = (
        f"{t(lang,'summary_region')} {region_display(lang, region_code)}\n"
        f"{t(lang,'summary_type')} {conn_type_display(lang, ctype)}\n"
        f"{t(lang,'summary_tariff')} {esc(tariff_display(lang, tariff_code))}\n"
        f"{t(lang,'summary_addr')} {esc(address)}\n\n"
        f"{t(lang,'summary_ok')}"
    )

    kb = controller_confirmation_keyboard(lang)
    if hasattr(target, "answer"):
        await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.message.answer(text, parse_mode="HTML", reply_markup=kb)

    await state.set_state(ControllerConnectionOrderStates.confirming_connection)

# ======================= STEP 7: confirm / resend =======================
@router.callback_query(F.data == "confirm_zayavka_call_center",
                       StateFilter(ControllerConnectionOrderStates.confirming_connection))
async def ctrl_confirm(callback: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")

    try:
        await safe_clear_kb(callback.message)
        data = await state.get_data()

        acting_client = data.get("acting_client")
        if not acting_client:
            return await callback.answer(t(lang, "no_client"), show_alert=True)

        # Controller user (kim yaratdi)
        user_row = await ensure_user(callback.from_user.id,
                                     callback.from_user.full_name,
                                     callback.from_user.username)
        controller_user_id = user_row["id"]
        client_user_id = acting_client["id"]

        region_code = (data.get("selected_region") or "toshkent_city").lower()
        region_id = REGION_CODE_TO_ID.get(region_code)
        if region_id is None:
            raise ValueError(f"Unknown region code: {region_code}")

        tariff_code = data.get("selected_tariff")
        tarif_id = await get_or_create_tarif_by_code(tariff_code) if tariff_code else None

        # description YUBORMAYMIZ (connection uchun shart emas!)
        request_id = await staff_orders_create_by_controller(
            user_id=controller_user_id,
            abonent_id=str(client_user_id),
            phone=acting_client.get("phone"),
            region=region_id,
            address=data.get("address", "Kiritilmagan"),
            tarif_id=tarif_id,
            connection_type=(data.get("connection_type") or "b2c"),
            type_of_zayavka="connection",
            initial_status="in_controller",
        )

        await callback.message.answer(
            (
                f"{t(lang,'ok_created_title')}\n\n"
                f"{t(lang,'lbl_req_id')} <code>{request_id}</code>\n"
                f"{t(lang,'lbl_region')} {region_display(lang, region_code)}\n"
                f"{t(lang,'lbl_tariff')} {esc(tariff_display(lang, tariff_code))}\n"
                f"{t(lang,'lbl_phone')} {esc(acting_client.get('phone','-'))}\n"
                f"{t(lang,'lbl_addr')} {esc(data.get('address','-'))}\n"
            ),
            reply_markup=get_controller_main_menu(lang),
            parse_mode="HTML",
        )
        await state.clear()
    except Exception as e:
        logger.exception("Controller confirm error: %s", e)
        await callback.answer(t(lang, "error_generic"), show_alert=True)

@router.callback_query(F.data == "resend_zayavka_call_center",
                       StateFilter(ControllerConnectionOrderStates.confirming_connection))
async def ctrl_resend(callback: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")

    await callback.answer(t(lang, "resend_restart"))
    await safe_clear_kb(callback.message)

    data = await state.get_data()
    acting_client = data.get("acting_client")

    await state.clear()
    if acting_client:
        await state.update_data(acting_client=acting_client)

    await state.set_state(ControllerConnectionOrderStates.selecting_region)
    await callback.message.answer(
        t(lang, "choose_region"),
        reply_markup=get_controller_regions_keyboard(lang=lang)
    )
