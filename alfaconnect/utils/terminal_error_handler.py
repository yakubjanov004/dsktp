"""
Terminal Error Handler - Terminalga chiqadigan errorlarni errors.log ga yo'naltiradi
"""

import sys
import logging
from utils.universal_error_logger import get_error_logger

class TerminalErrorHandler:
    """Terminal errorlarini errors.log ga yo'naltiradigan handler"""
    
    def __init__(self):
        self.error_logger = get_error_logger("TerminalErrorHandler")
        self.original_stderr = sys.stderr
        
    def write(self, message):
        """stderr ga yoziladigan xabarlarni errors.log ga yo'naltiradi"""
        if message.strip():  # Bo'sh xabarlarni e'tiborsiz qoldirish
            # Terminalga ham chiqarish
            self.original_stderr.write(message)
            self.original_stderr.flush()
            
            # errors.log ga ham yozish
            self.error_logger.error(f"Terminal Error: {message.strip()}")
    
    def flush(self):
        """Flush operatsiyasi"""
        self.original_stderr.flush()

def setup_terminal_error_handler():
    """Terminal error handler'ni sozlash"""
    error_handler = TerminalErrorHandler()
    sys.stderr = error_handler
    return error_handler

def restore_terminal_error_handler():
    """Asl terminal error handler'ni qaytarish"""
    sys.stderr = sys.__stderr__
