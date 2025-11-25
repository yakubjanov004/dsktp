from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# =========================
# Reply: Controller main menu
# =========================
def get_controller_main_menu(lang: str = 'uz') -> ReplyKeyboardMarkup:
    if (lang or 'uz').lower().startswith('ru'):
        keyboard = [
            [KeyboardButton(text="📥 Входящие"), KeyboardButton(text="📋 Просмотр заявок")],
            [KeyboardButton(text="🔌 Создать заявку на подключение"), KeyboardButton(text="🔧 Создать техническую заявку")],
            [KeyboardButton(text="👥 Активность сотрудников"), KeyboardButton(text="📤 Экспорт")],
            [KeyboardButton(text="🌐 Изменить язык")]
        ]
    else:
        keyboard = [
            [KeyboardButton(text="📥 Inbox"), KeyboardButton(text="📋 Arizalarni ko'rish")],
            [KeyboardButton(text="🔌 Ulanish arizasi yaratish"), KeyboardButton(text="🔧 Texnik xizmat yaratish")],
            [KeyboardButton(text="👥 Xodimlar faoliyati"), KeyboardButton(text="📤 Export")],
            [KeyboardButton(text="🌐 Tilni o'zgartirish")]
        ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# =========================
# Inline: Export (qolganlari o‘zgarmagan)
# =========================
def get_controller_export_types_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    lang = (lang or 'uz').lower()
    if lang.startswith("ru"):
        keyboard = [
            [InlineKeyboardButton(text="📋 Техн. заявки", callback_data="controller_export_tech_requests")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="controller_export_statistics")],
            [InlineKeyboardButton(text="👥 Сотрудники", callback_data="controller_export_employees")],
            [InlineKeyboardButton(text="🚫 Выход", callback_data="controller_export_end")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="📋 Texnik arizalar", callback_data="controller_export_tech_requests")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="controller_export_statistics")],
            [InlineKeyboardButton(text="👥 Xodimlar", callback_data="controller_export_employees")],
            [InlineKeyboardButton(text="🚫 Yopish", callback_data="controller_export_end")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_controller_time_period_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    """Time period selection keyboard for exports"""
    if (lang or 'uz').lower().startswith('ru'):
        keyboard = [
            [InlineKeyboardButton(text="📅 Сегодня", callback_data="controller_time_today")],
            [InlineKeyboardButton(text="📅 Неделя", callback_data="controller_time_week")],
            [InlineKeyboardButton(text="📅 Месяц", callback_data="controller_time_month")],
            [InlineKeyboardButton(text="📅 Всего", callback_data="controller_time_total")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="controller_export_back_types")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="📅 Bugun", callback_data="controller_time_today")],
            [InlineKeyboardButton(text="📅 Hafta", callback_data="controller_time_week")],
            [InlineKeyboardButton(text="📅 Oy", callback_data="controller_time_month")],
            [InlineKeyboardButton(text="📅 Jami", callback_data="controller_time_total")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="controller_export_back_types")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_controller_export_formats_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    if (lang or 'uz').lower().startswith('ru'):
        keyboard = [
            [InlineKeyboardButton(text="CSV",   callback_data="controller_format_csv")],
            [InlineKeyboardButton(text="Excel", callback_data="controller_format_xlsx")],
            [InlineKeyboardButton(text="Word",  callback_data="controller_format_docx")],
            [InlineKeyboardButton(text="PDF",   callback_data="controller_format_pdf")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="controller_export_back_types")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="CSV",   callback_data="controller_format_csv")],
            [InlineKeyboardButton(text="Excel", callback_data="controller_format_xlsx")],
            [InlineKeyboardButton(text="Word",  callback_data="controller_format_docx")],
            [InlineKeyboardButton(text="PDF",   callback_data="controller_format_pdf")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="controller_export_back_types")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# =========================
# Inline: Region tanlash (controller uchun)
# callback_data: "region_<code>"
# =========================
def get_controller_regions_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    # Nomlar asosan UZ bo‘lishi ham mayli; handlerga muhim bo‘lgani – callback_data
    rows = [
        [("Toshkent shahri", "г. Ташкент", "toshkent_city"),
         ("Toshkent viloyati", "Ташкентская область", "toshkent_region")],
        [("Andijon", "Андижан", "andijon"),
         ("Farg‘ona", "Фергана", "fergana")],
        [("Namangan", "Наманган", "namangan"),
         ("Sirdaryo", "Сырдарья", "sirdaryo")],
        [("Jizzax", "Джизак", "jizzax"),
         ("Samarqand", "Самарканд", "samarkand")],
        [("Buxoro", "Бухара", "bukhara"),
         ("Navoiy", "Навои", "navoi")],
        [("Qashqadaryo", "Кашкадарья", "kashkadarya"),
         ("Surxondaryo", "Сурхандарья", "surkhandarya")],
        [("Xorazm", "Хорезм", "khorezm"),
         ("Qoraqalpog‘iston", "Каракалпакстан", "karakalpakstan")],
    ]
    is_ru = (lang or 'uz').lower().startswith('ru')
    kb_rows = []
    for a_uz, a_ru, a_code in sum(rows, []):  # flatten pairs
        pass
    kb_rows = []
    for pair in rows:
        btns = []
        for uz_name, ru_name, code in pair:
            btns.append(InlineKeyboardButton(
                text=ru_name if is_ru else uz_name,
                callback_data=f"region_{code}"
            ))
        kb_rows.append(btns)
    return InlineKeyboardMarkup(inline_keyboard=kb_rows)

# =========================
# Inline: Ulanish turi (b2c/b2b)
# callback_data: "zayavka_type_b2c|b2b"
# =========================
def controller_zayavka_type_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    is_ru = (lang or 'uz').lower().startswith('ru')
    b2c = "Физ. лицо" if is_ru else "Jismoniy shaxs"
    b2b = "Юр. лицо"  if is_ru else "Yuridik shaxs"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=b2c, callback_data="zayavka_type_b2c"),
         InlineKeyboardButton(text=b2b, callback_data="zayavka_type_b2b")]
    ])

# =========================
# Inline: Tarif tanlash (OP callbacklari bilan)
# callback_data: "op_tariff_*"
# =========================
def get_controller_tariff_selection_keyboard() -> InlineKeyboardMarkup:
    # Hozircha UZ label'lar – callback_data muhim
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Oddiy-20",   callback_data="op_tariff_b2c_plan_0"),
         InlineKeyboardButton(text="Oddiy-50",  callback_data="op_tariff_b2c_plan_1")],
        [InlineKeyboardButton(text="Oddiy-100",   callback_data="op_tariff_b2c_plan_2"),
         InlineKeyboardButton(text="XIT-200",   callback_data="op_tariff_b2c_plan_3")],
        [InlineKeyboardButton(text="VIP-500",   callback_data="op_tariff_b2c_plan_4"),
         InlineKeyboardButton(text="PREMIUM",   callback_data="op_tariff_b2c_plan_5")],
        [InlineKeyboardButton(text="BizNET-Pro-1",   callback_data="op_tariff_biznet_plan_0"),
         InlineKeyboardButton(text="BizNET-Pro-2",  callback_data="op_tariff_biznet_plan_1")],
        [InlineKeyboardButton(text="BizNET-Pro-3",   callback_data="op_tariff_biznet_plan_2"),
         InlineKeyboardButton(text="BizNET-Pro-4",   callback_data="op_tariff_biznet_plan_3")],
        [InlineKeyboardButton(text="BizNET-Pro-5",   callback_data="op_tariff_biznet_plan_4"),
         InlineKeyboardButton(text="BizNET-Pro-6",   callback_data="op_tariff_biznet_plan_5")],
        [InlineKeyboardButton(text="BizNET-Pro-7+",   callback_data="op_tariff_biznet_plan_6"),
         InlineKeyboardButton(text="Tijorat-1",   callback_data="op_tariff_tijorat_plan_0")],
        [InlineKeyboardButton(text="Tijorat-2",   callback_data="op_tariff_tijorat_plan_1"),
         InlineKeyboardButton(text="Tijorat-3",  callback_data="op_tariff_tijorat_plan_2")],
        [InlineKeyboardButton(text="Tijorat-4",   callback_data="op_tariff_tijorat_plan_3"),
         InlineKeyboardButton(text="Tijorat-5",   callback_data="op_tariff_tijorat_plan_4")],
        [InlineKeyboardButton(text="Tijorat-100",   callback_data="op_tariff_tijorat_plan_5"),
         InlineKeyboardButton(text="Tijorat-300",   callback_data="op_tariff_tijorat_plan_6")],
        [InlineKeyboardButton(text="Tijorat-500",   callback_data="op_tariff_tijorat_plan_7"),
         InlineKeyboardButton(text="Tijorat-1000",   callback_data="op_tariff_tijorat_plan_8")],
    ])

# =========================
# Inline: Tasdiqlash (ULANISH)
# callback_data: confirm_zayavka_call_center / resend_zayavka_call_center
# =========================
def controller_confirmation_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    is_ru = (lang or 'uz').lower().startswith('ru')
    ok = "✅ Подтвердить" if is_ru else "✅ Tasdiqlash"
    re = "🔄 Изменить"     if is_ru else "🔄 Qayta kiritish"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ok, callback_data="confirm_zayavka_call_center")],
        [InlineKeyboardButton(text=re, callback_data="resend_zayavka_call_center")],
    ])

# =========================
# Inline: Tasdiqlash (TEXNIK XIZMAT)
# callback_data: confirm_zayavka_call_center_tech_service / resend_zayavka_call_center_tech_service
# =========================
def controller_confirmation_keyboard_tech_service(lang: str = 'uz') -> InlineKeyboardMarkup:
    is_ru = (lang or 'uz').lower().startswith('ru')
    ok = "✅ Подтвердить" if is_ru else "✅ Tasdiqlash"
    re = "🔄 Изменить"     if is_ru else "🔄 Qayta kiritish"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ok, callback_data="confirm_zayavka_call_center_tech_service")],
        [InlineKeyboardButton(text=re, callback_data="resend_zayavka_call_center_tech_service")],
    ])
