# handlers/controller/technician_service.py

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
from aiogram.exceptions import TelegramBadRequest

# ==== CONTROLLER klaviaturalari ====
from keyboards.controllers_buttons import (
    get_controller_main_menu,
    get_controller_regions_keyboard,                 # region tanlash (UZ/RU)
    controller_confirmation_keyboard_tech_service,   # tasdiqlash (UZ/RU)
)

# === States (controller) ===
from states.controller_states import ControllerTechnicianOrderStates

# === DB (controller varianti) ===
from database.basic.phone import find_user_by_phone                          # user lookup
from database.controller.orders import (
    staff_orders_technician_create, # texnik xizmat arizasi yaratish
)
from database.basic.user import ensure_user   # controller userini ensure
from database.basic.region import normalize_region_code

# 🔑 tilni olish
from database.basic.user import get_user_by_telegram_id

# === Role filter ===
from filters.role_filter import RoleFilter

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(RoleFilter("controller"))
router.callback_query.filter(RoleFilter("controller"))

# ----------------------- I18N -----------------------
T = {
    "ask_phone": {
        "uz": "📞 Mijoz telefon raqamini kiriting (masalan, +998901234567):",
        "ru": "📞 Введите номер телефона клиента (например, +998901234567):",
    },
    "bad_phone_fmt": {
        "uz": "❗️ Noto'g'ri format. Masalan: +998901234567",
        "ru": "❗️ Неверный формат. Например: +998901234567",
    },
    "user_not_found": {
        "uz": "❌ Bu raqam bo'yicha foydalanuvchi topilmadi. To'g'ri raqam yuboring.",
        "ru": "❌ Пользователь с таким номером не найден. Отправьте правильный номер.",
    },
    "client_found": {"uz": "👤 Mijoz topildi:", "ru": "👤 Клиент найден:"},
    "continue": {"uz": "Davom etish ▶️", "ru": "Продолжить ▶️"},
    "back": {"uz": "🔙 Orqaga", "ru": "🔙 Назад"},
    "back_to_phone_toast": {"uz": "Telefon bosqichiga qaytdik", "ru": "Вернулись к шагу телефона"},

    "ask_region": {"uz": "🌍 Regionni tanlang:", "ru": "🌍 Выберите регион:"},

    "ask_desc": {
        "uz": "📝 Muammoni qisqacha ta'riflab bering (description):",
        "ru": "📝 Кратко опишите проблему (description):",
    },
    "desc_too_short": {
        "uz": "❗️ Iltimos, muammoni aniqroq yozing (kamida 5 belgi).",
        "ru": "❗️ Пожалуйста, опишите проблему подробнее (минимум 5 символов).",
    },

    "ask_address": {"uz": "🏠 Manzilingizni kiriting:", "ru": "🏠 Введите адрес:"},
    "address_required": {"uz": "❗️ Iltimos, manzilni kiriting.", "ru": "❗️ Пожалуйста, укажите адрес."},

    "summary_region": {"uz": "🗺️ <b>Hudud:</b>", "ru": "🗺️ <b>Регион:</b>"},
    "summary_service_type": {"uz": "🛠 <b>Xizmat turi:</b> Texnik xizmat", "ru": "🛠 <b>Тип услуги:</b> Техническое обслуживание"},
    "summary_desc": {"uz": "📝 <b>Ta'rif:</b>", "ru": "📝 <b>Описание:</b>"},
    "summary_address": {"uz": "🏠 <b>Manzil:</b>", "ru": "🏠 <b>Адрес:</b>"},
    "summary_ok": {"uz": "Ma'lumotlar to‘g‘rimi?", "ru": "Данные верные?"},

    "created_ok_title": {"uz": "✅ <b>Texnik xizmat arizasi yaratildi</b>", "ru": "✅ <b>Заявка на техобслуживание создана</b>"},
    "field_req_id": {"uz": "🆔 Ariza raqami:", "ru": "🆔 Номер заявки:"},
    "field_region": {"uz": "📍 Region:", "ru": "📍 Регион:"},
    "field_phone": {"uz": "📞 Tel:", "ru": "📞 Телефон:"},
    "field_address": {"uz": "🏠 Manzil:", "ru": "🏠 Адрес:"},
    "field_problem": {"uz": "📝 Muammo:", "ru": "📝 Проблема:"},

    "client_not_selected": {"uz": "Mijoz tanlanmagan", "ru": "Клиент не выбран"},
    "error_generic": {"uz": "Xatolik yuz berdi", "ru": "Произошла ошибка"},
    "resend_toast": {"uz": "🔄 Qaytadan boshladik", "ru": "🔄 Начали заново"},
}

def normalize_lang(value: str | None) -> str:
    if not value: return "uz"
    v = value.strip().lower()
    if v in {"ru","rus","russian","ru-ru","ru_ru"}: return "ru"
    return "uz"

def t(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    return T.get(key, {}).get(lang, T.get(key, {}).get("uz", key))

# ----------------------- helpers -----------------------
PHONE_RE = re.compile(r"^\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$|^\+?998\d{9}$|^\d{9,12}$")

def normalize_phone(phone_raw: str) -> str | None:
    phone_raw = (phone_raw or "").strip()
    if not PHONE_RE.match(phone_raw):
        return None
    digits = re.sub(r"\D", "", phone_raw)
    if digits.startswith("998") and len(digits) == 12: return "+" + digits
    if len(digits) == 9: return "+998" + digits
    return phone_raw if phone_raw.startswith("+") else ("+" + digits if digits else None)

REGION_CODE_TO_ID = {
    "toshkent_city": 1, "toshkent_region": 2, "andijon": 3, "fergana": 4, "namangan": 5,
    "sirdaryo": 6, "jizzax": 7, "samarkand": 8, "bukhara": 9, "navoi": 10,
    "kashkadarya": 11, "surkhandarya": 12, "khorezm": 13, "karakalpakstan": 14,
}

async def _get_lang_from_db(user_tg_id: int) -> str:
    user = await get_user_by_telegram_id(user_tg_id)
    return normalize_lang((user or {}).get("language"))

async def _lang(state: FSMContext, user_tg_id: int) -> str:
    data = await state.get_data()
    lang = data.get("lang")
    if lang: return normalize_lang(lang)
    lang = await _get_lang_from_db(user_tg_id)
    await state.update_data(lang=lang)
    return lang

async def safe_clear_kb(message):
    if not getattr(message, "reply_markup", None):
        return
    try:
        await message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise

# ======================= ENTRY (reply button) =======================
UZ_ENTRY_TEXT = "🔧 Texnik xizmat yaratish"
RU_ENTRY_TEXTS = {
    "🔧 Создать техническую заявку",
    "🔧 Создать заявку на тех. обслуживание",
    "🛠 Создать заявку на техобслуживание",
}

@router.message(F.text.in_({UZ_ENTRY_TEXT} | RU_ENTRY_TEXTS))
async def ctrl_tservice_start(msg: Message, state: FSMContext):
    await state.clear()
    lang = await _get_lang_from_db(msg.from_user.id)
    await state.update_data(lang=lang)
    await state.set_state(ControllerTechnicianOrderStates.waiting_client_phone)
    await msg.answer(t(lang, "ask_phone"), reply_markup=ReplyKeyboardRemove())

# ======================= STEP 1: phone lookup =======================
@router.message(StateFilter(ControllerTechnicianOrderStates.waiting_client_phone))
async def ctrl_tservice_get_phone(msg: Message, state: FSMContext):
    lang = await _lang(state, msg.from_user.id)

    phone_n = normalize_phone(msg.text)
    if not phone_n:
        return await msg.answer(
            t(lang, "bad_phone_fmt"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t(lang, "back"), callback_data="ctrl_tservice_back_to_phone")]
            ])
        )

    user = await find_user_by_phone(phone_n)
    if not user:
        return await msg.answer(
            t(lang, "user_not_found"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t(lang, "back"), callback_data="ctrl_tservice_back_to_phone")]
            ])
        )

    await state.update_data(acting_client=user)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "continue"), callback_data="ctrl_tservice_continue"),
        InlineKeyboardButton(text=t(lang, "back"),     callback_data="ctrl_tservice_back_to_phone"),
    ]])
    text = (
        f"{t(lang,'client_found')}\n"
        f"• ID: <b>{user.get('id','')}</b>\n"
        f"• F.I.Sh: <b>{user.get('full_name','')}</b>\n"
        f"• Tel: <b>{user.get('phone','')}</b>\n\n"
        f"{t(lang,'continue')} / {t(lang,'back')}"
    )
    await msg.answer(text, parse_mode="HTML", reply_markup=kb)

# 🔙 Telefon bosqichiga qaytarish
@router.callback_query(F.data == "ctrl_tservice_back_to_phone")
async def ctrl_tservice_back_to_phone(cq: CallbackQuery, state: FSMContext):
    lang = await _lang(state, cq.from_user.id)
    await cq.answer(t(lang, "back_to_phone_toast"))
    await safe_clear_kb(cq.message)
    await state.clear()
    await state.update_data(lang=lang)
    await state.set_state(ControllerTechnicianOrderStates.waiting_client_phone)
    await cq.message.answer(t(lang, "ask_phone"), reply_markup=ReplyKeyboardRemove())

# ======================= STEP 2: region =======================
@router.callback_query(StateFilter(ControllerTechnicianOrderStates.waiting_client_phone),
                       F.data == "ctrl_tservice_continue")
async def ctrl_tservice_after_confirm_user(cq: CallbackQuery, state: FSMContext):
    lang = await _lang(state, cq.from_user.id)
    await safe_clear_kb(cq.message)
    await cq.message.answer(t(lang, "ask_region"), reply_markup=get_controller_regions_keyboard(lang))
    await state.set_state(ControllerTechnicianOrderStates.selecting_region)
    await cq.answer()

@router.callback_query(F.data.startswith("region_"),
                       StateFilter(ControllerTechnicianOrderStates.selecting_region))
async def ctrl_tservice_select_region(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(state, callback.from_user.id)
    await callback.answer()
    await safe_clear_kb(callback.message)

    region_code = callback.data.replace("region_", "", 1)
    await state.update_data(selected_region=region_code)

    await callback.message.answer(t(lang, "ask_desc"))
    await state.set_state(ControllerTechnicianOrderStates.description)

# ======================= STEP 3: description =======================
@router.message(StateFilter(ControllerTechnicianOrderStates.description))
async def ctrl_tservice_get_description(msg: Message, state: FSMContext):
    lang = await _lang(state, msg.from_user.id)
    desc = (msg.text or "").strip()
    if not desc or len(desc) < 5:
        return await msg.answer(t(lang, "desc_too_short"))
    await state.update_data(description=desc)

    await msg.answer(t(lang, "ask_address"))
    await state.set_state(ControllerTechnicianOrderStates.entering_address)

# ======================= STEP 4: address =======================
@router.message(StateFilter(ControllerTechnicianOrderStates.entering_address))
async def ctrl_tservice_get_address(msg: Message, state: FSMContext):
    lang = await _lang(state, msg.from_user.id)
    address = (msg.text or "").strip()
    if not address:
        return await msg.answer(t(lang, "address_required"))
    await state.update_data(address=address)
    await ctrl_tservice_show_summary(msg, state)

# ======================= STEP 5: summary =======================
async def ctrl_tservice_show_summary(target, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    region_code = data.get("selected_region", "-")
    address     = data.get("address", "-")
    description = data.get("description", "-")

    region_pretty = region_code.replace("_", " ").title()

    text = (
        f"{t(lang,'summary_region')} {region_pretty}\n"
        f"{t(lang,'summary_service_type')}\n"
        f"{t(lang,'summary_desc')} {description}\n"
        f"{t(lang,'summary_address')} {address}\n\n"
        f"{t(lang,'summary_ok')}"
    )

    kb = controller_confirmation_keyboard_tech_service(lang)
    if hasattr(target, "answer"):
        await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.message.answer(text, parse_mode="HTML", reply_markup=kb)

    await state.set_state(ControllerTechnicianOrderStates.confirming_connection)

# ======================= STEP 6: confirm / resend =======================
@router.callback_query(
    F.data == "confirm_zayavka_call_center_tech_service",
    StateFilter(ControllerTechnicianOrderStates.confirming_connection)
)
async def ctrl_tservice_confirm(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(state, callback.from_user.id)
    try:
        await safe_clear_kb(callback.message)
        data = await state.get_data()

        acting_client = data.get("acting_client")
        if not acting_client:
            return await callback.answer(t(lang, "client_not_selected"), show_alert=True)

        client_user_id = acting_client["id"]
        controller_row = await ensure_user(callback.from_user.id, callback.from_user.full_name, callback.from_user.username)
        controller_user_id = controller_row["id"]

        region_code = normalize_region_code((data.get("selected_region") or "toshkent_city")) or "toshkent_city"

        description = data.get("description", "") or ""

        request_id = await staff_orders_technician_create_by_controller(
            user_id=controller_user_id,
            phone=acting_client.get("phone"),
            abonent_id=str(client_user_id),
            region=region_code,
            address=data.get("address", "Kiritilmagan" if lang == "uz" else "Не указано"),
            description=description,
            # initial_status default: 'in_controller'
        )

        result_text = (
            f"{t(lang,'created_ok_title')}\n\n"
            f"{t(lang,'field_req_id')} <code>{request_id}</code>\n"
            f"{t(lang,'field_region')} {region_code.replace('_', ' ').title()}\n"
            f"{t(lang,'field_phone')} {acting_client.get('phone','-')}\n"
            f"{t(lang,'field_address')} {data.get('address','-')}\n"
            f"{t(lang,'field_problem')} {description or '-'}\n"
        )
        await callback.message.answer(
            result_text,
            reply_markup=get_controller_main_menu(lang),
            parse_mode="HTML",
        )
        await state.clear()
    except Exception as e:
        logger.exception("Controller technical confirm error: %s", e)
        await callback.answer(t(lang, "error_generic"), show_alert=True)

@router.callback_query(
    F.data == "resend_zayavka_call_center_tech_service",
    StateFilter(ControllerTechnicianOrderStates.confirming_connection)
)
async def ctrl_tservice_resend(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(state, callback.from_user.id)
    await callback.answer(t(lang, "resend_toast"))
    await safe_clear_kb(callback.message)

    data = await state.get_data()
    acting_client = data.get("acting_client")
    await state.clear()
    await state.update_data(lang=lang)
    if acting_client:
        await state.update_data(acting_client=acting_client)

    await state.set_state(ControllerTechnicianOrderStates.selecting_region)
    await callback.message.answer(t(lang, "ask_region"), reply_markup=get_controller_regions_keyboard(lang))
