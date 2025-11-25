# handlers/manager/technician_order.py

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
from keyboards.manager_buttons import (
    get_manager_main_menu,
    get_client_regions_keyboard,
    confirmation_keyboard_tech_service,
)

# === States ===
from states.manager_states import staffTechnicianOrderStates

# === DB functions ===
from database.manager.orders import (
    staff_orders_technician_create,
    ensure_user_manager,
)
from database.basic.user import get_user_by_telegram_id, find_user_by_phone
from database.basic.region import normalize_region_code

# === Role filter ===
from filters.role_filter import RoleFilter

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(RoleFilter("manager"))
router.callback_query.filter(RoleFilter("manager"))

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

def back_to_phone_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga" if lang == "uz" else "⬅️ Назад", callback_data="manager_tech_back_to_phone")]]
    )

# ======================= ENTRY (reply buttons) =======================
ENTRY_TEXTS_TECH = [
    "🔧 Texnik xizmat yaratish",  # UZ tugma
    "🔧 Создать заявку на тех. обслуживание",  # RU tugma
]

# ======================= ENTRY (reply buttons) =======================
@router.message(F.text.in_(ENTRY_TEXTS_TECH))
async def manager_start_tech(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(staffTechnicianOrderStates.waiting_client_phone)

    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await msg.answer(
        "📞 Mijoz telefon raqamini kiriting:" if lang == "uz" else "📞 Введите номер телефона клиента:",
        reply_markup=ReplyKeyboardRemove(),
    )

# ======================= STEP 1: phone lookup =======================
@router.message(StateFilter(staffTechnicianOrderStates.waiting_client_phone))
async def manager_get_phone_tech(msg: Message, state: FSMContext):
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
            InlineKeyboardButton(text="✅ Davom etish" if lang == "uz" else "✅ Продолжить", callback_data="manager_tech_continue"),
            InlineKeyboardButton(text="⬅️ Orqaga" if lang == "uz" else "⬅️ Назад",     callback_data="manager_tech_back_to_phone"),
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
@router.callback_query(F.data == "manager_tech_back_to_phone")
async def manager_back_to_phone_tech(cq: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(cq.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await cq.answer("📞 Telefon raqamni qaytadan kiriting" if lang == "uz" else "📞 Введите номер телефона заново")
    try:
        await cq.message.edit_reply_markup()
    except Exception:
        pass
    # acting_client ni ham tozalaymiz — toza boshlash uchun
    await state.clear()
    await state.set_state(staffTechnicianOrderStates.waiting_client_phone)
    await cq.message.answer(
        "📞 Mijoz telefon raqamini kiriting:" if lang == "uz" else "📞 Введите номер телефона клиента:",
        reply_markup=ReplyKeyboardRemove(),
    )

# ======================= STEP 2: region =======================
@router.callback_query(StateFilter(staffTechnicianOrderStates.waiting_client_phone), F.data == "manager_tech_continue")
async def manager_after_confirm_user_tech(cq: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(cq.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await cq.message.edit_reply_markup()
    await cq.message.answer("📍 Viloyatni tanlang:" if lang == "uz" else "📍 Выберите регион:", reply_markup=get_client_regions_keyboard(lang=lang))
    await state.set_state(staffTechnicianOrderStates.selecting_region)
    await cq.answer()

@router.callback_query(F.data.startswith("region_"), StateFilter(staffTechnicianOrderStates.selecting_region))
async def manager_select_region_tech(callback: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    await callback.answer()
    await callback.message.edit_reply_markup()

    region_code = callback.data.replace("region_", "", 1)
    await state.update_data(selected_region=region_code)

    await callback.message.answer("🏠 Manzilni kiriting:" if lang == "uz" else "🏠 Введите адрес:")
    await state.set_state(staffTechnicianOrderStates.entering_address)

# ======================= STEP 3: address =======================
@router.message(StateFilter(staffTechnicianOrderStates.entering_address))
async def manager_get_address_tech(msg: Message, state: FSMContext):
    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    address = (msg.text or "").strip()
    if not address:
        return await msg.answer("❌ Manzil kiritish majburiy!" if lang == "uz" else "❌ Адрес обязателен!")
    await state.update_data(address=address)

    await msg.answer("📝 Muammoni tavsiflang:" if lang == "uz" else "📝 Опишите проблему:")
    await state.set_state(staffTechnicianOrderStates.problem_description)

# ======================= STEP 4: description =======================
@router.message(StateFilter(staffTechnicianOrderStates.description))
async def manager_get_description(msg: Message, state: FSMContext):
    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    description = (msg.text or "").strip()
    if not description:
        return await msg.answer("❌ Tavsif kiritish majburiy!" if lang == "uz" else "❌ Описание обязательно!")
    await state.update_data(description=description)
    await manager_show_summary_tech(msg, state)

# ======================= STEP 5: summary =======================
async def manager_show_summary_tech(target, state: FSMContext):
    u = await get_user_by_telegram_id(target.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    data = await state.get_data()
    region_code = data.get("selected_region", "-")
    address = data.get("address", "-")
    description = data.get("description", "-")

    text = (
        f"{('📍 Viloyat:' if lang == 'uz' else '📍 Регион:')} {region_display(lang, region_code)}\n"
        f"{('🏠 Manzil:' if lang == 'uz' else '🏠 Адрес:')} {esc(address)}\n"
        f"{('📝 Tavsif:' if lang == 'uz' else '📝 Описание:')} {esc(description)}\n\n"
    )
    
    # Text for confirmation question
    if lang == 'uz':
        confirmation_text = "✅ Ma'lumotlar to'g'rimi?"
    else:
        confirmation_text = "✅ Данные верны?"
    
    text += confirmation_text

    kb = confirmation_keyboard_tech_service(lang)
    if hasattr(target, "answer"):
        await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.message.answer(text, parse_mode="HTML", reply_markup=kb)

    await state.set_state(staffTechnicianOrderStates.confirming_connection)

# ======================= STEP 6: confirm / resend =======================
@router.callback_query(F.data == "confirm_zayavka_call_center_tech_service", StateFilter(staffTechnicianOrderStates.confirming_connection))
async def manager_confirm_tech(callback: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(callback.from_user.id)
    lang = normalize_lang(u.get("language") if u else "uz")

    try:
        await callback.message.edit_reply_markup()
        data = await state.get_data()

        acting_client = data.get("acting_client")
        if not acting_client:
            return await callback.answer("❌ Mijoz ma'lumotlari topilmadi!" if lang == "uz" else "❌ Данные клиента не найдены!", show_alert=True)

        # Yaratayotgan Manager foydalanuvchi (DB dagi id)
        user_row = await ensure_user_manager(callback.from_user.id, callback.from_user.full_name, callback.from_user.username)
        manager_user_id = user_row["id"]

        client_user_id = acting_client["id"]

        region_code = normalize_region_code((data.get("selected_region") or "toshkent_city")) or "toshkent_city"

        result = await staff_orders_technician_create(
            user_id=manager_user_id,
            phone=acting_client.get("phone"),
            abonent_id=str(client_user_id),
            region=region_code,
            address=data.get("address", "Kiritilmagan" if lang == "uz" else "Не указан"),
            description=data.get("description", "Kiritilmagan" if lang == "uz" else "Не указан"),
            business_type="B2C",  # Default B2C
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
                creator_role='manager',
                region=region_name,
                address=data.get("address", "Kiritilmagan" if lang == "uz" else "Не указан"),
                tariff_name=None,  # Texnik xizmatda tarif yo'q
                description=data.get("description", "Kiritilmagan" if lang == "uz" else "Не указан"),
                business_type="B2C"
            )
        except Exception as group_error:
            logger.error(f"Failed to send group notification for Manager technician order: {group_error}")

        await callback.message.answer(
            (
                f"{('✅ Texnik xizmat arizasi yaratildi!' if lang == 'uz' else '✅ Заявка на техническое обслуживание создана!')}\n\n"
                f"{('🆔 Ariza raqami:' if lang == 'uz' else '🆔 Номер заявки:')} <code>{result['application_number']}</code>\n"
                f"{('📍 Viloyat:' if lang == 'uz' else '📍 Регион:')} {region_display(lang, region_code)}\n"
                f"{('📱 Telefon:' if lang == 'uz' else '📱 Телефон:')} {esc(acting_client.get('phone','-'))}\n"
                f"{('🏠 Manzil:' if lang == 'uz' else '🏠 Адрес:')} {esc(data.get('address','-'))}\n"
                f"{('📝 Tavsif:' if lang == 'uz' else '📝 Описание:')} {esc(data.get('description','-'))}\n"
            ),
            reply_markup=get_manager_main_menu(lang),
            parse_mode="HTML",
        )
        await state.clear()
    except Exception as e:
        logger.exception("Manager tech confirm error: %s", e)
        await callback.answer("❌ Xatolik yuz berdi!" if lang == "uz" else "❌ Произошла ошибка!", show_alert=True)

@router.callback_query(F.data == "resend_zayavka_call_center_tech_service", StateFilter(staffTechnicianOrderStates.confirming_connection))
async def manager_resend_tech(callback: CallbackQuery, state: FSMContext):
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

    await state.set_state(staffTechnicianOrderStates.selecting_region)
    await callback.message.answer("📍 Viloyatni tanlang:" if lang == "uz" else "📍 Выберите регион:", reply_markup=get_client_regions_keyboard(lang=lang))