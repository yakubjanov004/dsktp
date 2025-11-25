from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.enums.parse_mode import ParseMode
import os
import logging

from database.basic.language import get_user_language

router = Router()
logger = logging.getLogger(__name__)

# --- Lokalizatsiya helper ---
def text_by_lang(lang: str) -> str:
    if lang == "ru":
        return (
            "🛜 **ОФИЦИАЛЬНЫЙ БОТ UZTELECOM**\n\n"
            "✨ *Через нашего бота вы можете воспользоваться следующими услугами:*\n\n"
            "🔧 **Техническая поддержка** — быстро решайте ваши проблемы\n"
            "📞 **Заявка на подключение** — оставьте заявку на новое подключение\n"
            "📋 **Мои заявки** — отслеживайте все свои заявки\n"
            "👤 **Профиль** — управляйте личными данными\n"
            "📞 **Контакты** — свяжитесь с нашим сервисным центром\n\n"
            "💡 *Бот работает 24/7 и оперативно обрабатывает ваши запросы!*\n\n"
            "🌟 **Наши преимущества:**\n"
            "• Быстрый сервис\n"
            "• Профессиональный подход\n"
            "• Качественная техподдержка\n"
            "• Постоянная поддержка\n\n"
            "#UzTelecom #ОфициальныйБот #Техподдержка #Подключение #Заявка #ОнлайнСервис #Ташкент"
        )
    # default: uz
    return (
        "🛜 **UZTELECOM RASMIY BOTI**\n\n"
        "✨ *Bizning bot orqali siz quyidagi xizmatlardan foydalanishingiz mumkin:*\n\n"
        "🔧 **Texnik xizmat** — muammolaringizni tez hal qiling\n"
        "📞 **Ulanish buyurtmasi** — yangi ulanish uchun ariza bering\n"
        "📋 **Buyurtmalarim** — barcha arizalaringizni kuzatib boring\n"
        "👤 **Profil** — shaxsiy ma'lumotlaringizni boshqaring\n"
        "📞 **Aloqa** — xizmat markazimiz bilan bog'laning\n\n"
        "💡 *Bot 24/7 ishlaydi va sizning so'rovlaringizni tezkor qayta ishlaydi!*\n\n"
        "🌟 **Bizning afzalliklarimiz:**\n"
        "• Tezkor xizmat ko'rsatish\n"
        "• Professional yondashuv\n"
        "• Sifatli texnik yordam\n"
        "• Doimiy qo'llab-quvvatlash\n\n"
        "#UzTelecom #RasmiyBot #TexnikXizmat #Ulanish #Buyurtma #OnlineXizmat #Toshkent"
    )

@router.message(F.text.in_(["📄 Bot qo'llanmasi", "📄Инструкция по использованию бота"]))
async def bot_guide_handler(message: Message):
    lang = await get_user_language(message.from_user.id) or "uz"
    caption_or_text = text_by_lang(lang)

    # Video faylni yuborish
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    video_path = os.path.join(base_dir, "static", "videos", "uztelecom.MP4")

    if os.path.exists(video_path):
        video = FSInputFile(video_path)
        await message.answer_video(
            video=video,
            caption=caption_or_text,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # Agar video topilmasa, faqat matn yuboramiz
        await message.answer(caption_or_text, parse_mode=ParseMode.MARKDOWN)
