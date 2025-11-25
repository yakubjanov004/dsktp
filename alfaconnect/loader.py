import logging
import sys
import warnings
import asyncio
from logging.handlers import RotatingFileHandler
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import ClientTimeout, TCPConnector
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings
from middlewares import ErrorHandlingMiddleware
import os

# =========================================================
# LOGGING CONFIGURATION - loader.py ichida to'liq
# =========================================================

def setup_logging():
    """Logging tizimini sozlash - logs/bot.log va logs/errors.log"""
    
    # logs papkasini yaratish
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Root logger'ni tozalash
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # =========================================================
    # BOT.LOG - Barcha bot faoliyatlari (INFO daraja)
    # =========================================================
    
    # Bot log uchun formatter
    bot_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Bot log fayl handler (RotatingFileHandler)
    bot_file_handler = RotatingFileHandler(
        os.path.join(log_dir, "bot.log"),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    bot_file_handler.setLevel(logging.INFO)
    bot_file_handler.setFormatter(bot_formatter)
    
    # Bot log console handler (terminalga ham chiqarish)
    bot_console_handler = logging.StreamHandler(sys.stdout)
    bot_console_handler.setLevel(logging.INFO)
    bot_console_handler.setFormatter(bot_formatter)
    
    # =========================================================
    # ERRORS.LOG - Barcha xatoliklar (WARNING va ERROR daraja)
    # =========================================================
    
    # Error log uchun formatter
    error_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Error log fayl handler (RotatingFileHandler)
    error_file_handler = RotatingFileHandler(
        os.path.join(log_dir, "errors.log"),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding="utf-8"
    )
    error_file_handler.setLevel(logging.WARNING)
    error_file_handler.setFormatter(error_formatter)
    
    # Error log console handler (terminalga ham chiqarish)
    error_console_handler = logging.StreamHandler(sys.stderr)
    error_console_handler.setLevel(logging.WARNING)
    error_console_handler.setFormatter(error_formatter)
    
    # =========================================================
    # LOGGER'LARNI SOZLASH
    # =========================================================
    
    # Root logger'ga handler'lar qo'shish
    root_logger.addHandler(bot_file_handler)
    root_logger.addHandler(bot_console_handler)
    root_logger.addHandler(error_file_handler)
    root_logger.addHandler(error_console_handler)
    root_logger.setLevel(logging.INFO)
    
    # =========================================================
    # AIOGRAM LOGGER'LARNI SOZLASH
    # =========================================================
    
    # Aiogram logger'larini sozlash
    aiogram_logger = logging.getLogger("aiogram")
    aiogram_logger.setLevel(logging.WARNING)  # Faqat WARNING va ERROR
    
    # Aiogram client logger'ini sozlash
    aiogram_client_logger = logging.getLogger("aiogram.client")
    aiogram_client_logger.setLevel(logging.WARNING)
    
    # Aiogram dispatcher logger'ini sozlash
    aiogram_dispatcher_logger = logging.getLogger("aiogram.dispatcher")
    aiogram_dispatcher_logger.setLevel(logging.WARNING)
    
    # =========================================================
    # ASYNCIO LOGGER'LARNI SOZLASH
    # =========================================================
    
    # Asyncio logger'larini sozlash
    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.setLevel(logging.WARNING)
    
    # =========================================================
    # WARNINGS'LARNI LOG QILISH
    # =========================================================
    
    # Warnings'larni log qilish uchun handler
    warnings_logger = logging.getLogger("py.warnings")
    warnings_logger.addHandler(error_file_handler)
    warnings_logger.addHandler(error_console_handler)
    warnings_logger.setLevel(logging.WARNING)
    
    # =========================================================
    # UNCAUGHT EXCEPTIONS'LARNI LOG QILISH
    # =========================================================
    
    def handle_exception(exc_type, exc_value, exc_traceback):
        """Tutib olinmagan exception'larni log qilish"""
        if issubclass(exc_type, KeyboardInterrupt):
            # KeyboardInterrupt'ni e'tiborsiz qoldirish
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # Error log'ga yozish
        error_logger = logging.getLogger("uncaught_exception")
        error_logger.error(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    
    # Uncaught exception handler'ni o'rnatish
    sys.excepthook = handle_exception
    
    # =========================================================
    # ASYNCIO EXCEPTION HANDLER
    # =========================================================
    
    def handle_asyncio_exception(loop, context):
        """Asyncio exception'larni log qilish"""
        exception = context.get('exception')
        if exception:
            error_logger = logging.getLogger("asyncio_exception")
            error_logger.error(
                f"Asyncio exception: {context.get('message', 'Unknown error')}",
                exc_info=exception
            )
        else:
            error_logger = logging.getLogger("asyncio_exception")
            error_logger.warning(f"Asyncio warning: {context.get('message', 'Unknown warning')}")
    
    # Asyncio exception handler'ni o'rnatish (faqat running loop mavjud bo'lsa)
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None
    if running_loop is not None:
        running_loop.set_exception_handler(handle_asyncio_exception)
    
    # =========================================================
    # LOGGING SOZLASH TUGADI
    # =========================================================
    
    # Bot logger'ni yaratish va test qilish
    bot_logger = logging.getLogger("AlfaConnectBot")
    bot_logger.info("Logging tizimi muvaffaqiyatli sozlandi!")
    bot_logger.info(f"Bot log: {os.path.join(log_dir, 'bot.log')}")
    bot_logger.info(f"Error log: {os.path.join(log_dir, 'errors.log')}")
    
    return bot_logger

# =========================================================
# LOGGING'NI SOZLASH
# =========================================================

logger = setup_logging()

# =========================================================
# LEGACY IMPORTLAR UCHUN PROXY OBYEKTLAR (bot/dp)
# =========================================================

class _LazyProxy:
    """Run-time da haqiqiy obyektga delegatsiya qiluvchi oddiy proxy.

    loader.bot/dp import qilingan modullarda import paytida mavjud bo'ladi,
    lekin haqiqiy obyekt create_bot_and_dp() ichida o'rnatilgach ishlaydi.
    """
    def __init__(self):
        self._target = None

    def _set(self, target):
        self._target = target
        return target

    def __getattr__(self, name):
        if self._target is None:
            raise RuntimeError("Object not initialized yet. Ensure create_bot_and_dp() is called before use.")
        return getattr(self._target, name)


# Global proxy instances (legacy imports: `from loader import bot, dp`)
bot = _LazyProxy()
dp = _LazyProxy()

# =========================================================
# BOT/DISPATCHER YARATISH UCHUN FABRIKA
# =========================================================

async def create_bot_and_dp() -> tuple[Bot, Dispatcher]:
    """Running event loop ichida Bot va Dispatcher ni yaratadi."""
    # Use simple integer timeout for aiogram compatibility
    session = AiohttpSession(timeout=30)

    real_bot = Bot(
        token=settings.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    real_dp = Dispatcher(storage=MemoryStorage())

    # Middleware'ni qo'shish
    real_dp.update.middleware(ErrorHandlingMiddleware(bot=real_bot))

    logger.info("Bot va Dispatcher muvaffaqiyatli yaratildi!")
    logger.info("ErrorHandlingMiddleware qo'shildi!")

    # Legacy proxy obyektlarni to'ldirish
    bot._set(real_bot)
    dp._set(real_dp)

    return real_bot, real_dp
