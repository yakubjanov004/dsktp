from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_junior_manager_main_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Kichik menejer uchun bosh menyu — 6 ta tugma."""
    inbox_text = "📥 Inbox"
    view_apps_text = "📋 Arizalarni ko'rish" if lang == "uz" else "📋 Просмотр заявок"
    create_connection_text = "🔌 Ulanish arizasi yaratish" if lang == "uz" else "🔌 Создать заявку"
    client_search_text = "🔍 Mijoz qidiruv" if lang == "uz" else "🔍 Поиск клиентов"
    statistics_text = "📊 Statistika" if lang == "uz" else "📊 Статистика"
    change_lang_text = "🌐 Tilni o'zgartirish" if lang == "uz" else "🌐 Изменить язык"

    keyboard = [
        [KeyboardButton(text=inbox_text), KeyboardButton(text=view_apps_text)],
        [KeyboardButton(text=create_connection_text), KeyboardButton(text=client_search_text)],
        [KeyboardButton(text=statistics_text), KeyboardButton(text=change_lang_text)],
    ]
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

def get_client_regions_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    """Regions selection keyboard for client"""
    if lang == "ru":
        keyboard = [
            [
                InlineKeyboardButton(text="г. Ташкент", callback_data="region_toshkent_city"),
                InlineKeyboardButton(text="Ташкентская область", callback_data="region_toshkent_region")
            ],
            [
                InlineKeyboardButton(text="Андижан", callback_data="region_andijon"),
                InlineKeyboardButton(text="Фергана", callback_data="region_fergana")
            ],
            [
                InlineKeyboardButton(text="Наманган", callback_data="region_namangan"),
                InlineKeyboardButton(text="Сырдарья", callback_data="region_sirdaryo")
            ],
            [
                InlineKeyboardButton(text="Джизак", callback_data="region_jizzax"),
                InlineKeyboardButton(text="Самарканд", callback_data="region_samarkand")
            ],
            [
                InlineKeyboardButton(text="Бухара", callback_data="region_bukhara"),
                InlineKeyboardButton(text="Навои", callback_data="region_navoi")
            ],
            [
                InlineKeyboardButton(text="Кашкадарья", callback_data="region_kashkadarya"),
                InlineKeyboardButton(text="Сурхандарья", callback_data="region_surkhandarya")
            ],
            [
                InlineKeyboardButton(text="Хорезм", callback_data="region_khorezm"),
                InlineKeyboardButton(text="Каракалпакстан", callback_data="region_karakalpakstan")
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(text="Toshkent shahri", callback_data="region_toshkent_city"),
                InlineKeyboardButton(text="Toshkent viloyati", callback_data="region_toshkent_region")
            ],
            [
                InlineKeyboardButton(text="Andijon", callback_data="region_andijon"),
                InlineKeyboardButton(text="Farg'ona", callback_data="region_fergana")
            ],
            [
                InlineKeyboardButton(text="Namangan", callback_data="region_namangan"),
                InlineKeyboardButton(text="Sirdaryo", callback_data="region_sirdaryo")
            ],
            [
                InlineKeyboardButton(text="Jizzax", callback_data="region_jizzax"),
                InlineKeyboardButton(text="Samarqand", callback_data="region_samarkand")
            ],
            [
                InlineKeyboardButton(text="Buxoro", callback_data="region_bukhara"),
                InlineKeyboardButton(text="Navoiy", callback_data="region_navoi")
            ],
            [
                InlineKeyboardButton(text="Qashqadaryo", callback_data="region_kashkadarya"),
                InlineKeyboardButton(text="Surxondaryo", callback_data="region_surkhandarya")
            ],
            [
                InlineKeyboardButton(text="Xorazm", callback_data="region_khorezm"),
                InlineKeyboardButton(text="Qoraqalpog'iston", callback_data="region_karakalpakstan")
            ]
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)