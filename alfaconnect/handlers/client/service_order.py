from datetime import datetime
import html
import logging
from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from keyboards.client_buttons import (
    get_client_main_menu,
    zayavka_type_keyboard,
    geolocation_keyboard,
    media_attachment_keyboard,
    get_client_regions_keyboard,
    get_contact_keyboard,
)
from states.client_states import ServiceOrderStates
from database.basic.user import get_user_by_telegram_id, get_user_phone_by_telegram_id, update_user_phone_by_telegram_id
from database.basic.language import get_user_language
from database.client.orders import create_service_order
from utils.directory_utils import setup_media_structure
from config import settings
from loader import bot
import os
import asyncio
import asyncpg
from datetime import datetime

logger = logging.getLogger(__name__)
router = Router()

# ---------- Media fayllarini saqlash funksiyasi ----------
async def save_service_media_file(file_id: str, media_type: str, user_id: int, order_id: int) -> str:
    """Media faylini yuklab olish va saqlash"""
    try:
        # Media faylini olish
        if media_type == 'photo':
            file = await bot.get_file(file_id)
        elif media_type == 'video':
            file = await bot.get_file(file_id)
        else:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = 'jpg' if media_type == 'photo' else 'mp4'
        file_name = f"technician_{order_id}_{user_id}_{timestamp}.{file_extension}"

        setup_media_structure(settings.MEDIA_ROOT)

        current_year = datetime.now().strftime('%Y')
        current_month = datetime.now().strftime('%m')

        media_dir = os.path.join(settings.MEDIA_ROOT, current_year, current_month, 'orders', 'attachments')
        os.makedirs(media_dir, exist_ok=True)

        file_path = os.path.join(media_dir, file_name)
        await bot.download_file(file.file_path, file_path)

        # Media faylini database ga saqlash
        try:
            # Fayl hajmini olish
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            # Media faylini database ga saqlash (asyncpg bilan)
            conn = await asyncpg.connect(settings.DB_URL)
            try:
                await conn.execute("""
                    INSERT INTO media_files (
                        file_path, file_type, file_size, original_name, mime_type,
                        category, related_table, related_id, uploaded_by, is_active
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, 
                    file_path,
                    media_type,
                    file_size,
                    file_name,
                    f'image/jpeg' if media_type == 'photo' else 'video/mp4',
                    'service_attachment',
                    'technician_orders',
                    order_id,
                    user_id,
                    True
                )

                logger.info(f"Media file saved to database: {file_path}")

            finally:
                await conn.close()

        except Exception as e:
            logger.error(f"Could not save media file to database: {e}")

        return file_path

    except Exception as e:
        logger.error(f"Error saving media file: {e}")
        return None

# ---------- Region nomlarini normallashtirish ----------
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


def normalize_region(region_code: str) -> str:
    """Region kodini nomiga aylantirish"""
    return REGION_CODE_TO_UZ.get(region_code, region_code)


# ---------- Tasdiqlash inline klaviaturasi ----------
def confirmation_inline_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    confirm_text = "✅ Tasdiqlash" if lang == "uz" else "✅ Подтвердить"
    restart_text = "🔁 Qayta yuborish" if lang == "uz" else "🔁 Заполнить заново"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=confirm_text, callback_data="confirm_service_yes"),
        InlineKeyboardButton(text=restart_text, callback_data="confirm_service_no"),
    ]])

# ---------- Start: Texnik xizmat oqimi ----------
@router.message(F.text.in_(["🔧 Texnik xizmat", "🔧 Техническая служба"]))
async def start_service_order(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    try:
        await state.update_data(telegram_id=message.from_user.id)

        phone = await get_user_phone_by_telegram_id(message.from_user.id)
        if not phone:
            phone_text = "Iltimos, raqamingizni jo'nating (tugma orqali)." if lang == "uz" else "Пожалуйста, отправьте свой номер телефона (через кнопку)."
            await message.answer(phone_text, reply_markup=get_contact_keyboard(lang) if callable(get_contact_keyboard) else get_contact_keyboard())
            return
        else:
            await state.update_data(phone=phone)

        title_text = "🔧 <b>Texnik xizmat arizasi</b>\n\n📍 Qaysi hududda xizmat kerak?" if lang == "uz" else "🔧 <b>Заявка в техподдержку</b>\n\n📍 В каком регионе требуется обслуживание?"
        await message.answer(
            title_text,
            reply_markup=get_client_regions_keyboard(lang) if callable(get_client_regions_keyboard) else get_client_regions_keyboard(),
            parse_mode='HTML'
        )
        await state.set_state(ServiceOrderStates.selecting_region)

    except Exception as e:
        logger.error(f"Error: {e}")
        error_text = "❌ Xatolik yuz berdi." if lang == "uz" else "❌ Произошла ошибка."
        await message.answer(error_text)

# ---------- Contact qabul qilish ----------
@router.message(StateFilter(ServiceOrderStates.waiting_for_contact), F.contact)
async def handle_contact_for_service_order(message: Message, state: FSMContext):
    try:
        if not message.contact:
            return
        if message.contact.user_id and message.contact.user_id != message.from_user.id:
            phone_error = "Iltimos, faqat o'zingizning raqamingizni yuboring." if lang == "uz" else "Пожалуйста, отправьте только свой номер телефона."
            await message.answer(phone_error, reply_markup=get_contact_keyboard(lang) if callable(get_contact_keyboard) else get_contact_keyboard())
            return

        phone_number = message.contact.phone_number
        await update_user_phone_by_telegram_id(message.from_user.id, phone_number)
        await state.update_data(phone=phone_number, telegram_id=message.from_user.id)

        region_text = "✅ Raqam qabul qilindi. Endi hududni tanlang:" if lang == "uz" else "✅ Номер получен. Теперь выберите регион:"
        await message.answer(region_text, reply_markup=get_client_regions_keyboard(lang) if callable(get_client_regions_keyboard) else get_client_regions_keyboard())
        await state.set_state(ServiceOrderStates.selecting_region)

    except Exception as e:
        logger.error(f"Error in handle_contact_for_service_order: {e}")
        error_text = "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Попробуйте еще раз."
        await message.answer(error_text)

# ---------- Region tanlash ----------
@router.callback_query(F.data.startswith("region_"), StateFilter(ServiceOrderStates.selecting_region))
async def select_region(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id) or "uz"
    try:
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)

        region_code = callback.data.replace("region_", "", 1)
        region_name = normalize_region(region_code)

        await state.update_data(selected_region=region_name, region=region_name)

        abonent_text = "Abonent turini tanlang:" if lang == "uz" else "Выберите тип абонента:"
        await callback.message.answer(
            abonent_text,
            reply_markup=zayavka_type_keyboard(lang) if callable(zayavka_type_keyboard) else zayavka_type_keyboard(),
            parse_mode='HTML'
        )
        await state.set_state(ServiceOrderStates.selecting_abonent_type)

    except Exception as e:
        logger.error(f"Error: {e}")
        error_text = "❌ Xatolik yuz berdi." if lang == "uz" else "❌ Произошла ошибка."
        await callback.answer(error_text, show_alert=True)

# ---------- Abonent turini tanlash ----------
@router.callback_query(F.data.startswith("zayavka_type_"), StateFilter(ServiceOrderStates.selecting_abonent_type))
async def select_abonent_type(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id) or "uz"
    try:
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)

        abonent_type = callback.data.split("_")[-1].upper()
        await state.update_data(abonent_type=abonent_type)

        id_text = "🆔 Abonent ID raqamingizni kiriting:" if lang == "uz" else "🆔 Введите ваш ID абонента:"
        await callback.message.answer(id_text)
        await state.set_state(ServiceOrderStates.waiting_for_contact)

    except Exception as e:
        logger.error(f"Error: {e}")
        await callback.answer("❌ Xatolik yuz berdi.", show_alert=True)

# ---------- Abonent ID kiritish ----------
@router.message(StateFilter(ServiceOrderStates.waiting_for_contact), F.text)
async def get_abonent_id(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    try:
        await state.update_data(abonent_id=message.text)
        problem_text = "📝 Muammoni batafsil yozing:" if lang == "uz" else "📝 Опишите проблему подробнее:"
        await message.answer(problem_text)
        await state.set_state(ServiceOrderStates.entering_reason)
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Попробуйте еще раз.")

# ---------- Sabab / Muammo matni ----------
@router.message(StateFilter(ServiceOrderStates.entering_reason), F.text)
async def get_reason(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    try:
        await state.update_data(reason=message.text)
        await message.answer("📍 Manzilingizni kiriting:" if lang == "uz" else "📍 Введите ваш адрес:")
        await state.set_state(ServiceOrderStates.entering_address)
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Попробуйте еще раз.")

# ---------- Manzil ----------
@router.message(StateFilter(ServiceOrderStates.entering_address), F.text)
async def get_address(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    try:
        await state.update_data(address=message.text)
        await message.answer("📷 Muammo rasmi yoki videosini yuborasizmi:" if lang == "uz" else "📷 Прикрепите фото или видео проблемы?", reply_markup=media_attachment_keyboard(lang) if callable(media_attachment_keyboard) else media_attachment_keyboard())
        await state.set_state(ServiceOrderStates.asking_for_media)
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Попробуйте еще раз.")

# ---------- Media yuborish qarori ----------
@router.callback_query(F.data.in_(["attach_media_yes", "attach_media_no"]), StateFilter(ServiceOrderStates.asking_for_media))
async def ask_for_media(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id) or "uz"
    try:
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)

        if callback.data == "attach_media_yes":
            await callback.message.answer("📷 Rasm yoki video yuboring:" if lang == "uz" else "📷 Отправьте фото или видео:")
            await state.set_state(ServiceOrderStates.waiting_for_media)
        else:
            await ask_for_geolocation(callback.message, state, lang)
    except Exception as e:
        logger.error(f"Error: {e}")
        await callback.answer("❌ Xatolik yuz berdi.", show_alert=True)

# ---------- Media qabul qilish ----------
@router.message(StateFilter(ServiceOrderStates.waiting_for_media), F.photo | F.video)
async def get_media(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    try:
        if message.photo:
            media_id = message.photo[-1].file_id
            media_type = 'photo'
        elif message.video:
            video_size = message.video.file_size or 0
            max_size = 50 * 1024 * 1024
            
            if video_size > max_size:
                error_text = (
                    f"❌ Video hajmi juda katta!\n"
                    f"📊 Hozirgi hajm: {video_size / (1024*1024):.1f} MB\n"
                    f"📏 Maksimal hajm: 50 MB\n\n"
                    f"💡 Kichikroq video yuboring yoki video sifati pastroq qiling."
                    if lang == "uz" else
                    f"❌ Размер видео слишком большой!\n"
                    f"📊 Текущий размер: {video_size / (1024*1024):.1f} MB\n"
                    f"📏 Максимальный размер: 50 MB\n\n"
                    f"💡 Отправьте видео меньшего размера или снизьте качество."
                )
                await message.answer(error_text)
                return
            
            media_id = message.video.file_id
            media_type = 'video'
        else:
            media_id = None
            media_type = None

        # Media fayllari keyinro finish_service_order da saqlanadi (order_id olinagach)

        await state.update_data(media_id=media_id, media_type=media_type)
        await ask_for_geolocation(message, state, lang)
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Попробуйте еще раз.")

# ---------- Geolokatsiya so‘rash ----------
async def ask_for_geolocation(message: Message, state: FSMContext, lang: str):
    await message.answer("📍 Geolokatsiya yuborasizmi:" if lang == "uz" else "📍 Отправите геолокацию?", reply_markup=geolocation_keyboard(lang) if callable(geolocation_keyboard) else geolocation_keyboard())
    await state.set_state(ServiceOrderStates.asking_for_location)

# ---------- Geolokatsiya qarori ----------
@router.callback_query(F.data.in_(["send_location_yes", "send_location_no"]), StateFilter(ServiceOrderStates.asking_for_location))
async def geo_decision(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id) or "uz"
    try:
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)

        if callback.data == "send_location_yes":
            location_keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📍 Joylashuvni yuborish" if lang == "uz" else "📍 Отправить локацию", request_location=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await callback.message.answer("📍 Joylashuvingizni yuboring:" if lang == "uz" else "📍 Отправьте вашу локацию:", reply_markup=location_keyboard)
            await state.set_state(ServiceOrderStates.waiting_for_location)
        else:
            await show_service_order_confirmation(callback.message, state, lang)
    except Exception as e:
        logger.error(f"Error: {e}")
        await callback.answer("❌ Xatolik yuz berdi.", show_alert=True)

# ---------- Lokatsiyani qabul qilish ----------
@router.message(StateFilter(ServiceOrderStates.waiting_for_location), F.location)
async def get_geo(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    try:
        await state.update_data(geo=message.location)
        await message.answer("✅ Joylashuv qabul qilindi!" if lang == "uz" else "✅ Геолокация получена!", reply_markup=ReplyKeyboardRemove() if callable(ReplyKeyboardRemove) else ReplyKeyboardRemove())
        await show_service_order_confirmation(message, state, lang)
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Попробуйте еще раз.")

# ---------- Lokatsiyani matn bilan kiritish ----------
@router.message(StateFilter(ServiceOrderStates.waiting_for_location), F.text)
async def get_location_text(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    try:
        await state.update_data(location=message.text)
        await message.answer("✅ Joylashuv qabul qilindi!" if lang == "uz" else "✅ Геолокация получена!", reply_markup=ReplyKeyboardRemove() if callable(ReplyKeyboardRemove) else ReplyKeyboardRemove())
        await show_service_order_confirmation(message, state, lang)
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Попробуйте еще раз.")

# ---------- Tasdiqlash oynasi ----------
async def show_service_order_confirmation(message: Message, state: FSMContext, lang: str):
    try:
        data = await state.get_data()
        region = data.get('selected_region') or data.get('region')
        geo = data.get('geo')
        location_text = data.get('location')

        if geo:
            geo_text = f"{geo.latitude}, {geo.longitude}"
        elif location_text:
            geo_text = location_text
        else:
            geo_text = "Berilmagan" if lang == "uz" else "Не указана"

        # Ma'lumotlarni olish
        region_name = normalize_region(region) if region else "Tanlanmagan"
        abonent_type = data.get('abonent_type') or "Tanlanmagan"
        abonent_id = data.get('abonent_id') or "Kiritilmagan"
        phone = data.get('phone') or "Kiritilmagan"
        reason = data.get('reason') or data.get('description') or "Kiritilmagan"
        address = data.get('address') or "Kiritilmagan"
        media_status = "✅ Mavjud" if data.get('media_id') else "❌ Yo'q"
        
        summary_msg = (
            "📋 <b>Texnik xizmat arizasi ma'lumotlari:</b>\n\n" +
            f"🌍 <b>Hudud:</b> {region_name}\n" +
            f"👤 <b>Abonent turi:</b> {abonent_type}\n" +
            f"🆔 <b>Abonent ID:</b> {abonent_id}\n" +
            f"📞 <b>Telefon:</b> {phone}\n" +
            f"📝 <b>Muammo:</b> {reason}\n" +
            f"📍 <b>Manzil:</b> {address}\n" +
            f"🗺 <b>Joylashuv:</b> {geo_text}\n" +
            f"📷 <b>Media:</b> {media_status}\n\n" +
            "Ma'lumotlar to'g'rimi?"
        ) if lang == "uz" else (
            "📋 <b>Данные по заявке в техподдержку:</b>\n\n" +
            f"🌍 <b>Регион:</b> {region_name}\n" +
            f"👤 <b>Тип абонента:</b> {abonent_type}\n" +
            f"🆔 <b>ID абонента:</b> {abonent_id}\n" +
            f"📞 <b>Телефон:</b> {phone}\n" +
            f"📝 <b>Проблема:</b> {reason}\n" +
            f"📍 <b>Адрес:</b> {address}\n" +
            f"🗺 <b>Локация:</b> {geo_text}\n" +
            f"📷 <b>Медиа:</b> {media_status}\n\n" +
            "Все верно?"
        )
        await message.answer(summary_msg, reply_markup=confirmation_inline_kb(lang), parse_mode="HTML")
        await state.set_state(ServiceOrderStates.confirming_service)
    except Exception as e:
        logger.error(f"Error in show_service_order_confirmation: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Попробуйте еще раз.")

# ---------- Yakuniy tasdiqlash / Qayta boshlash ----------
@router.callback_query(F.data.in_(["confirm_service_yes", "confirm_service_no"]), StateFilter(ServiceOrderStates.confirming_service))
async def handle_service_confirmation(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id) or "uz"
    try:
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)

        if callback.data == "confirm_service_yes":
            data = await state.get_data()
            geo = data.get('geo')
            await finish_service_order(callback, state, lang, geo=geo)
        else:
            await callback.message.answer("🔄 Ariza qayta boshlanmoqda...\n\nIltimos, hududni tanlang:" if lang == "uz" else "🔄 Заявка начинается заново...\n\nПожалуйста, выберите регион:", reply_markup=get_client_regions_keyboard(lang) if callable(get_client_regions_keyboard) else get_client_regions_keyboard())
            await state.clear()
            await state.set_state(ServiceOrderStates.selecting_region)
    except Exception as e:
        logger.error(f"Error in handle_service_confirmation: {e}")
        await callback.answer("❌ Xatolik yuz berdi.", show_alert=True)

# ---------- Yaratish (finish) ----------
async def finish_service_order(callback_or_message, state: FSMContext, lang: str, geo=None):
    try:
        # Prevent bot from creating service orders
        if callback_or_message.from_user.id == settings.BOT_ID:
            logger.warning(f"Bot attempted to create service order, ignoring")
            return
            
        data = await state.get_data()
        region = data.get('selected_region') or data.get('region')
        region_db_value = (region or '').lower()

        user_record = await get_user_by_telegram_id(callback_or_message.from_user.id)
        if user_record is None:
            from database.basic.user import ensure_user
            user_record = await ensure_user(
                telegram_id=callback_or_message.from_user.id,
                full_name=callback_or_message.from_user.full_name,
                username=callback_or_message.from_user.username,
                role='client'
            )
        
        if user_record is None or user_record.get('id') == 0 or user_record.get('id') is None:
            # If user creation failed or returned bot user (id=0), we cannot proceed
            error_msg = "❌ Foydalanuvchi ma'lumotlari yaratilmadi. Qaytadan urinib ko'ring." if lang == "uz" else "❌ Не удалось создать данные пользователя. Попробуйте еще раз."
            if hasattr(callback_or_message, 'message'):
                # It's a CallbackQuery
                await callback_or_message.message.answer(error_msg, reply_markup=get_client_main_menu(lang) if callable(get_client_main_menu) else get_client_main_menu())
            else:
                # It's a Message
                await callback_or_message.answer(error_msg, reply_markup=get_client_main_menu(lang) if callable(get_client_main_menu) else get_client_main_menu())
            await state.clear()
            return
            
        user = dict(user_record)
        
        # Double check that user_id is valid
        if not user.get('id') or user.get('id') == 0:
            error_msg = "❌ Foydalanuvchi ID noto'g'ri. Qaytadan urinib ko'ring." if lang == "uz" else "❌ Неверный ID пользователя. Попробуйте еще раз."
            if hasattr(callback_or_message, 'message'):
                await callback_or_message.message.answer(error_msg, reply_markup=get_client_main_menu(lang) if callable(get_client_main_menu) else get_client_main_menu())
            else:
                await callback_or_message.answer(error_msg, reply_markup=get_client_main_menu(lang) if callable(get_client_main_menu) else get_client_main_menu())
            await state.clear()
            return

        if geo:
            geo_str = f"{geo.latitude},{geo.longitude}"
        elif data.get('location'):
            geo_str = data.get('location')
        else:
            geo_str = None

        business_type = 'B2B' if data.get('abonent_type') == 'B2B' else 'B2C'
        
        request_id = await create_service_order(
            user.get('id'),
            region_db_value,
            data.get('abonent_id'),
            data.get('address'),
            data.get('reason'),
            data.get('media_id'),
            geo_str,
            business_type
        )
        
        conn = await asyncpg.connect(settings.DB_URL)
        try:
            app_number_result = await conn.fetchrow(
                "SELECT application_number FROM technician_orders WHERE id = $1",
                request_id
            )
            application_number = app_number_result['application_number'] if app_number_result else f"TECH-{business_type}-{request_id:04d}"
            
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
                application_number, user.get('id') 
            )
        finally:
            await conn.close()

        if data.get('media_id') and data.get('media_type') and user.get('id') != 0:
            media_path = await save_service_media_file(
                data['media_id'],
                data['media_type'],
                user.get('id'),
                request_id
            )
            if media_path:
                logger.info(f"Media file saved: {media_path}")
            else:
                logger.warning(f"Failed to save media file for order {request_id}")

        # Guruhga xabar (hozir UZda; xohlasangiz ru versiyasini ham shunday qo'shamiz)
        group_notification_sent = False
        if settings.ZAYAVKA_GROUP_ID:
            try:
                geo_text = ""
                if geo:
                    geo_text = f"\n📍 <b>Lokatsiya:</b> <a href='https://maps.google.com/?q={geo.latitude},{geo.longitude}'>Google Maps</a>"
                elif data.get('location'):
                    geo_text = f"\n📍 <b>Lokatsiya:</b> {data.get('location')}"

                phone_for_msg = data.get('phone') or user.get('phone') or '-'
                default_name = "Noma'lum"
                client_name_for_msg = user.get('full_name') or callback_or_message.from_user.full_name or default_name
                region_name = normalize_region(region) if region else "Tanlanmagan"
                
                problem_text = (data.get('reason') or data.get('description') or '')[:50]
                if len(problem_text) < len(data.get('reason') or data.get('description') or ''):
                    problem_text += "..."
                
                address_text = (data.get('address') or '')[:80]
                if len(address_text) < len(data.get('address') or ''):
                    address_text += "..."
                
                # Media status text
                media_status = "✅ Mavjud" if data.get('media_id') else "❌ Yo'q"
                
                group_msg = (
                    f"🔧 <b>YANGI TEXNIK XIZMAT ARIZASI</b>\n"
                    f"{'='*30}\n"
                    f"🆔 <b>ID:</b> <code>{application_number}</code>\n"
                    f"👤 <b>Mijoz:</b> {client_name_for_msg}\n"
                    f"📞 <b>Tel:</b> {phone_for_msg}\n"
                    f"🏢 <b>Region:</b> {region_name}\n"
                    f"🏢 <b>Abonent:</b> {data.get('abonent_type')} - {data.get('abonent_id')}\n"
                    f"📍 <b>Manzil:</b> {address_text}\n"
                    f"📝 <b>Muammo:</b> {problem_text}\n"
                    f"{geo_text}\n"
                    f"📷 <b>Media:</b> {media_status}\n"
                    f"🕐 <b>Vaqt:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                    f"{'='*30}"
                )

                if data.get('media_id'):
                    if data.get('media_type') == 'photo':
                        await bot.send_photo(
                            chat_id=settings.ZAYAVKA_GROUP_ID,
                            photo=data['media_id'],
                            caption=group_msg,
                            parse_mode='HTML'
                        )
                    elif data.get('media_type') == 'video':
                        await bot.send_video(
                            chat_id=settings.ZAYAVKA_GROUP_ID,
                            video=data['media_id'],
                            caption=group_msg,
                            parse_mode='HTML'
                        )
                else:
                    await bot.send_message(
                        chat_id=settings.ZAYAVKA_GROUP_ID,
                        text=group_msg,
                        parse_mode='HTML'
                    )

                if geo:
                    await bot.send_location(
                        settings.ZAYAVKA_GROUP_ID,
                        latitude=geo.latitude,
                        longitude=geo.longitude
                    )
                
                group_notification_sent = True
                logger.info(f"Group notification sent successfully for service order {application_number}")

            except Exception as group_error:
                logger.error(f"Group notification error: {group_error}")
                if hasattr(settings, 'ADMIN_GROUP_ID') and settings.ADMIN_GROUP_ID:
                    try:
                        await bot.send_message(
                            chat_id=settings.ADMIN_GROUP_ID,
                            text=f"⚠️ Guruhga xabar yuborishda xato:\n{group_msg}\n\nXato: {group_error}",
                            parse_mode='HTML'
                        )
                    except:
                        pass
        else:
            logger.warning("ZAYAVKA_GROUP_ID not configured - skipping group notification")

        # Foydalanuvchiga muvaffaqiyat xabari — tilga mos
        region_name = normalize_region(region) if region else "Tanlanmagan"
        abonent_id = data.get('abonent_id') or "Kiritilmagan"
        address = data.get('address') or "Kiritilmagan"
        
        # Xabar uzunligini cheklash
        region_name = region_name[:50] if len(region_name) > 50 else region_name
        abonent_id = abonent_id[:20] if len(abonent_id) > 20 else abonent_id
        address = address[:100] if len(address) > 100 else address
        
        success_msg = (
            f"✅ <b>Texnik xizmat arizangiz qabul qilindi!</b>\n\n"
            f"🆔 <b>Ariza raqami:</b> <code>{application_number}</code>\n"
            f"⏰ <b>Texnik mutaxassis tez orada bog'lanadi!</b>"
        ) if lang == "uz" else (
            f"✅ <b>Ваша заявка в техподдержку принята!</b>\n\n"
            f"🆔 <b>Номер:</b> <code>{application_number}</code>\n"
            f"⏰ <b>Специалист свяжется с вами в ближайшее время!</b>"
        )

        if hasattr(callback_or_message, 'message'):
            await callback_or_message.message.answer(success_msg, parse_mode='HTML', reply_markup=get_client_main_menu(lang) if callable(get_client_main_menu) else get_client_main_menu())
        else:
            await callback_or_message.answer(success_msg, parse_mode='HTML', reply_markup=get_client_main_menu(lang) if callable(get_client_main_menu) else get_client_main_menu())
        await state.clear()

    except Exception as e:
        logger.error(f"Error in finish_service_order: {e}")
        error_msg = "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring." if lang == "uz" else "❌ Произошла ошибка. Попробуйте еще раз."
        if hasattr(callback_or_message, 'message'):
            # It's a CallbackQuery
            await callback_or_message.message.answer(error_msg, reply_markup=get_client_main_menu(lang) if callable(get_client_main_menu) else get_client_main_menu())
        else:
            # It's a Message
            await callback_or_message.answer(error_msg, reply_markup=get_client_main_menu(lang) if callable(get_client_main_menu) else get_client_main_menu())
        await state.clear()

# ---------- Bekor qilish ----------
@router.callback_query(F.data == "service_cancel")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id) or "uz"
    try:
        await callback.answer("Bekor qilindi" if lang == "uz" else "Отменено")
        await callback.message.edit_reply_markup(reply_markup=None)

        await state.clear()
        await callback.message.answer("❌ Texnik xizmat arizasi bekor qilindi" if lang == "uz" else "❌ Заявка в техподдержку отменена", reply_markup=get_client_main_menu(lang) if callable(get_client_main_menu) else get_client_main_menu())
    except Exception as e:
        logger.error(f"Error in cancel_order: {e}")
        await callback.answer("❌ Xatolik yuz berdi.", show_alert=True)
