from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import settings

def get_call_center_main_keyboard(lang: str = 'uz', telegram_id: int = None) -> ReplyKeyboardMarkup:
    # Config'dan WEBAPP_URL ni olish
    webapp_url = settings.WEBAPP_URL
    
    # Telegram ID ni URL'ga qo'shish (fallback uchun)
    if telegram_id and webapp_url.startswith("https://"):
        separator = "&" if "?" in webapp_url else "?"
        webapp_url_with_id = f"{webapp_url}{separator}telegram_id={telegram_id}"
    else:
        webapp_url_with_id = webapp_url
    
    if lang == 'ru':
        webapp_text = "💬 Онлайн Чат Web App"
        keyboard = [
            [KeyboardButton(text="📥 Входящие"), KeyboardButton(text="🔍 Поиск клиента")],
            [KeyboardButton(text="🔌 Создать заявку на подключение"), KeyboardButton(text="🔧 Создать техническую заявку")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🌐 Изменить язык")],
        ]
        # Telegram WebApp faqat HTTPS URL larni qabul qiladi
        if webapp_url.startswith("https://"):
            keyboard.append([KeyboardButton(text=webapp_text, web_app=WebAppInfo(url=webapp_url_with_id))])
    else:
        webapp_text = "💬 Onlayn Chat Web App"
        keyboard = [
            [KeyboardButton(text="📥 Inbox"), KeyboardButton(text="🔍 Mijoz qidirish")],
            [KeyboardButton(text="🔌 Ulanish arizasi yaratish"), KeyboardButton(text="🔧 Texnik xizmat yaratish")],
            [KeyboardButton(text="📊 Statistikalar"), KeyboardButton(text="🌐 Tilni o'zgartirish")],
        ]
        # Telegram WebApp faqat HTTPS URL larni qabul qiladi
        if webapp_url.startswith("https://"):
            keyboard.append([KeyboardButton(text=webapp_text, web_app=WebAppInfo(url=webapp_url_with_id))])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def zayavka_type_keyboard(lang="uz"):
    """Zayavka turini tanlash klaviaturasi - 2 tilda"""
    person_physical_text = "👤 Jismoniy shaxs" if lang == "uz" else "👤 Физическое лицо"
    person_legal_text = "🏢 Yuridik shaxs" if lang == "uz" else "🏢 Юридическое лицо"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=person_physical_text, callback_data="zayavka_type_b2c")],
            [InlineKeyboardButton(text=person_legal_text, callback_data="zayavka_type_b2b")]
        ]
    )
    return keyboard

def get_operator_tariff_selection_keyboard() -> InlineKeyboardMarkup:
    """Tariff selection keyboard for CALL-CENTER OPERATOR (UZ only)."""
    keyboard = [
        [
            InlineKeyboardButton(text="Oddiy-20", callback_data="op_tariff_b2c_plan_0"),
            InlineKeyboardButton(text="Oddiy-50", callback_data="op_tariff_b2c_plan_1"),
        ],
        [
            InlineKeyboardButton(text="Oddiy-100", callback_data="op_tariff_b2c_plan_2"),
            InlineKeyboardButton(text="XIT-200", callback_data="op_tariff_b2c_plan_3"),
        ],
        [
            InlineKeyboardButton(text="VIP-500", callback_data="op_tariff_b2c_plan_4"),
            InlineKeyboardButton(text="PREMIUM", callback_data="op_tariff_b2c_plan_5"),
        ],
        [
            InlineKeyboardButton(text="BizNET-Pro-1", callback_data="op_tariff_biznet_plan_0"),
            InlineKeyboardButton(text="BizNET-Pro-2", callback_data="op_tariff_biznet_plan_1"),
        ],
        [
            InlineKeyboardButton(text="BizNET-Pro-3", callback_data="op_tariff_biznet_plan_2"),
            InlineKeyboardButton(text="BizNET-Pro-4", callback_data="op_tariff_biznet_plan_3"),
        ],
        [
            InlineKeyboardButton(text="BizNET-Pro-5", callback_data="op_tariff_biznet_plan_4"),
            InlineKeyboardButton(text="BizNET-Pro-6", callback_data="op_tariff_biznet_plan_5"),
        ],
        [
            InlineKeyboardButton(text="BizNET-Pro-7+", callback_data="op_tariff_biznet_plan_6"),
            InlineKeyboardButton(text="Tijorat-1", callback_data="op_tariff_tijorat_plan_0"),
        ],
        [
            InlineKeyboardButton(text="Tijorat-2", callback_data="op_tariff_tijorat_plan_1"),
            InlineKeyboardButton(text="Tijorat-3", callback_data="op_tariff_tijorat_plan_2"),
        ],
        [
            InlineKeyboardButton(text="Tijorat-4", callback_data="op_tariff_tijorat_plan_3"),
            InlineKeyboardButton(text="Tijorat-5", callback_data="op_tariff_tijorat_plan_4"),
        ],
        [
            InlineKeyboardButton(text="Tijorat-100", callback_data="op_tariff_tijorat_plan_5"),
            InlineKeyboardButton(text="Tijorat-300", callback_data="op_tariff_tijorat_plan_6"),
        ],
        [
            InlineKeyboardButton(text="Tijorat-500", callback_data="op_tariff_tijorat_plan_7"),
            InlineKeyboardButton(text="Tijorat-1000", callback_data="op_tariff_tijorat_plan_8"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def confirmation_keyboard(lang="uz"):
    """Tasdiqlash klaviaturasi - 2 tilda"""
    confirm_text = "✅ Tasdiqlash" if lang == "uz" else "✅ Подтвердить"
    resend_text = "🔄 Qayta yuborish" if lang == "uz" else "🔄 Отправить заново"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=confirm_text, callback_data="confirm_zayavka_call_center"),
            InlineKeyboardButton(text=resend_text, callback_data="resend_zayavka_call_center")
        ]
    ])
    return keyboard

def confirmation_keyboard_tech_service(lang="uz"):
    """Tasdiqlash klaviaturasi - 2 tilda"""
    confirm_text = "✅ Tasdiqlash" if lang == "uz" else "✅ Подтвердить"
    resend_text = "🔄 Qayta yuborish" if lang == "uz" else "🔄 Отправить заново"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=confirm_text, callback_data="confirm_zayavka_call_center_tech_service"),
            InlineKeyboardButton(text=resend_text, callback_data="resend_zayavka_call_center_tech_service")
        ]
    ])
    return keyboard

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_client_regions_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    """Regions selection keyboard for client (Uz/Ru)"""

    if lang == "ru":
        keyboard = [
            [
                InlineKeyboardButton(text="г. Ташкент", callback_data="region_toshkent_city"),
                InlineKeyboardButton(text="Ташкентская область", callback_data="region_toshkent_region"),
            ],
            [
                InlineKeyboardButton(text="Андижан", callback_data="region_andijon"),
                InlineKeyboardButton(text="Фергана", callback_data="region_fergana"),
            ],
            [
                InlineKeyboardButton(text="Наманган", callback_data="region_namangan"),
                InlineKeyboardButton(text="Сырдарья", callback_data="region_sirdaryo"),
            ],
            [
                InlineKeyboardButton(text="Джизак", callback_data="region_jizzax"),
                InlineKeyboardButton(text="Самарканд", callback_data="region_samarkand"),
            ],
            [
                InlineKeyboardButton(text="Бухара", callback_data="region_bukhara"),
                InlineKeyboardButton(text="Навои", callback_data="region_navoi"),
            ],
            [
                InlineKeyboardButton(text="Кашкадарья", callback_data="region_kashkadarya"),
                InlineKeyboardButton(text="Сурхандарья", callback_data="region_surkhandarya"),
            ],
            [
                InlineKeyboardButton(text="Хорезм", callback_data="region_khorezm"),
                InlineKeyboardButton(text="Каракалпакстан", callback_data="region_karakalpakstan"),
            ],
        ]
    else:  # default uz
        keyboard = [
            [
                InlineKeyboardButton(text="Toshkent shahri", callback_data="region_toshkent_city"),
                InlineKeyboardButton(text="Toshkent viloyati", callback_data="region_toshkent_region"),
            ],
            [
                InlineKeyboardButton(text="Andijon", callback_data="region_andijon"),
                InlineKeyboardButton(text="Farg'ona", callback_data="region_fergana"),
            ],
            [
                InlineKeyboardButton(text="Namangan", callback_data="region_namangan"),
                InlineKeyboardButton(text="Sirdaryo", callback_data="region_sirdaryo"),
            ],
            [
                InlineKeyboardButton(text="Jizzax", callback_data="region_jizzax"),
                InlineKeyboardButton(text="Samarqand", callback_data="region_samarkand"),
            ],
            [
                InlineKeyboardButton(text="Buxoro", callback_data="region_bukhara"),
                InlineKeyboardButton(text="Navoiy", callback_data="region_navoi"),
            ],
            [
                InlineKeyboardButton(text="Qashqadaryo", callback_data="region_kashkadarya"),
                InlineKeyboardButton(text="Surxondaryo", callback_data="region_surkhandarya"),
            ],
            [
                InlineKeyboardButton(text="Xorazm", callback_data="region_khorezm"),
                InlineKeyboardButton(text="Qoraqalpog'iston", callback_data="region_karakalpakstan"),
            ],
        ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
