"""
Linux server uchun main script
Bu fayl production Linux server muhitida ishlatish uchun optimallashtirilgan.
- Faqat FastAPI va Bot ishlaydi
- Webapp alohida ishlaydi (nginx orqali serve qilinadi)
- Windows uchun main_windows.py faylini ishlatish kerak.
"""
import asyncio
import sys
import logging
import threading
import signal
import atexit

from config import settings
from loader import create_bot_and_dp
from handlers import router as handlers_router
from utils.directory_utils import setup_media_structure, setup_static_structure

# Logger'ni olish
logger = logging.getLogger(__name__)

# Global thread reference (cleanup uchun)
api_thread = None

# Setup media and static directory structures
try:
    setup_media_structure()
    setup_static_structure()
    logger.info("Media va static papkalar muvaffaqiyatli yaratildi")
except Exception as e:
    logger.exception("Directory setup failed", exc_info=True)
    sys.exit(1)

def run_api_server():
    """Run FastAPI server in background thread"""
    import uvicorn
    try:
        logger.info(
            "Starting FastAPI server on %s (bind=%s)",
            settings.backend_http_url,
            settings.api_bind_host,
        )
        uvicorn.run(
            "api.server:app",
            host=settings.api_bind_host,
            port=settings.API_PORT,
            log_level="info",
            access_log=True
        )
    except Exception as e:
        logger.exception(f"API server error: {e}", exc_info=True)


def cleanup_processes():
    """Cleanup all threads on exit (Linux server specific)"""
    global api_thread
    
    try:
        logger.info("Cleaning up processes...")
        # API thread daemon thread bo'lgani uchun avtomatik to'xtatiladi
        # Agar kerak bo'lsa, bu yerda qo'shimcha cleanup qilish mumkin
    except Exception as e:
        logger.error(f"Error in cleanup_processes: {e}")

# Register cleanup function
atexit.register(cleanup_processes)

# Webapp server kodini olib tashladik - server da nginx orqali serve qilinadi


async def main():
    global api_thread
    
    # Start FastAPI server in background thread
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    logger.info(
        "FastAPI server thread started on %s (bind=%s)",
        settings.backend_http_url,
        settings.api_bind_host,
    )
    
    # Server da webapp alohida ishlaydi (nginx orqali serve qilinadi)
    # Production da webapp build qilingan va nginx orqali serve qilinadi
    logger.info("Webapp server da nginx orqali serve qilinadi (alohida ishlaydi)")
    
    # Server qayta ishga tushganda material recovery
    try:
        from database.technician.materials import recover_technician_materials_after_crash, recover_warehouse_materials_after_crash
        await recover_technician_materials_after_crash()
        await recover_warehouse_materials_after_crash()
        logger.info("Material recovery completed successfully")
    except Exception as e:
        logger.error(f"Material recovery failed: {e}")
    
    bot, dp = await create_bot_and_dp()
    dp.include_router(handlers_router)
    
    # Pollingni barqaror qilish uchun backoff bilan qayta urinib ko'rish
    base_delay = 1
    max_delay = 60
    attempt = 0
    
    while True:
        try:
            logger.info("Bot starting...")
            await dp.start_polling(bot)
            break  # muvaffaqiyatli tugasa siklni to'xtatamiz
        except asyncio.CancelledError:
            logger.info("Bot stopped by user")
            break
        except Exception:
            attempt += 1
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            logger.exception("Polling error. Reconnecting after %s seconds...", delay, exc_info=True)
            await asyncio.sleep(delay)
            continue
        finally:
            try:
                await bot.session.close()
            except Exception:
                pass
            logger.info("Bot session closed")

def signal_handler(signum, frame):
    """Handle signals (SIGTERM, SIGINT) gracefully - Linux specific"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    cleanup_processes()
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers (Linux)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
        cleanup_processes()
        sys.exit(0)
    except Exception as e:
        logger.exception("Main error", exc_info=True)
        cleanup_processes()
        sys.exit(1)
