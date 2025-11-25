from aiogram import Router, F
from aiogram.types import Message
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text.in_(["📝 Buyurtmalar", "📝 Заказы"]))
async def orders_handler(message: Message):
    await message.answer("📝 Buyurtmalar\n\nBu yerda buyurtmalar boshqariladi.\n\n👤 Rol: Call Center Supervisor")
