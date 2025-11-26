"""
Windows uchun main script
Bu fayl Windows operatsion tizimida ishlatish uchun optimallashtirilgan.
Ngrok integratsiyasi qo'shilgan - avtomatik HTTPS tunnel yaratadi.
"""
import asyncio
import sys
import logging
import threading
import subprocess
import os
import signal
import atexit
import time
import socket
from pathlib import Path

from config import settings
from loader import create_bot_and_dp
from handlers import router as handlers_router
from utils.directory_utils import setup_media_structure, setup_static_structure

# Logger'ni olish (avval yaratish kerak)
logger = logging.getLogger(__name__)

# ============================================
# NGROK CONFIGURATION
# ============================================
NGROK_AUTHTOKEN = "350nMzK4nfSGrIzUt2c6pagvoJk_3N3BEX5zjSDUpAgQeU9Hb"
NGROK_ENABLED = True  # Ngrok'ni yoqish/o'chirish

# Global ngrok process reference
ngrok_process = None
ngrok_backend_url = None  # Backend (API) uchun ngrok URL
ngrok_frontend_url = None  # Frontend (WebApp) uchun ngrok URL

# Konfiguratsiya (.env orqali)
API_PORT = settings.API_PORT
API_BIND_HOST = settings.api_bind_host
PUBLIC_HOST = settings.public_host
WEBAPP_PORT = settings.resolved_webapp_port

# Development mode'da lokal IP dan foydalanish
if settings.ENVIRONMENT == "development":
    # To'g'ri lokal IP ni olish (tarmoq interfeysi)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = socket.gethostbyname(socket.gethostname())
    
    # Agar WEBAPP_URL production domen bo'lsa, uni lokal IP ga o'zgartirish
    # Ngrok URL larni o'zgartirmaslik (ular development uchun HTTPS tunnel)
    if settings.WEBAPP_URL and "ngrok" in settings.WEBAPP_URL:
        WEBAPP_URL = settings.WEBAPP_URL
        logger.info(f"✅ Using ngrok tunnel URL: {WEBAPP_URL}")
    elif settings.WEBAPP_URL and ("darrov.uz" in settings.WEBAPP_URL or settings.WEBAPP_URL.startswith("https://")):
        WEBAPP_URL = f"http://{local_ip}:{WEBAPP_PORT}"
        logger.warning(f"⚠️  Development mode detected! WEBAPP_URL changed from {settings.WEBAPP_URL} to {WEBAPP_URL}")
        # Settings'ni ham yangilash (keyboards uchun)
        settings.WEBAPP_URL = WEBAPP_URL
    else:
        WEBAPP_URL = settings.WEBAPP_URL
    # PUBLIC_HOST ni ham lokal IP ga o'zgartirish (agar localhost bo'lsa)
    if PUBLIC_HOST in ["localhost", "127.0.0.1"]:
        PUBLIC_HOST = local_ip
        logger.warning(f"⚠️  PUBLIC_HOST changed to {PUBLIC_HOST} for network access")
        # BACKEND URL'larni ham yangilash
        BACKEND_HTTP_URL = f"http://{PUBLIC_HOST}:{API_PORT}"
        BACKEND_WS_URL = f"ws://{PUBLIC_HOST}:{API_PORT}"
    else:
        BACKEND_HTTP_URL = settings.backend_http_url
        BACKEND_WS_URL = settings.backend_ws_url
else:
    WEBAPP_URL = settings.WEBAPP_URL
    BACKEND_HTTP_URL = settings.backend_http_url
    BACKEND_WS_URL = settings.backend_ws_url

# Global process va thread references (cleanup uchun)
running_processes = []

# Setup media and static directory structures
try:
    setup_media_structure()
    setup_static_structure()
    logger.info("Media va static papkalar muvaffaqiyatli yaratildi")
except Exception as e:
    logger.exception("Directory setup failed", exc_info=True)
    sys.exit(1)

def run_ngrok_tunnels() -> tuple[str | None, str | None]:
    """
    Ngrok tunnels ishga tushirish - backend va frontend uchun.
    
    Returns:
        Tuple (backend_url, frontend_url) yoki (None, None)
    """
    global ngrok_process, ngrok_backend_url, ngrok_frontend_url
    
    if not NGROK_ENABLED:
        logger.info("Ngrok is disabled. Skipping tunnel creation.")
        return None, None
    
    try:
        # Avval mavjud ngrok jarayonlarini to'xtatish
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "ngrok.exe"],
                capture_output=True,
                shell=True,
                timeout=5
            )
            time.sleep(2)
        except Exception:
            pass  # Agar ngrok ishlamayotgan bo'lsa, xato bo'ladi - bu normal
        
        # Ngrok config fayli yo'lini olish
        current_dir = Path(__file__).parent.absolute()
        ngrok_config_path = current_dir / "ngrok.yml"
        
        if not ngrok_config_path.exists():
            logger.error(f"❌ Ngrok config file not found: {ngrok_config_path}")
            return None, None
        
        # Ngrok tunnels ishga tushirish (config fayli orqali)
        logger.info(f"Starting ngrok tunnels from config: {ngrok_config_path}")
        ngrok_process = subprocess.Popen(
            ["ngrok", "start", "--all", "--config", str(ngrok_config_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        running_processes.append(ngrok_process)
        
        # Ngrok URL larni olish uchun kutish (API orqali)
        logger.info("Waiting for ngrok tunnels to start...")
        time.sleep(5)  # Ngrok ishga tushishi uchun kutish
        
        # Ngrok API orqali URL larni olish
        try:
            import urllib.request
            import json
            
            # Ngrok local API
            api_url = "http://127.0.0.1:4040/api/tunnels"
            
            backend_url = None
            frontend_url = None
            
            for attempt in range(10):
                try:
                    with urllib.request.urlopen(api_url, timeout=5) as response:
                        data = json.loads(response.read().decode())
                        tunnels = data.get("tunnels", [])
                        
                        for tunnel in tunnels:
                            public_url = tunnel.get("public_url", "")
                            tunnel_name = tunnel.get("name", "")
                            tunnel_config = tunnel.get("config", {})
                            tunnel_addr = tunnel_config.get("addr", "")
                            
                            if not public_url.startswith("https://"):
                                continue
                            
                            # Tunnel portiga qarab aniqlash
                            if ":8001" in tunnel_addr or tunnel_name == "backend":
                                backend_url = public_url
                                logger.info(f"✅ Backend tunnel: {backend_url}")
                            elif ":3200" in tunnel_addr or tunnel_name == "frontend":
                                frontend_url = public_url
                                logger.info(f"✅ Frontend tunnel: {frontend_url}")
                        
                        if backend_url and frontend_url:
                            ngrok_backend_url = backend_url
                            ngrok_frontend_url = frontend_url
                            return backend_url, frontend_url
                            
                except Exception as e:
                    logger.debug(f"Ngrok API attempt {attempt + 1} failed: {e}")
                
                time.sleep(2)
            
            # Agar hech bo'lmaganda bitta URL topilsa
            if backend_url or frontend_url:
                ngrok_backend_url = backend_url
                ngrok_frontend_url = frontend_url
                return backend_url, frontend_url
            
            logger.warning("Could not get ngrok URLs from API")
            return None, None
            
        except Exception as e:
            logger.error(f"Error getting ngrok URLs: {e}")
            return None, None
            
    except FileNotFoundError:
        logger.error("❌ Ngrok is not installed or not in PATH!")
        logger.error("   Please install ngrok: https://ngrok.com/download")
        return None, None
    except Exception as e:
        logger.error(f"Error starting ngrok tunnels: {e}")
        return None, None


def stop_ngrok_tunnels():
    """Ngrok tunnels'ni to'xtatish"""
    global ngrok_process, ngrok_backend_url, ngrok_frontend_url
    
    try:
        if ngrok_process and ngrok_process.poll() is None:
            logger.info("Stopping ngrok tunnels...")
            ngrok_process.terminate()
            time.sleep(1)
            if ngrok_process.poll() is None:
                ngrok_process.kill()
        
        # Barcha ngrok jarayonlarini to'xtatish
        subprocess.run(
            ["taskkill", "/F", "/IM", "ngrok.exe"],
            capture_output=True,
            shell=True
        )
        
        ngrok_process = None
        ngrok_backend_url = None
        ngrok_frontend_url = None
        logger.info("Ngrok tunnels stopped")
    except Exception as e:
        logger.warning(f"Error stopping ngrok: {e}")


def run_api_server():
    """Run FastAPI server in a background process"""
    global running_processes
    try:
        logger.info(f"Starting FastAPI server on http://{PUBLIC_HOST}:{API_PORT} (bind={API_BIND_HOST})")
        
        # API portni tekshirish va agar band bo'lsa, oldingi processni to'xtatish
        if check_port_windows(API_PORT):
            logger.warning(f"Port {API_PORT} is already in use. Attempting to find and kill the process...")
            kill_process_on_port_windows(API_PORT)
            time.sleep(2)

        api_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.server:app", "--host", API_BIND_HOST, "--port", str(API_PORT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        running_processes.append(api_process)
        logger.info(f"FastAPI server started (PID: {api_process.pid})")

        def log_output(process, name):
            try:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        logger.info(f"[{name}] {line.strip()}")
            except Exception as e:
                logger.error(f"{name} output logging error: {e}")

        output_thread = threading.Thread(target=log_output, args=(api_process, "FastAPI"), daemon=True)
        output_thread.start()
        return api_process
    except Exception as e:
        logger.exception(f"API server error: {e}", exc_info=True)
        return None


def cleanup_processes():
    """Cleanup all processes and threads on exit (Windows specific)"""
    global running_processes
    
    # Ngrok'ni to'xtatish
    if NGROK_ENABLED:
        stop_ngrok_tunnels()
    
    if not running_processes:
        return
    
    logger.info(f"Cleaning up {len(running_processes)} processes...")
    
    # Avval barcha process'larni terminate qilish
    for process in running_processes:
        if process.poll() is None:  # Agar process hali ham ishlayotgan bo'lsa
            logger.info(f"Terminating process {process.pid}...")
            try:
                # Windows'da process'ni to'xtatish
                process.terminate()
            except Exception as e:
                logger.warning(f"Could not terminate process {process.pid}: {e}")
    
    # Kichik kutish (graceful shutdown uchun)
    time.sleep(2)
    
    # Agar hali ham ishlayotgan bo'lsa, force kill
    for process in running_processes:
        try:
            if process.poll() is None:  # Hali ham ishlayotgan bo'lsa
                logger.warning(f"Process {process.pid} did not terminate, forcing kill...")
                try:
                    # Windows'da process va uning child process'larini kill qilish
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        timeout=5,
                        shell=True
                    )
                except Exception as e:
                    logger.error(f"Failed to kill process {process.pid} with taskkill: {e}")
                    try:
                        process.kill()
                    except Exception as e2:
                        logger.error(f"Failed to kill process {process.pid}: {e2}")
            else:
                logger.info(f"Process {process.pid} terminated successfully.")
        except Exception as e:
            logger.error(f"Error cleaning up process: {e}")
    
    # Port'larni ham tozalash
    try:
        logger.info("Cleaning up ports...")
        kill_process_on_port_windows(API_PORT)
        kill_process_on_port_windows(WEBAPP_PORT)
    except Exception as e:
        logger.warning(f"Error cleaning up ports: {e}")
    
    running_processes = []


# Register cleanup function
atexit.register(cleanup_processes)

def kill_process_on_port_windows(port: int):
    """Windows da portni ishlatayotgan process ni topish va kill qilish"""
    try:
        # Windows da netstat orqali PID ni topish
        netstat_result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            shell=True
        )
        if netstat_result.stdout:
            found_pids = set()  # Duplicate PID larni oldini olish uchun
            for line in netstat_result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            pid_int = int(pid)
                            found_pids.add(pid_int)
                        except ValueError:
                            continue
            
            # Topilgan PID larni kill qilish (bir marta)
            # /T flag - child process'larni ham kill qilish
            for pid_int in found_pids:
                try:
                    logger.info(f"Attempting to kill process using port {port}: PID {pid_int} (with child processes)")
                    kill_result = subprocess.run(
                        ["taskkill", "/PID", str(pid_int), "/T", "/F"],
                        capture_output=True,
                        text=True,
                        shell=True,
                        timeout=5
                    )
                    if kill_result.returncode == 0:
                        logger.info(f"Successfully killed process {pid_int} and its children")
                    else:
                        # Process allaqachon to'xtatilgan bo'lishi mumkin
                        if "not found" in kill_result.stderr.lower() or "does not exist" in kill_result.stderr.lower():
                            logger.debug(f"Process {pid_int} already terminated")
                        else:
                            logger.warning(f"Could not kill process {pid_int}: {kill_result.stderr}")
                except subprocess.TimeoutExpired:
                    logger.warning(f"Timeout killing process {pid_int}")
                except Exception as e:
                    logger.warning(f"Error killing process {pid_int}: {e}")
            
            if found_pids:
                # Kichik kutish (process to'xtatilishiga)
                time.sleep(2)
                return True
    except Exception as e:
        logger.warning(f"Could not find or kill process on port {port}: {e}")
    return False

def get_local_ip_windows() -> str:
    """Windows da lokal IP manzilini olish (tarmoq interfeysi)"""
    try:
        # Socket yaratish va tarmoqga ulanish (haqiqiy ulanish emas, faqat IP olish uchun)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Internetga ulanishga harakat qilish (haqiqiy ulanish emas)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            return ip
        except Exception:
            # Agar ulanish bo'lmasa, localhost qaytarish
            return "127.0.0.1"
        finally:
            s.close()
    except Exception as e:
        logger.warning(f"Could not get local IP: {e}")
        return "127.0.0.1"

def check_port_windows(port: int) -> bool:
    """Windows da port bandligini tekshirish"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        target_host = API_BIND_HOST if API_BIND_HOST != "0.0.0.0" else PUBLIC_HOST
        result = sock.connect_ex((target_host, port))
        sock.close()
        return result == 0
    except Exception as e:
        logger.debug(f"Could not check port {port}: {e}")
        return False

def run_webapp_server():
    """Run Next.js webapp server in background process (Windows specific)"""
    global running_processes
    try:
        # Webapp papkasini topish
        current_dir = Path(__file__).parent.absolute()
        webapp_dir = current_dir.parent / "webapp"
        
        if not webapp_dir.exists():
            logger.warning(f"Webapp directory not found: {webapp_dir}")
            logger.warning("Webapp will not be started. Please start it manually.")
            return None
        
        # Node.js va npm borligini tekshirish
        try:
            subprocess.run(
                ["node", "--version"], 
                check=True, 
                capture_output=True,
                shell=True
            )
            subprocess.run(
                ["npm", "--version"], 
                check=True, 
                capture_output=True,
                shell=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"Node.js yoki npm topilmadi: {e}")
            logger.warning("Webapp ni qo'lda ishga tushirishingiz kerak.")
            return None
        
        logger.info(f"Starting Next.js webapp from: {webapp_dir}")
        
        # Port 3200 ni ishlatayotgan process'larni to'xtatish
        if check_port_windows(WEBAPP_PORT):
            logger.warning(f"Port {WEBAPP_PORT} is already in use. Attempting to find and kill the process...")
            kill_process_on_port_windows(WEBAPP_PORT)
            time.sleep(2)  # Process to'xtatilishini kutish
            # Qayta tekshirish
            if check_port_windows(WEBAPP_PORT):
                logger.error(f"Port {WEBAPP_PORT} is still in use after cleanup attempt!")
                logger.error(f"Please stop the process manually using:")
                logger.error(f"  netstat -ano | findstr :{WEBAPP_PORT}")
                logger.error(f"  taskkill /PID <pid> /F")
                return None

        backend_url = BACKEND_HTTP_URL
        websocket_url = BACKEND_WS_URL

        env = os.environ.copy()
        env["PORT"] = str(WEBAPP_PORT)
        env["NEXT_PORT"] = str(WEBAPP_PORT)
        env["HOST"] = API_BIND_HOST
        env["BACKEND_URL"] = backend_url
        env["NEXT_PUBLIC_API_BASE"] = "/api"
        env["NEXT_PUBLIC_WS_URL"] = websocket_url  # Fallback, but runtime config takes priority
        env["NEXT_PUBLIC_BACKEND_URL"] = backend_url
        env["NEXT_PUBLIC_API_ORIGIN"] = backend_url
        env["NEXT_PUBLIC_WS_BASE"] = websocket_url
        allowed_origins = {
            PUBLIC_HOST,
            f"{PUBLIC_HOST}:{WEBAPP_PORT}",
            f"http://{PUBLIC_HOST}",
            f"https://{PUBLIC_HOST}",
            f"http://{PUBLIC_HOST}:{WEBAPP_PORT}",
            f"https://{PUBLIC_HOST}:{WEBAPP_PORT}",
            WEBAPP_URL,
            backend_url,
        }
        env["ALLOWED_DEV_ORIGINS"] = ",".join(sorted(filter(None, allowed_origins)))
        
        # Windows da CREATE_NEW_PROCESS_GROUP flag qo'shish
        # Bu "Terminate batch job" xabarini oldini oladi
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
        
        # npm run dev ni ishga tushirish
        # Use 0.0.0.0 to bind to all interfaces (localhost + network)
        # This allows access from localhost and network interfaces
        # Note: Next.js will show "0.0.0.0" in logs, but it's accessible via localhost and network IPs
        webapp_hostname = "0.0.0.0"
        process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--hostname", webapp_hostname],
            cwd=str(webapp_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            shell=True,
            creationflags=creation_flags
        )
        
        running_processes.append(process)
        logger.info(f"Next.js webapp started (PID: {process.pid}) on {WEBAPP_URL} (bind={API_BIND_HOST})")
        
        # Process output ni log qilish
        def log_output():
            try:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        logger.info(f"[Webapp] {line.strip()}")
            except Exception as e:
                logger.error(f"Webapp output logging error: {e}")
        
        output_thread = threading.Thread(target=log_output, daemon=True)
        output_thread.start()
        
        return process
        
    except Exception as e:
        logger.exception(f"Webapp server error: {e}", exc_info=True)
        return None


async def main():
    global ngrok_backend_url, ngrok_frontend_url, BACKEND_HTTP_URL, BACKEND_WS_URL, WEBAPP_URL
    
    # Windows uchun lokal IP ni ko'rsatish
    local_ip = get_local_ip_windows()
    logger.info("=" * 60)
    logger.info("Windows Local Development Setup")
    logger.info("=" * 60)
    logger.info(f"Local IP Address: {local_ip}")
    logger.info(f"API Server: http://{PUBLIC_HOST}:{API_PORT} (bind: {API_BIND_HOST})")
    logger.info(f"WebApp: {WEBAPP_URL}")
    logger.info("")
    logger.info("For network access from other devices:")
    logger.info(f"  - API: http://{local_ip}:{API_PORT}")
    logger.info(f"  - WebApp: http://{local_ip}:{WEBAPP_PORT}")
    logger.info("")
    logger.info("Make sure Windows Firewall allows connections on these ports!")
    logger.info("=" * 60)
    
    # Start FastAPI server in background process
    api_process = run_api_server()
    if not api_process:
        logger.error("Failed to start FastAPI server. Exiting.")
        return
    
    # Start Next.js webapp server in background process (NGROK'dan OLDIN!)
    webapp_process = run_webapp_server()
    if not webapp_process:
        logger.warning("Next.js webapp server not started. Please start it manually if needed.")
    
    # ============================================
    # NGROK TUNNELS SETUP (Backend + Frontend)
    # ============================================
    if NGROK_ENABLED:
        logger.info("")
        logger.info("=" * 60)
        logger.info("🌐 Setting up Ngrok Tunnels (Backend + Frontend)...")
        logger.info("=" * 60)
        
        # Servers tayyor bo'lishi uchun kutish
        logger.info("Waiting for servers to be ready...")
        time.sleep(5)
        
        # Ngrok tunnels ishga tushirish
        backend_url, frontend_url = run_ngrok_tunnels()
        
        if backend_url or frontend_url:
            logger.info("")
            logger.info("=" * 60)
            logger.info("✅ NGROK TUNNELS READY!")
            logger.info("=" * 60)
            
            if backend_url:
                ngrok_backend_url = backend_url
                BACKEND_HTTP_URL = backend_url
                BACKEND_WS_URL = backend_url.replace("https://", "wss://")
                logger.info(f"🔗 Backend API:  {BACKEND_HTTP_URL}")
                logger.info(f"🔗 Backend WS:   {BACKEND_WS_URL}")
            
            if frontend_url:
                ngrok_frontend_url = frontend_url
                WEBAPP_URL = frontend_url
                # Settings'ni ham yangilash (keyboards uchun)
                settings.WEBAPP_URL = frontend_url
                logger.info(f"🔗 Frontend URL: {WEBAPP_URL}")
            
            logger.info("")
            logger.info("📋 Telegram Bot uchun:")
            logger.info(f"   - WebApp URL: {WEBAPP_URL}")
            logger.info(f"   - API URL:    {BACKEND_HTTP_URL}")
            logger.info("")
            logger.info("🌐 Browserda ochish uchun:")
            logger.info(f"   - WebApp: {WEBAPP_URL}")
            logger.info(f"   - API Docs: {BACKEND_HTTP_URL}/docs")
            logger.info("=" * 60)
            logger.info("")
        else:
            logger.warning("⚠️ Ngrok tunnels could not be created. Using local URLs.")
    else:
        logger.info("ℹ️ Ngrok is disabled. Using local URLs only.")
    
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
            break
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
    """Handle signals (CTRL+C) gracefully - Windows specific"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    cleanup_processes()
    # Port'larni ham tozalash
    try:
        kill_process_on_port_windows(API_PORT)
        kill_process_on_port_windows(WEBAPP_PORT)
    except Exception:
        pass
    sys.exit(0)

if __name__ == "__main__":
    # Windows da signal handlers
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    except (ValueError, OSError) as e:
        # Windows'da ba'zi signal'lar ishlamaydi
        logger.debug(f"Could not register signal handler: {e}")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
        cleanup_processes()
        # Port'larni ham tozalash
        try:
            kill_process_on_port_windows(API_PORT)
            kill_process_on_port_windows(WEBAPP_PORT)
        except Exception:
            pass
        sys.exit(0)
    except Exception as e:
        logger.exception("Main error", exc_info=True)
        cleanup_processes()
        # Port'larni ham tozalash
        try:
            kill_process_on_port_windows(API_PORT)
            kill_process_on_port_windows(WEBAPP_PORT)
        except Exception:
            pass
        sys.exit(1)

