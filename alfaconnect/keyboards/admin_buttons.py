from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ========== Tizim holati (System Status) ==========

def get_system_status_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Tizim holati uchun inline keyboard"""
    overview_text = "📊 Umumiy ko'rinish" if lang == "uz" else "📊 Общий обзор"
    orders_text = "📝 Zayavkalar holati" if lang == "uz" else "📝 Статус заявок"
    performance_text = "⚡ Ishlash ko'rsatkichlari" if lang == "uz" else "⚡ Показатели производительности"
    activity_text = "🔄 So'nggi faoliyat" if lang == "uz" else "🔄 Последняя активность"
    database_text = "💾 Ma'lumotlar bazasi" if lang == "uz" else "💾 База данных"
    refresh_text = "🔄 Yangilash" if lang == "uz" else "🔄 Обновить"
    close_text = "❌ Yopish" if lang == "uz" else "❌ Закрыть"
    
    keyboard = [
        [
            InlineKeyboardButton(text=overview_text, callback_data="system_overview"),
            InlineKeyboardButton(text=orders_text, callback_data="system_orders")
        ],
        [
            InlineKeyboardButton(text=performance_text, callback_data="system_performance"),
            InlineKeyboardButton(text=activity_text, callback_data="system_activity")
        ],
        [
            InlineKeyboardButton(text=database_text, callback_data="system_database"),
            InlineKeyboardButton(text=refresh_text, callback_data="system_refresh")
        ],
        [
            InlineKeyboardButton(text=close_text, callback_data="system_close")
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ========== Umumiy (admin) ==========

def get_admin_main_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    statistics_text = "📊 Statistika" if lang == "uz" else "📊 Статистика"
    users_text = "👥 Foydalanuvchilar" if lang == "uz" else "👥 Пользователи"
    orders_text = "📝 Zayavkalar" if lang == "uz" else "📝 Заявки"
    export_text = "📤 Export" if lang == "uz" else "📤 Экспорт"
    language_text = "🌐 Til" if lang == "uz" else "🌐 Язык"
    backup_text = "🗄️ Backup & Logs" if lang == "uz" else "🗄️ Бэкап и логи"

    keyboard = [
        [KeyboardButton(text=statistics_text), KeyboardButton(text=users_text)],
        [KeyboardButton(text=orders_text), KeyboardButton(text=backup_text)],
        [KeyboardButton(text=export_text), KeyboardButton(text=language_text)],
    ]

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=False)

# ========== Admin Users (handlers/admin/users.py) ==========
def get_user_management_keyboard(lang="uz"):
    """Foydalanuvchi boshqaruv klaviaturasi - 2 tilda"""
    all_users_text = "👥 Barcha foydalanuvchilar" if lang == "uz" else "👥 Все пользователи"
    staff_text = "👤 Xodimlar" if lang == "uz" else "👤 Сотрудники"
    block_text = "🔒 Bloklash/Blokdan chiqarish" if lang == "uz" else "🔒 Блокировка/Разблокировка"
    role_text = "🔄 Rolni o'zgartirish" if lang == "uz" else "🔄 Изменить роль"
    back_text = "◀️ Orqaga" if lang == "uz" else "◀️ Назад"
    
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=all_users_text),
                KeyboardButton(text=staff_text)
            ],
            [
                KeyboardButton(text=block_text),
                KeyboardButton(text=role_text)
            ],
            [
                KeyboardButton(text=back_text)
            ]
        ],
        resize_keyboard=True
    )

# handlers/admin/users.py uchun
def get_inline_role_selection() -> InlineKeyboardMarkup:
    """Returns inline keyboard for role selection"""
    keyboard = [
        [
            InlineKeyboardButton(text="👤 Admin", callback_data="role_admin"),
            InlineKeyboardButton(text="👤 Mijoz", callback_data="role_client")
        ],
        [
            InlineKeyboardButton(text="👤 Menejer", callback_data="role_manager"),
            InlineKeyboardButton(text="👤 Junior Manager", callback_data="role_junior_manager")
        ],
        [
            InlineKeyboardButton(text="👤 Controller", callback_data="role_controller"),
            InlineKeyboardButton(text="👤 Texnik", callback_data="role_technician")
        ],
        [
            InlineKeyboardButton(text="👤 Ombor", callback_data="role_warehouse"),
            InlineKeyboardButton(text="👤 Call Center", callback_data="role_callcenter_operator")
        ],
        [
            InlineKeyboardButton(text="👤 Call Center Supervisor", callback_data="role_callcenter_supervisor")
        ],
        [
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="role_cancel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Bu bo'lim: users.py
def get_inline_search_method() -> InlineKeyboardMarkup:
    """Returns inline keyboard for search method selection"""
    keyboard = [
        [
            InlineKeyboardButton(text="🆔 Telegram ID orqali", callback_data="search_telegram_id"),
            InlineKeyboardButton(text="📱 Telefon raqam orqali", callback_data="search_phone")
        ],
        [
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="search_cancel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# handlers/admin/users.py uchun
def get_users_pagination_keyboard(current_page: int, total_pages: int, has_prev: bool, has_next: bool, user_type: str = "all") -> InlineKeyboardMarkup:
    """Foydalanuvchilar paginatsiyasi uchun klaviatura
    
    Args:
        current_page: Joriy sahifa raqami
        total_pages: Jami sahifalar soni
        has_prev: Oldingi sahifa mavjudligi
        has_next: Keyingi sahifa mavjudligi
        user_type: Foydalanuvchi turi (all, staff)
    
    Returns:
        InlineKeyboardMarkup: Paginatsiya klaviaturasi
    """
    keyboard = []
    
    # Navigatsiya tugmalari
    nav_row = []
    
    if has_prev:
        # Birinchi sahifa
        if current_page > 2:
            nav_row.append(InlineKeyboardButton(text="⏪ 1", callback_data=f"users_page_{user_type}_1"))
        
        # Oldingi sahifa
        nav_row.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"users_page_{user_type}_{current_page-1}"))
    
    # Joriy sahifa ko'rsatkichi
    nav_row.append(InlineKeyboardButton(text=f"📄 {current_page}/{total_pages}", callback_data="current_page"))
    
    if has_next:
        # Keyingi sahifa
        nav_row.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"users_page_{user_type}_{current_page+1}"))
        
        # Oxirgi sahifa
        if current_page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text=f"{total_pages} ⏩", callback_data=f"users_page_{user_type}_{total_pages}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Sahifa raqamlari (joriy sahifa atrofida)
    page_row = []
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, current_page + 2)
    
    for page in range(start_page, end_page + 1):
        if page == current_page:
            page_row.append(InlineKeyboardButton(text=f"• {page} •", callback_data="current_page"))
        else:
            page_row.append(InlineKeyboardButton(text=str(page), callback_data=f"users_page_{user_type}_{page}"))
    
    if len(page_row) > 1:  
        keyboard.append(page_row)
    
    # Yopish tugmasi
    keyboard.append([
        InlineKeyboardButton(text="❌ Yopish", callback_data="users_back_to_menu")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ========== Admin Orders (handlers/admin/orders.py) ==========
def get_applications_main_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    connection_text = "🔌 Ulanish zayavkalari" if lang == "uz" else "🔌 Заявки на подключение"
    technician_text = "🔧 Texnik zayavkalar" if lang == "uz" else "🔧 Технические заявки"
    staff_text = "👥 Xodim zayavkalari" if lang == "uz" else "👥 Заявки сотрудников"
    back_text = "◀️ Orqaga" if lang == "uz" else "◀️ Назад"

    keyboard = [
        [KeyboardButton(text=technician_text), KeyboardButton(text=connection_text)],
        [KeyboardButton(text=staff_text), KeyboardButton(text=back_text)]
    ]

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ========== Admin Orders Navigation (handlers/admin/orders.py) ==========
def get_orders_navigation_keyboard(current_index: int, total_orders: int, order_type: str, lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Zayavkalar orasida navigatsiya uchun inline keyboard
    """
    keyboard = []
    
    # Navigation tugmalari
    nav_buttons = []
    
    # Oldingi tugma
    if current_index > 0:
        prev_text = "⬅️ Oldingi" if lang == "uz" else "⬅️ Предыдущий"
        nav_buttons.append(InlineKeyboardButton(
            text=prev_text,
            callback_data=f"admin_order_prev_{order_type}_{current_index-1}"
        ))
    
    # Keyingi tugma
    if current_index < total_orders - 1:
        next_text = "Keyingi ➡️" if lang == "uz" else "Следующий ➡️"
        nav_buttons.append(InlineKeyboardButton(
            text=next_text,
            callback_data=f"admin_order_next_{order_type}_{current_index+1}"
        ))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Orqaga tugma
    back_text = "◀️ Orqaga" if lang == "uz" else "◀️ Назад"
    keyboard.append([InlineKeyboardButton(
        text=back_text,
        callback_data="admin_orders_back"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_statistics_keyboard(lang: str = "uz"):
    """Admin statistics section inline keyboard with bilingual support"""
    
    # Define button texts based on language
    overview_text = "📈 Umumiy ko'rinish" if lang == "uz" else "📈 Общий обзор"
    users_text = "👥 Foydalanuvchilar" if lang == "uz" else "👥 Пользователи"
    connection_text = "📋 Ulanish buyurtmalari" if lang == "uz" else "📋 Заявки на подключение"
    tech_text = "🔧 Texnik buyurtmalar" if lang == "uz" else "🔧 Технические заявки"
    roles_text = "👤 Rollar bo'yicha" if lang == "uz" else "👤 По ролям"
    monthly_text = "📊 Oylik statistika" if lang == "uz" else "📊 Месячная статистика"
    close_text = "❌ Yopish" if lang == "uz" else "❌ Закрыть"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=overview_text, callback_data="stats_overview"),
            InlineKeyboardButton(text=users_text, callback_data="stats_users")
        ],
        [
            InlineKeyboardButton(text=connection_text, callback_data="stats_connection_orders"),
            InlineKeyboardButton(text=tech_text, callback_data="stats_tech_orders")
        ],
        [
            InlineKeyboardButton(text=roles_text, callback_data="stats_by_roles"),
            InlineKeyboardButton(text=monthly_text, callback_data="stats_monthly")
        ],
        [
            InlineKeyboardButton(text=close_text, callback_data="stats_close")
        ]
    ])
    return keyboard


# ========== Admin Export ==========
def get_admin_export_types_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    if lang == "uz":
        keyboard = [
            [
                InlineKeyboardButton(text="👤 Foydalanuvchilar (mijozlar)", callback_data="admin_export_users_clients"),
                InlineKeyboardButton(text="👥 Xodimlar", callback_data="admin_export_users_staff"),
            ],
            [
                InlineKeyboardButton(text="🔌 Ulanish arizalari", callback_data="admin_export_connection"),
                InlineKeyboardButton(text="🔧 Texnik arizalar", callback_data="admin_export_technician"),
            ],
            [
                InlineKeyboardButton(text="👤 Xodim arizalari", callback_data="admin_export_staff"),
                InlineKeyboardButton(text="📦 Ombor inventarizatsiyasi", callback_data="admin_export_warehouse_inventory"),
            ],
            [
                InlineKeyboardButton(text="📊 Ombor statistikasi", callback_data="admin_export_warehouse_stats"),
                InlineKeyboardButton(text="📊 Statistika", callback_data="admin_export_statistics"),
            ],
            [InlineKeyboardButton(text="🚫 Yopish", callback_data="admin_export_end")],
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(text="👤 Пользователи (клиенты)", callback_data="admin_export_users_clients"),
                InlineKeyboardButton(text="👥 Сотрудники", callback_data="admin_export_users_staff"),
            ],
            [
                InlineKeyboardButton(text="🔌 Заявки на подключение", callback_data="admin_export_connection"),
                InlineKeyboardButton(text="🔧 Технические заявки", callback_data="admin_export_technician"),
            ],
            [
                InlineKeyboardButton(text="👤 Заявки сотрудников", callback_data="admin_export_staff"),
                InlineKeyboardButton(text="📦 Инвентаризация склада", callback_data="admin_export_warehouse_inventory"),
            ],
            [
                InlineKeyboardButton(text="📊 Статистика склада", callback_data="admin_export_warehouse_stats"),
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin_export_statistics"),
            ],
            [InlineKeyboardButton(text="🚫 Закрыть", callback_data="admin_export_end")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_time_period_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Time period selection keyboard for admin exports"""
    if lang == "uz":
        keyboard = [
            [InlineKeyboardButton(text="📅 Bugun", callback_data="admin_time_today")],
            [InlineKeyboardButton(text="📅 Hafta", callback_data="admin_time_week")],
            [InlineKeyboardButton(text="📅 Oy", callback_data="admin_time_month")],
            [InlineKeyboardButton(text="📅 Jami", callback_data="admin_time_total")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_export_back_types")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="📅 Сегодня", callback_data="admin_time_today")],
            [InlineKeyboardButton(text="📅 Неделя", callback_data="admin_time_week")],
            [InlineKeyboardButton(text="📅 Месяц", callback_data="admin_time_month")],
            [InlineKeyboardButton(text="📅 Всего", callback_data="admin_time_total")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_export_back_types")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_export_formats_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    if lang == "uz":
        keyboard = [
            [InlineKeyboardButton(text="CSV", callback_data="admin_format_csv")],
            [InlineKeyboardButton(text="Excel", callback_data="admin_format_xlsx")],
            [InlineKeyboardButton(text="Word", callback_data="admin_format_docx")],
            [InlineKeyboardButton(text="PDF", callback_data="admin_format_pdf")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_export_back_types")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="CSV", callback_data="admin_format_csv")],
            [InlineKeyboardButton(text="Excel", callback_data="admin_format_xlsx")],
            [InlineKeyboardButton(text="Word", callback_data="admin_format_docx")],
            [InlineKeyboardButton(text="PDF", callback_data="admin_format_pdf")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_export_back_types")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
