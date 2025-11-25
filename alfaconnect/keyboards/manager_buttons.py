from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict


def get_manager_main_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    if lang == "uz":
        keyboard = [
            [KeyboardButton(text="📥 Inbox"), KeyboardButton(text="📋 Arizalarni ko'rish")],
            [KeyboardButton(text="🔌 Ulanish arizasi yaratish"), KeyboardButton(text="🔧 Texnik xizmat yaratish")],
            [KeyboardButton(text="🛜 SmartService arizalari"), KeyboardButton(text="📤 Export")],
            [KeyboardButton(text="🕐 Real vaqtda kuzatish"), KeyboardButton(text="👥 Xodimlar faoliyati")],
            [KeyboardButton(text="🌐 Tilni o'zgartirish")],
        ]
    else:  # ruscha
        keyboard = [
            [KeyboardButton(text="📥 Входящие"), KeyboardButton(text="📋 Все заявки")],
            [KeyboardButton(text="🔌 Создать заявку на подключение"), KeyboardButton(text="🔧 Создать заявку на тех. обслуживание")],
            [KeyboardButton(text="🛜 SmartService заявки"), KeyboardButton(text="📤 Экспорт")],
            [KeyboardButton(text="🕐 Мониторинг в реальном времени"), KeyboardButton(text="👥 Активность сотрудников")],
            [KeyboardButton(text="🌐 Изменить язык")],
        ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_manager_status_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Manager status selection keyboard"""
    if lang == "uz":
        keyboard = [
            [InlineKeyboardButton(text="🔄 Yangi", callback_data="manager_status_new")],
            [InlineKeyboardButton(text="⏳ Jarayonda", callback_data="manager_status_in_progress")],
            [InlineKeyboardButton(text="✅ Bajarildi", callback_data="manager_status_completed")],
            [InlineKeyboardButton(text="❌ Bekor qilindi", callback_data="manager_status_cancelled")],
            [InlineKeyboardButton(text="🚫 Yopish", callback_data="manager_status_end")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="🔄 Новый", callback_data="manager_status_new")],
            [InlineKeyboardButton(text="⏳ В процессе", callback_data="manager_status_in_progress")],
            [InlineKeyboardButton(text="✅ Выполнено", callback_data="manager_status_completed")],
            [InlineKeyboardButton(text="❌ Отменено", callback_data="manager_status_cancelled")],
            [InlineKeyboardButton(text="🚫 Выход", callback_data="manager_status_end")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

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

def get_manager_export_types_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    """Manager export types selection keyboard"""
    if lang == "uz":
        keyboard = [
            [InlineKeyboardButton(text="📋 Arizalar", callback_data="manager_export_orders")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="manager_export_statistics")],
            [InlineKeyboardButton(text="👥 Xodimlar", callback_data="manager_export_employees")],
            [InlineKeyboardButton(text="🚫 Yopish", callback_data="manager_export_end")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="📋 Заказы", callback_data="manager_export_orders")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="manager_export_statistics")],
            [InlineKeyboardButton(text="👥 Сотрудники", callback_data="manager_export_employees")],
            [InlineKeyboardButton(text="🚫 Выход", callback_data="manager_export_end")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_manager_time_period_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    """Time period selection keyboard for manager exports"""
    if lang == "uz":
        keyboard = [
            [InlineKeyboardButton(text="📅 Bugun", callback_data="manager_time_today")],
            [InlineKeyboardButton(text="📅 Hafta", callback_data="manager_time_week")],
            [InlineKeyboardButton(text="📅 Oy", callback_data="manager_time_month")],
            [InlineKeyboardButton(text="📅 Jami", callback_data="manager_time_total")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="manager_export_back_types")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="📅 Сегодня", callback_data="manager_time_today")],
            [InlineKeyboardButton(text="📅 Неделя", callback_data="manager_time_week")],
            [InlineKeyboardButton(text="📅 Месяц", callback_data="manager_time_month")],
            [InlineKeyboardButton(text="📅 Всего", callback_data="manager_time_total")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="manager_export_back_types")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_manager_export_formats_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    """Manager export formats selection keyboard"""
    if lang == "uz":
        keyboard = [
            [InlineKeyboardButton(text="CSV", callback_data="manager_format_csv")],
            [InlineKeyboardButton(text="Excel", callback_data="manager_format_xlsx")],
            [InlineKeyboardButton(text="Word", callback_data="manager_format_docx")],
            [InlineKeyboardButton(text="PDF", callback_data="manager_format_pdf")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="manager_export_back_types")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="CSV", callback_data="manager_format_csv")],
            [InlineKeyboardButton(text="Excel", callback_data="manager_format_xlsx")],
            [InlineKeyboardButton(text="Word", callback_data="manager_format_docx")],
            [InlineKeyboardButton(text="PDF", callback_data="manager_format_pdf")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="manager_export_back_types")]
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

def get_client_regions_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    is_ru = (lang or '').strip().lower().startswith('ru')

    if is_ru:
        keyboard = [
            [InlineKeyboardButton(text="г. Ташкент",           callback_data="region_toshkent_city"),
             InlineKeyboardButton(text="Ташкентская область",  callback_data="region_toshkent_region")],
            [InlineKeyboardButton(text="Андижан",              callback_data="region_andijon"),
             InlineKeyboardButton(text="Фергана",              callback_data="region_fergana")],
            [InlineKeyboardButton(text="Наманган",             callback_data="region_namangan"),
             InlineKeyboardButton(text="Сырдарья",             callback_data="region_sirdaryo")],
            [InlineKeyboardButton(text="Джизак",               callback_data="region_jizzax"),
             InlineKeyboardButton(text="Самарканд",            callback_data="region_samarkand")],
            [InlineKeyboardButton(text="Бухара",               callback_data="region_bukhara"),
             InlineKeyboardButton(text="Навои",                callback_data="region_navoi")],
            [InlineKeyboardButton(text="Кашкадарья",           callback_data="region_kashkadarya"),
             InlineKeyboardButton(text="Сурхандарья",          callback_data="region_surkhandarya")],
            [InlineKeyboardButton(text="Хорезм",               callback_data="region_khorezm"),
             InlineKeyboardButton(text="Каракалпакстан",       callback_data="region_karakalpakstan")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="Toshkent shahri",      callback_data="region_toshkent_city"),
             InlineKeyboardButton(text="Toshkent viloyati",    callback_data="region_toshkent_region")],
            [InlineKeyboardButton(text="Andijon",              callback_data="region_andijon"),
             InlineKeyboardButton(text="Farg'ona",             callback_data="region_fergana")],
            [InlineKeyboardButton(text="Namangan",             callback_data="region_namangan"),
             InlineKeyboardButton(text="Sirdaryo",             callback_data="region_sirdaryo")],
            [InlineKeyboardButton(text="Jizzax",               callback_data="region_jizzax"),
             InlineKeyboardButton(text="Samarqand",            callback_data="region_samarkand")],
            [InlineKeyboardButton(text="Buxoro",               callback_data="region_bukhara"),
             InlineKeyboardButton(text="Navoiy",               callback_data="region_navoi")],
            [InlineKeyboardButton(text="Qashqadaryo",          callback_data="region_kashkadarya"),
             InlineKeyboardButton(text="Surxondaryo",          callback_data="region_surkhandarya")],
            [InlineKeyboardButton(text="Xorazm",               callback_data="region_khorezm"),
             InlineKeyboardButton(text="Qoraqalpog'iston",     callback_data="region_karakalpakstan")],
        ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)