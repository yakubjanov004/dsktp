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

# === Keyboards ===
from keyboards.call_center_buttons import (
    get_call_center_main_keyboard,
    get_client_regions_keyboard,          # Region tanlash
    confirmation_keyboard_tech_service,   # confirm/resend (tech service)
)

# === States ===
from states.call_center_states import staffTechnicianOrderStates

# === DB ===
from database.call_center.search import find_user_by_phone
from database.basic.user import ensure_user
from database.technician.call_center import staff_orders_create
from database.basic.language import get_user_language
from database.basic.region import normalize_region_code

# === Role filter ===
from filters.role_filter import RoleFilter

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(RoleFilter("callcenter_operator"))
router.callback_query.filter(RoleFilter("callcenter_operator"))

# ----------------------- helpers -----------------------
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

def back_to_phone_kb(lang: str) -> InlineKeyboardMarkup:
    """Telefon bosqichiga qaytaruvchi inline tugma."""
    label = "🔙 Orqaga" if lang == "uz" else "🔙 Назад"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data="op_tservice_back_to_phone")]
    ])

# ======================= ENTRY =======================
ENTRY_TEXTS = {
    "uz": "🔧 Texnik xizmat yaratish",
    "ru": "🔧 Создать техническую заявку",
}

@router.message(F.text.in_(ENTRY_TEXTS.values()))
async def op_start_text(msg: Message, state: FSMContext):
    lang = await get_user_language(msg.from_user.id) or "uz"

    await state.clear()
    await state.update_data(lang=lang)
    text = (
        "📞 Mijoz telefon raqamini kiriting (masalan, +998901234567):"
        if lang == "uz"
        else "📞 Введите номер клиента (например, +998901234567):"
    )
    await state.set_state(staffTechnicianOrderStates.waiting_client_phone)
    await msg.answer(text, reply_markup=ReplyKeyboardRemove())

# ======================= STEP 1: phone lookup =======================
@router.message(StateFilter(staffTechnicianOrderStates.waiting_client_phone))
async def op_get_phone(msg: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang") or await get_user_language(msg.from_user.id) or "uz"

    phone_n = normalize_phone(msg.text)
    if not phone_n:
        return await msg.answer(
            "❗️ Noto'g'ri format. Masalan: +998901234567"
            if lang == "uz"
            else "❗️ Неверный формат. Например: +998901234567",
            reply_markup=back_to_phone_kb(lang)
        )

    user = await find_user_by_phone(phone_n)
    if not user:
        return await msg.answer(
            "❌ Bu raqam bo'yicha foydalanuvchi topilmadi."
            if lang == "uz"
            else "❌ Пользователь с таким номером не найден.",
            reply_markup=back_to_phone_kb(lang)
        )

    await state.update_data(acting_client=user)
    # ✅ Topildi — Davom etish + Orqaga yonma-yon
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="▶️ Davom etish" if lang == "uz" else "▶️ Продолжить",
            callback_data="op_tservice_continue"
        ),
        InlineKeyboardButton(
            text="🔙 Orqaga" if lang == "uz" else "🔙 Назад",
            callback_data="op_tservice_back_to_phone"
        ),
    ]])
    text = (
        "👤 Mijoz topildi:\n"
        f"• ID: <b>{user.get('id','')}</b>\n"
        f"• F.I.Sh: <b>{user.get('full_name','')}</b>\n"
        f"• Tel: <b>{user.get('phone','')}</b>\n\n"
        "Davom etish yoki orqaga qaytishni tanlang."
        if lang == "uz"
        else
        "👤 Клиент найден:\n"
        f"• ID: <b>{user.get('id','')}</b>\n"
        f"• Ф.И.О: <b>{user.get('full_name','')}</b>\n"
        f"• Тел: <b>{user.get('phone','')}</b>\n\n"
        "Продолжить или вернуться назад."
    )
    await msg.answer(text, parse_mode="HTML", reply_markup=kb)

# 🔙 Har qayerdan telefon bosqichiga qaytarish
@router.callback_query(F.data == "op_tservice_back_to_phone")
async def tservice_back_to_phone(cq: CallbackQuery, state: FSMContext):
    lang = (await state.get_data()).get("lang") or await get_user_language(cq.from_user.id) or "uz"
    await cq.answer("Telefon bosqichiga qaytdik" if lang == "uz" else "Вернулись к вводу телефона")
    try:
        await cq.message.edit_reply_markup()
    except Exception:
        pass
    await state.clear()
    await state.update_data(lang=lang)
    await state.set_state(staffTechnicianOrderStates.waiting_client_phone)
    await cq.message.answer(
        "📞 Mijoz telefon raqamini kiriting (masalan, +998901234567):"
        if lang == "uz" else
        "📞 Введите номер клиента (например, +998901234567):",
        reply_markup=ReplyKeyboardRemove()
    )

# ======================= STEP 2: region =======================
@router.callback_query(
    StateFilter(staffTechnicianOrderStates.waiting_client_phone),
    F.data == "op_tservice_continue"
)
async def op_after_confirm_user(cq: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cq.from_user.id) or "uz"

    await cq.message.edit_reply_markup()
    text = "🌍 Regionni tanlang:" if lang == "uz" else "🌍 Выберите регион:"

    # 🔑 lang ni uzatamiz
    await cq.message.answer(text, reply_markup=get_client_regions_keyboard(lang))

    await state.set_state(staffTechnicianOrderStates.selecting_region)
    await cq.answer()


@router.callback_query(F.data.startswith("region_"), StateFilter(staffTechnicianOrderStates.selecting_region))
async def op_select_region(callback: CallbackQuery, state: FSMContext):
    lang = (await state.get_data()).get("lang") or await get_user_language(callback.from_user.id) or "uz"

    await callback.answer()
    await callback.message.edit_reply_markup()
    region_code = callback.data.replace("region_", "", 1)
    await state.update_data(selected_region=region_code)

    await callback.message.answer(
        "📝 Muammoni qisqacha ta'riflab bering:" if lang == "uz" else "📝 Опишите проблему:"
    )
    await state.set_state(staffTechnicianOrderStates.description)

# ======================= STEP 3: description =======================
@router.message(StateFilter(staffTechnicianOrderStates.description))
async def op_get_description(msg: Message, state: FSMContext):
    lang = (await state.get_data()).get("lang") or await get_user_language(msg.from_user.id) or "uz"

    desc = (msg.text or "").strip()
    if not desc or len(desc) < 5:
        return await msg.answer(
            "❗️ Iltimos, muammoni aniqroq yozing (kamida 5 belgi)."
            if lang == "uz"
            else "❗️ Пожалуйста, опишите проблему подробнее (минимум 5 символов)."
        )
    await state.update_data(description=desc)

    await msg.answer("🏠 Manzilingizni kiriting:" if lang == "uz" else "🏠 Введите адрес:")
    await state.set_state(staffTechnicianOrderStates.entering_address)

# ======================= STEP 4: address =======================
@router.message(StateFilter(staffTechnicianOrderStates.entering_address))
async def op_get_address(msg: Message, state: FSMContext):
    lang = (await state.get_data()).get("lang") or await get_user_language(msg.from_user.id) or "uz"

    address = (msg.text or "").strip()
    if not address:
        return await msg.answer(
            "❗️ Iltimos, manzilni kiriting." if lang == "uz" else "❗️ Пожалуйста, введите адрес."
        )
    await state.update_data(address=address)
    await op_show_summary(msg, state)

# ======================= STEP 5: summary =======================
async def op_show_summary(target, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang") or "uz"

    region = data.get("selected_region", "-")
    address = data.get("address", "-")
    description = data.get("description", "-")

    text = (
        f"🗺️ <b>Hudud:</b> {region}\n"
        f"🛠 <b>Xizmat turi:</b> Texnik xizmat\n"
        f"📝 <b>Ta'rif:</b> {description}\n"
        f"🏠 <b>Manzil:</b> {address}\n\n"
        "Ma'lumotlar to‘g‘rimi?"
        if lang == "uz"
        else
        f"🗺️ <b>Регион:</b> {region}\n"
        f"🛠 <b>Тип услуги:</b> Техническое обслуживание\n"
        f"📝 <b>Описание:</b> {description}\n"
        f"🏠 <b>Адрес:</b> {address}\n\n"
        "Данные верны?"
    )

    # 🔑 lang uzatildi
    kb = confirmation_keyboard_tech_service(lang)

    if hasattr(target, "answer"):
        await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.message.answer(text, parse_mode="HTML", reply_markup=kb)

    await state.set_state(staffTechnicianOrderStates.confirming_connection)


# ======================= STEP 6: confirm =======================
@router.callback_query(
    F.data == "confirm_zayavka_call_center_tech_service",
    StateFilter(staffTechnicianOrderStates.confirming_connection)
)
async def op_confirm(callback: CallbackQuery, state: FSMContext):
    lang = (await state.get_data()).get("lang") or await get_user_language(callback.from_user.id) or "uz"

    try:
        await callback.message.edit_reply_markup()

        data = await state.get_data()
        acting_client = data.get("acting_client")
        if not acting_client:
            return await callback.answer(
                "Mijoz tanlanmagan" if lang == "uz" else "Клиент не выбран",
                show_alert=True
            )

        client_user_id = acting_client["id"]
        user_row = await ensure_user(callback.from_user.id, callback.from_user.full_name, callback.from_user.username)
        user_id = user_row["id"]

        region_code = normalize_region_code((data.get("selected_region") or "toshkent_city")) or "toshkent_city"

        description = data.get("description", "") or ""

        request_id = await staff_orders_create(
            user_id=user_id,
            phone=acting_client.get("phone"),
            abonent_id=str(client_user_id),
            region=region_code,
            address=data.get("address", "Kiritilmagan" if lang == "uz" else "Не указан"),
            description=description,
        )

        # Guruhga xabar yuborish
        try:
            from loader import bot
            from utils.notification_service import send_group_notification_for_staff_order
            from database.basic.user import get_user_by_telegram_id
            
            region_name = region_code.replace('_', ' ').title()
            
            # Bazadan xodim ma'lumotlarini olish
            creator_user = await get_user_by_telegram_id(callback.from_user.id)
            creator_name = creator_user.get('full_name', callback.from_user.full_name) if creator_user else callback.from_user.full_name
            
            await send_group_notification_for_staff_order(
                bot=bot,
                order_id=request_id,
                order_type="technician",
                client_name=acting_client.get('full_name', 'Noma\'lum'),
                client_phone=acting_client.get('phone', '-'),
                creator_name=creator_name,
                creator_role='call_center',
                region=region_name,
                address=data.get("address", "Kiritilmagan" if lang == "uz" else "Не указан"),
                tariff_name=None,  # Texnik xizmatda tarif yo'q
                description=description,
                business_type="B2C"
            )
        except Exception as group_error:
            logger.error(f"Failed to send group notification for Call Center technician order: {group_error}")

        # request_id aslida application_number ni qaytaradi
        application_number = request_id if isinstance(request_id, str) and "-" in str(request_id) else f"#{request_id}"
        
        text = (
            "✅ <b>Texnik xizmat arizasi yaratildi</b>\n\n"
            f"🆔 <b>Ariza raqami:</b> {application_number}\n"
            f"👤 <b>Mijoz:</b> {acting_client.get('full_name', '-')}\n"
            f"📞 <b>Telefon:</b> {acting_client.get('phone','-')}\n"
            f"🆔 <b>Abonent ID:</b> {str(client_user_id)}\n"
            f"📍 <b>Region:</b> {region_code.replace('_', ' ').title()}\n"
            f"🏠 <b>Manzil:</b> {data.get('address','-')}\n"
            f"📝 <b>Tavsif:</b> {description or '-'}\n"
            if lang == "uz"
            else
            "✅ <b>Заявка на техобслуживание создана</b>\n\n"
            f"🆔 <b>Номер заявки:</b> {application_number}\n"
            f"👤 <b>Клиент:</b> {acting_client.get('full_name', '-')}\n"
            f"📞 <b>Телефон:</b> {acting_client.get('phone','-')}\n"
            f"🆔 <b>ID абонента:</b> {str(client_user_id)}\n"
            f"📍 <b>Регион:</b> {region_code.replace('_', ' ').title()}\n"
            f"🏠 <b>Адрес:</b> {data.get('address','-')}\n"
            f"📝 <b>Описание:</b> {description or '-'}\n"
        )

        await callback.message.answer(
            text,
            reply_markup=get_call_center_main_keyboard(lang, callback.from_user.id),
            parse_mode="HTML",
        )
        await state.clear()

    except Exception as e:
        logger.exception("Operator technical confirm error: %s", e)
        await callback.answer(
            "Xatolik yuz berdi" if lang == "uz" else "Произошла ошибка",
            show_alert=True
        )

# ======================= STEP 7: resend (regiondan qayta) =======================
@router.callback_query(
    F.data == "resend_zayavka_call_center_tech_service",
    StateFilter(staffTechnicianOrderStates.confirming_connection)
)
async def op_resend(callback: CallbackQuery, state: FSMContext):
    """Qayta yuborish: jarayonni REGION tanlashdan qayta boshlaydi."""
    data = await state.get_data()
    lang = data.get("lang") or await get_user_language(callback.from_user.id) or "uz"

    await callback.answer("🔄 Qaytadan boshladik" if lang == "uz" else "🔄 Начали заново")
    try:
        await callback.message.edit_reply_markup()
    except Exception:
        pass

    acting_client = data.get("acting_client")
    # state-ni tozalab, zarurini saqlab qo'yamiz
    await state.clear()
    await state.update_data(lang=lang)
    if acting_client:
        await state.update_data(acting_client=acting_client)

    await state.set_state(staffTechnicianOrderStates.selecting_region)
    await callback.message.answer(
        "🌍 Regionni tanlang:" if lang == "uz" else "🌍 Выберите регион:",
        reply_markup=get_client_regions_keyboard()
    )