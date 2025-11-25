from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_warehouse_main_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    inbox = "📥 Inbox"
    inventory = "📦 Inventarizatsiya" if lang == "uz" else "📦 Инвентаризация"
    orders = "📋 Texnik ishlatgan materiallar" if lang == "uz" else "📋 Материалы использованные техником"
    statistics = "📊 Statistikalar" if lang == "uz" else "📊 Статистика"
    technician_material_to_give = "📦 Teknik xodimga mahsulot berish" if lang == "uz" else "📦 Отдать материал технику"
    technician_material_balance = "📦🔎 Teknikda qolgan mat." if lang == "uz" else "📦🔎 Остаток мат. у техника"
    export = "📤 Export" if lang == "uz" else "📤 Экспорт"
    change_lang = "🌐 Tilni o'zgartirish" if lang == "uz" else "🌐 Изменить язык"

    keyboard = [
        [KeyboardButton(text=inbox), KeyboardButton(text=inventory)],
        [KeyboardButton(text=orders), KeyboardButton(text=statistics)],
        [KeyboardButton(text=technician_material_to_give), KeyboardButton(text=technician_material_balance)],
        [KeyboardButton(text=export), KeyboardButton(text=change_lang)],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_inventory_actions_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    uz = {
        "add_new": "🆕 Yangi mahsulot qo'shish",
        "add_existing": "📦 Mavjud mahsulot sonini o'zgartirish",
        "update": "✏️ Mahsulotni yangilash",
        "low": "⚠️ Kam zaxira",
        "out": "❌ Tugagan mahsulotlar",
        "search": "🔎 Qidirish",
        "all": "📄 Barcha mahsulotlar",
        "back": "◀️ Orqaga",
    }
    ru = {
        "add_new": "🆕 Добавить новый товар",
        "add_existing": "📦 Изменить количество товара",
        "update": "✏️ Обновить товар",
        "low": "⚠️ Низкий запас",
        "out": "❌ Закончились",
        "search": "🔎 Поиск",
        "all": "📄 Все товары",
        "back": "◀️ Назад",
    }
    T = uz if lang == "uz" else ru

    keyboard = [
        [KeyboardButton(text=T["add_new"]), KeyboardButton(text=T["add_existing"])],
        [KeyboardButton(text=T["update"]), KeyboardButton(text=T["low"])],
        [KeyboardButton(text=T["out"]), KeyboardButton(text=T["search"])],
        [KeyboardButton(text=T["all"]), KeyboardButton(text=T["back"])],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# --- STATISTIKA MENYUSI (rasmga mos) ---

def get_warehouse_statistics_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:

    uz = {
        "inv": "📊 Inventarizatsiya statistikasi",
        "ord": "📦 Buyurtmalar statistikasi",
        "low": "⚠️ Kam zaxira statistikasi",
        "fin": "💰 Moliyaviy hisobot",
        "range": "📊 Vaqt oralig'idagi statistika",
        "back": "🔙 Orqaga",
    }
    ru = {
        "inv": "📊 Статистика инвентаризации",
        "ord": "📦 Статистика заказов",
        "low": "⚠️ Статистика низких запасов",
        "fin": "💰 Финансовый отчет",
        "range": "📊 Статистика за период",
        "back": "🔙 Назад",
    }
    T = uz if lang == "uz" else ru
    keyboard = [
        [KeyboardButton(text=T["inv"])],
        [KeyboardButton(text=T["ord"])],
        [KeyboardButton(text=T["low"])],
        [KeyboardButton(text=T["fin"])],
        [KeyboardButton(text=T["range"])],
        [KeyboardButton(text=T["back"])],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_stats_period_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:

    uz = {
        "daily": "📊 Kunlik statistika",
        "weekly": "📅 Haftalik statistika",
        "monthly": "📆 Oylik statistika",
        "yearly": "📈 Yillik statistika",
        "back": "🔙 Orqaga",
    }
    ru = {
        "daily": "📊 Дневная статистика",
        "weekly": "📅 Недельная статистика",
        "monthly": "📆 Месячная статистика",
        "yearly": "📈 Годовая статистика",
        "back": "🔙 Назад",
    }
    T = uz if lang == "uz" else ru
    keyboard = [
        [KeyboardButton(text=T["monthly"]), KeyboardButton(text=T["daily"])],
        [KeyboardButton(text=T["weekly"]),  KeyboardButton(text=T["yearly"])],
        [KeyboardButton(text=T["back"])],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_warehouse_export_types_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:

    uz = {
        "inventory": "📦 Inventarizatsiya",
        "statistics": "📊 Statistika"
    }
    ru = {
        "inventory": "📦 Инвентаризация",
        "statistics": "📊 Статистика"
    }
    T = uz if lang == "uz" else ru
    
    keyboard = [
        [InlineKeyboardButton(text=T["inventory"], callback_data="warehouse_export_inventory")],
        [InlineKeyboardButton(text=T["statistics"], callback_data="warehouse_export_statistics")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_warehouse_material_requests_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Material requests uchun order turlarini tanlash klaviaturasi
    """
    uz = {
        "connection": "🔗 Ulanish arizalari materiallari",
        "technician": "🔧 Texnik xizmat materiallari",
        "staff": "👥 Xodim arizalari materiallari",
        "back": "❌ Yopish"
    }
    ru = {
        "connection": "🔗 Материалы заявок на подключение",
        "technician": "🔧 Материалы техобслуживания", 
        "staff": "👥 Материалы заявок сотрудников",
        "back": "❌ Закрыть"
    }
    T = uz if lang == "uz" else ru
    
    keyboard = [
        [InlineKeyboardButton(text=T["connection"], callback_data="warehouse_material_requests_connection")],
        [InlineKeyboardButton(text=T["technician"], callback_data="warehouse_material_requests_technician")],
        [InlineKeyboardButton(text=T["staff"], callback_data="warehouse_material_requests_staff")],
        [InlineKeyboardButton(text=T["back"], callback_data="warehouse_material_requests_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_warehouse_export_formats_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:

    back_text = "◀️ Orqaga" if lang == "uz" else "◀️ Назад"
    
    keyboard = [
        [InlineKeyboardButton(text="CSV", callback_data="warehouse_format_csv")],
        [InlineKeyboardButton(text="Excel", callback_data="warehouse_format_xlsx")],
        [InlineKeyboardButton(text="Word", callback_data="warehouse_format_docx")],
        [InlineKeyboardButton(text="PDF", callback_data="warehouse_format_pdf")],
        [InlineKeyboardButton(text=back_text, callback_data="warehouse_export_back_types")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_warehouse_inbox_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Ombor inbox uchun order turlarini tanlash klaviaturasi
    """
    uz = {
        "connection": "🔗 Ulanish arizalari",
        "technician": "🔧 Texnik xizmat",
        "staff": "👥 Xodim arizalari",
        "back": "❌ Yopish"
    }
    ru = {
        "connection": "🔗 Заявки на подключение",
        "technician": "🔧 Техническое обслуживание", 
        "staff": "👥 Заявки сотрудников",
        "back": "❌ Закрыть"
    }
    T = uz if lang == "uz" else ru
    
    keyboard = [
        [InlineKeyboardButton(text=T["connection"], callback_data="warehouse_inbox_connection")],
        [InlineKeyboardButton(text=T["technician"], callback_data="warehouse_inbox_technician")],
        [InlineKeyboardButton(text=T["staff"], callback_data="warehouse_inbox_staff")],
        [InlineKeyboardButton(text=T["back"], callback_data="warehouse_inbox_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_warehouse_inbox_navigation_keyboard(
    current_index: int, 
    total_count: int, 
    lang: str = "uz"
) -> InlineKeyboardMarkup:
    """
    Ombor inbox arizalari orasida navigatsiya qilish uchun klaviatura
    """
    keyboard = []
    
    # Navigation buttons
    nav_row = []
    if current_index > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️", 
            callback_data=f"warehouse_prev_inbox_{current_index-1}"
        ))
    
    nav_row.append(InlineKeyboardButton(
        text=f"{current_index + 1}/{total_count}",
        callback_data="warehouse_page_info"
    ))
    
    if current_index < total_count - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️", 
            callback_data=f"warehouse_next_inbox_{current_index+1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Back to categories button
    back_text = "🔙 Orqaga" if lang == "uz" else "🔙 Назад"
    keyboard.append([InlineKeyboardButton(
        text=back_text, 
        callback_data="warehouse_inbox_back_to_categories"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_connection_inbox_controls(
    current_index: int,
    total_count: int,
    order_id: int,
    lang: str = "uz"
) -> InlineKeyboardMarkup:
    """
    Connection inbox uchun navigatsiya + Tasdiqlash tugmasi.
    """
    keyboard = []

    # Top row: navigation
    nav_row = []
    if current_index > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️",
            callback_data=f"warehouse_prev_inbox_{current_index-1}"
        ))
    nav_row.append(InlineKeyboardButton(
        text=f"{current_index + 1}/{total_count}",
        callback_data="warehouse_page_info"
    ))
    if current_index < total_count - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️",
            callback_data=f"warehouse_next_inbox_{current_index+1}"
        ))
    if nav_row:
        keyboard.append(nav_row)

    # Confirm row
    confirm_text = "✅ Tasdiqlash" if lang == "uz" else "✅ Подтвердить"
    keyboard.append([
        InlineKeyboardButton(text=confirm_text, callback_data=f"warehouse_confirm_conn_{order_id}")
    ])

    # Back row
    back_text = "🔙 Orqaga" if lang == "uz" else "🔙 Назад"
    keyboard.append([InlineKeyboardButton(
        text=back_text,
        callback_data="warehouse_inbox_back_to_categories"
    )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_technician_inbox_controls(
    current_index: int,
    total_count: int,
    order_id: int,
    lang: str = "uz"
) -> InlineKeyboardMarkup:
    """
    Technician inbox uchun navigatsiya + Tasdiqlash tugmasi.
    """
    keyboard = []

    # Navigation buttons
    nav_row = []
    if current_index > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️",
            callback_data=f"warehouse_prev_inbox_{current_index-1}"
        ))
    nav_row.append(InlineKeyboardButton(
        text=f"{current_index + 1}/{total_count}",
        callback_data="warehouse_page_info"
    ))
    if current_index < total_count - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️",
            callback_data=f"warehouse_next_inbox_{current_index+1}"
        ))
    if nav_row:
        keyboard.append(nav_row)

    # Confirm button with unique callback pattern
    confirm_text = "✅ Tasdiqlash" if lang == "uz" else "✅ Подтвердить"
    keyboard.append([
        InlineKeyboardButton(text=confirm_text, callback_data=f"warehouse_confirm_tech_{order_id}")
    ])

    # Back button
    back_text = "🔙 Orqaga" if lang == "uz" else "🔙 Назад"
    keyboard.append([InlineKeyboardButton(
        text=back_text,
        callback_data="warehouse_inbox_back_to_categories"
    )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_staff_inbox_controls(
    current_index: int,
    total_count: int,
    order_id: int,
    lang: str = "uz"
) -> InlineKeyboardMarkup:
    """
    Staff inbox uchun navigatsiya + Tasdiqlash tugmasi.
    """
    keyboard = []

    # Navigation buttons
    nav_row = []
    if current_index > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️",
            callback_data=f"warehouse_prev_inbox_{current_index-1}"
        ))
    nav_row.append(InlineKeyboardButton(
        text=f"{current_index + 1}/{total_count}",
        callback_data="warehouse_page_info"
    ))
    if current_index < total_count - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️",
            callback_data=f"warehouse_next_inbox_{current_index+1}"
        ))
    if nav_row:
        keyboard.append(nav_row)

    # Confirm button with unique callback pattern
    confirm_text = "✅ Tasdiqlash" if lang == "uz" else "✅ Подтвердить"
    keyboard.append([
        InlineKeyboardButton(text=confirm_text, callback_data=f"warehouse_confirm_staff_{order_id}")
    ])

    # Back button
    back_text = "🔙 Orqaga" if lang == "uz" else "🔙 Назад"
    keyboard.append([InlineKeyboardButton(
        text=back_text,
        callback_data="warehouse_inbox_back_to_categories"
    )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_warehouse_material_requests_navigation_keyboard(
    current_index: int, 
    total_count: int, 
    order_type: str,
    order_id: int,
    lang: str = "uz"
) -> InlineKeyboardMarkup:
    """
    Ombor material so'rovlari orasida navigatsiya qilish uchun klaviatura
    """
    keyboard = []
    
    # Navigation buttons
    nav_row = []
    if current_index > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️", 
            callback_data=f"warehouse_prev_{order_type}_{current_index-1}"
        ))
    
    nav_row.append(InlineKeyboardButton(
        text=f"{current_index + 1}/{total_count}",
        callback_data="warehouse_page_info"
    ))
    
    if current_index < total_count - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️", 
            callback_data=f"warehouse_next_{order_type}_{current_index+1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Confirm button
    confirm_text = "✅ Materiallarni tasdiqlash" if lang == "uz" else "✅ Подтвердить материалы"
    keyboard.append([InlineKeyboardButton(
        text=confirm_text,
        callback_data=f"warehouse_confirm_material_{order_type}_{order_id}"
    )])
    
    # Back to categories button
    back_text = "🔙 Orqaga" if lang == "uz" else "🔙 Назад"
    keyboard.append([InlineKeyboardButton(
        text=back_text, 
        callback_data="warehouse_back_to_categories"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)