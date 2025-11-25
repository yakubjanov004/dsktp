# handlers/call_center/webapp.py
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database.basic.language import get_user_language
from config import settings
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text.in_(["💬 Onlayn Chat Web App", "💬 Онлайн Чат Web App"]))
async def webapp_handler(message: Message):
    """Handle webapp button for call center operators/supervisors"""
    user_lang = await get_user_language(message.from_user.id)
    webapp_url = settings.WEBAPP_URL
    
    # Telegram ID ni URL'ga qo'shish
    telegram_id = message.from_user.id
    if telegram_id:
        separator = "&" if "?" in webapp_url else "?"
        webapp_url_with_id = f"{webapp_url}{separator}telegram_id={telegram_id}"
    else:
        webapp_url_with_id = webapp_url
    
    if user_lang == "ru":
        if webapp_url.startswith("https://"):
            # HTTPS URL - inline keyboard button ishlatish mumkin
            webapp_text = (
                "💬 <b>Онлайн Чат Web App</b>\n\n"
                "Откройте веб-приложение для работы с чатами в реальном времени:\n\n"
            )
            button_text = "🌐 Открыть веб-приложение"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=button_text, url=webapp_url_with_id)]
            ])
            await message.answer(webapp_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            # HTTP URL - oddiy text message
            webapp_text = (
                "💬 <b>Онлайн Чат Web App</b>\n\n"
                "Для работы с чатами в реальном времени, откройте веб-приложение:\n\n"
                f"🌐 <code>{webapp_url_with_id}</code>\n\n"
                "⚠️ <i>Примечание: Скопируйте ссылку выше и откройте в браузере</i>"
            )
            await message.answer(webapp_text, parse_mode="HTML")
    else:
        if webapp_url.startswith("https://"):
            # HTTPS URL - inline keyboard button ishlatish mumkin
            webapp_text = (
                "💬 <b>Onlayn Chat Web App</b>\n\n"
                "Real vaqtda chatlar bilan ishlash uchun web ilovani oching:\n\n"
            )
            button_text = "🌐 Web ilovani ochish"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=button_text, url=webapp_url_with_id)]
            ])
            await message.answer(webapp_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            # HTTP URL - oddiy text message
            webapp_text = (
                "💬 <b>Onlayn Chat Web App</b>\n\n"
                "Real vaqtda chatlar bilan ishlash uchun web ilovani oching:\n\n"
                f"🌐 <code>{webapp_url_with_id}</code>\n\n"
                "⚠️ <i>Eslatma: Yuqoridagi linkni nusxalab, brauzerda oching</i>"
            )
            await message.answer(webapp_text, parse_mode="HTML")

