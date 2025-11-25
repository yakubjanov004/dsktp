"""
Universal Error Logger - Centralized logging system

Bu modul barcha xatolarni markazlashtirilgan tarzda log qiladi.
"""

import logging
import traceback
from typing import Optional, Dict, Any
from datetime import datetime
import json
import os
from logging.handlers import RotatingFileHandler

log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Bot log uchun alohida logger
bot_logger = logging.getLogger("BotLogger")
bot_handler = RotatingFileHandler(
    os.path.join(log_dir, "bot.log"), 
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding="utf-8"
)
bot_handler.setLevel(logging.INFO)
bot_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
bot_handler.setFormatter(bot_formatter)
bot_logger.addHandler(bot_handler)
bot_logger.setLevel(logging.INFO)

# Console uchun alohida handler (faqat INFO va yuqori)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
console_handler.setFormatter(console_formatter)
bot_logger.addHandler(console_handler)

# Error logger alohida - faqat ERROR va CRITICAL
error_logger = logging.getLogger("ErrorLogger")
error_logger.setLevel(logging.ERROR)

# Error fayl handler
error_file_handler = RotatingFileHandler(
    os.path.join(log_dir, "errors.log"), 
    maxBytes=5*1024*1024,  # 5MB
    backupCount=3,
    encoding="utf-8"
)
error_file_handler.setLevel(logging.ERROR)
error_file_formatter = logging.Formatter(
    "%(asctime)s | ERROR | %(message)s"
)
error_file_handler.setFormatter(error_file_formatter)
error_logger.addHandler(error_file_handler)

# Console uchun error handler (terminalga chiqadigan errorlar)
error_console_handler = logging.StreamHandler()
error_console_handler.setLevel(logging.ERROR)
error_console_formatter = logging.Formatter(
    "%(asctime)s | ERROR | %(message)s"
)
error_console_handler.setFormatter(error_console_formatter)
error_logger.addHandler(error_console_handler)

def get_universal_logger(name: str = "AlfaConnectBot") -> logging.Logger:
    """Universal logger olish - bot.log ga yozadi"""
    logger = logging.getLogger(name)
    
    # Agar handler yo'q bo'lsa, qo'shish
    if not logger.handlers:
        logger.addHandler(bot_handler)
        logger.addHandler(console_handler)
        logger.setLevel(logging.INFO)
    
    return logger

def get_error_logger(name: str = "ErrorLogger") -> logging.Logger:
    """Error logger olish - errors.log ga yozadi"""
    logger = logging.getLogger(name)
    
    # Agar handler yo'q bo'lsa, qo'shish
    if not logger.handlers:
        logger.addHandler(error_file_handler)
        logger.addHandler(error_console_handler)
        logger.setLevel(logging.ERROR)
    
    return logger

def log_error(
    error: Exception,
    context: str = "",
    user_id: Optional[int] = None,
    additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """Xatolarni log qilish - faqat errors.log ga"""
    
    error_data = {
        "timestamp": datetime.now().isoformat(),
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context,
        "user_id": user_id,
        "traceback": traceback.format_exc()
    }
    
    if additional_data:
        error_data.update(additional_data)
    
    # Faqat error loggerga yozish (errors.log va terminalga)
    error_logger.error(json.dumps(error_data, ensure_ascii=False, indent=2))

def log_info(message: str, context: str = "", user_id: Optional[int] = None) -> None:
    """Info log qilish - faqat bot.log ga"""
    logger = get_universal_logger()
    logger.info(f"INFO: {context} | {message} | User: {user_id}")

def log_warning(message: str, context: str = "", user_id: Optional[int] = None) -> None:
    """Warning log qilish - faqat bot.log ga"""
    logger = get_universal_logger()
    logger.warning(f"WARNING: {context} | {message} | User: {user_id}")

def log_debug(message: str, context: str = "", user_id: Optional[int] = None) -> None:
    """Debug log qilish - faqat bot.log ga"""
    logger = get_universal_logger()
    logger.debug(f"DEBUG: {context} | {message} | User: {user_id}")

def get_recent_errors(limit: int = 50) -> list:
    """So'nggi xatoliklarni olish"""
    error_file = os.path.join(log_dir, "errors.log")
    errors = []
    
    if os.path.exists(error_file):
        try:
            with open(error_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # So'nggi qatorlarni olish
                recent_lines = lines[-limit*3:]  # Har bir error bir necha qator bo'lishi mumkin
                
                current_error = ""
                for line in recent_lines:
                    if line.strip().startswith('{'):
                        if current_error:
                            try:
                                error_data = json.loads(current_error)
                                errors.append(error_data)
                            except:
                                pass
                        current_error = line.strip()
                    elif current_error and (line.startswith('  ') or line.startswith('\t')):
                        current_error += line
                
                # So'nggi errorni ham qo'shish
                if current_error:
                    try:
                        error_data = json.loads(current_error)
                        errors.append(error_data)
                    except:
                        pass
                        
        except Exception as e:
            log_error(e, "Error reading error log file")
    
    return errors[-limit:] if len(errors) > limit else errors

def search_errors_by_type(error_type: str, limit: int = 20) -> list:
    """Xatolik turi bo'yicha qidirish"""
    all_errors = get_recent_errors(200)  # Ko'proq error olish
    filtered_errors = []
    
    for error in all_errors:
        if error.get('error_type', '').lower() == error_type.lower():
            filtered_errors.append(error)
            if len(filtered_errors) >= limit:
                break
    
    return filtered_errors

def get_error_statistics() -> Dict[str, Any]:
    """Xatoliklar statistikasi"""
    errors = get_recent_errors(100)
    stats = {
        'total_errors': len(errors),
        'error_types': {},
        'users_with_errors': set(),
        'contexts': {}
    }
    
    for error in errors:
        # Error type statistikasi
        error_type = error.get('error_type', 'Unknown')
        stats['error_types'][error_type] = stats['error_types'].get(error_type, 0) + 1
        
        # User statistikasi
        user_id = error.get('user_id')
        if user_id:
            stats['users_with_errors'].add(user_id)
        
        # Context statistikasi
        context = error.get('context', 'Unknown')
        stats['contexts'][context] = stats['contexts'].get(context, 0) + 1
    
    stats['users_with_errors'] = len(stats['users_with_errors'])
    return stats

def clear_old_logs(days: int = 7) -> None:
    """Eski loglarni tozalash"""
    import time
    
    current_time = time.time()
    cutoff_time = current_time - (days * 24 * 60 * 60)
    
    for filename in os.listdir(log_dir):
        if filename.endswith('.log'):
            filepath = os.path.join(log_dir, filename)
            if os.path.getctime(filepath) < cutoff_time:
                try:
                    os.remove(filepath)
                    log_info(f"Old log file removed: {filename}", "Log Cleanup")
                except Exception as e:
                    log_error(e, f"Error removing old log file: {filename}")
