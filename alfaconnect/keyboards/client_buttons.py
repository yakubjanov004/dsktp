from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from typing import List, Dict, Any
from config import settings


def get_contact_keyboard(lang="uz"):
    share_contact_text = "📱 Kontakt ulashish" if lang == "uz" else "📱 Поделиться контактом"
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=share_contact_text, request_contact=True)]],
        resize_keyboard=True
    )
    return keyboard

def get_client_main_menu(lang="uz"):
    service_order_text = "🔧 Texnik xizmat" if lang == "uz" else "🔧 Техническая служба"
    connection_order_text = "🔌 Ulanish uchun ariza" if lang == "uz" else "🔌 Заявка на подключение"
    smart_service_text = "🛜 Smart Service" if lang == "uz" else "🛜 Smart Service"
    contact_operator_text = "📞 Operator bilan bog'lanish" if lang == "uz" else "📞 Связаться с оператором"
    cabinet_text = "👤 Kabinet" if lang == "uz" else "👤 Кабинет"
    bot_guide_text = "📄 Bot qo'llanmasi" if lang == "uz" else " 📄Инструкция по использованию бота"
    change_language_text = "🌐 Tilni o'zgartirish" if lang == "uz" else "🌐 Изменить язык"
    
    buttons = [
        [
            KeyboardButton(text=connection_order_text),
            KeyboardButton(text=service_order_text)    
        ],
        [
            KeyboardButton(text=smart_service_text)
        ],
        [
            KeyboardButton(text=contact_operator_text),
            KeyboardButton(text=cabinet_text)
        ],
        [
            KeyboardButton(text=bot_guide_text),
            KeyboardButton(text=change_language_text)
        ]
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )
    return keyboard

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

def media_attachment_keyboard(lang="uz"):
    """Media biriktirish klaviaturasi - 2 tilda"""
    yes_text = "✅ Ha" if lang == "uz" else "✅ Да"
    no_text = "❌ Yo'q" if lang == "uz" else "❌ Нет"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=yes_text, callback_data="attach_media_yes")],
        [InlineKeyboardButton(text=no_text, callback_data="attach_media_no")]
    ])
    return keyboard

def geolocation_keyboard(lang="uz"):
    """Geolokatsiya klaviaturasi - 2 tilda"""
    yes_text = "✅ Ha" if lang == "uz" else "✅ Да"
    no_text = "❌ Yo'q" if lang == "uz" else "❌ Нет"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=yes_text, callback_data="send_location_yes")],
        [InlineKeyboardButton(text=no_text, callback_data="send_location_no")]
    ])
    return keyboard

def confirmation_keyboard(lang="uz"):
    """Tasdiqlash klaviaturasi - 2 tilda"""
    confirm_text = "✅ Tasdiqlash" if lang == "uz" else "✅ Подтвердить"
    resend_text = "🔄 Qayta yuborish" if lang == "uz" else "🔄 Отправить заново"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=confirm_text, callback_data="confirm_zayavka"),
            InlineKeyboardButton(text=resend_text, callback_data="resend_zayavka")
        ]
    ])
    return keyboard

# --- New Tariff Plans ---
B2C_PLANS = [
    {"name": "Oddiy-20", "price": "110,000", "speed_day": "20", "speed_night": "20", "tasix": "20", "reg": "75,000"},
    {"name": "Oddiy-50", "price": "130,000", "speed_day": "50", "speed_night": "50", "tasix": "50", "reg": "75,000"},
    {"name": "Oddiy-100", "price": "160,000", "speed_day": "100", "speed_night": "100", "tasix": "100", "reg": "75,000"},
    {"name": "XIT-200", "price": "200,000", "speed_day": "200", "speed_night": "200", "tasix": "200", "reg": "75,000"},
    {"name": "VIP-500", "price": "500,000", "speed_day": "500", "speed_night": "500", "tasix": "500", "reg": "0"},
    {"name": "PREMIUM", "price": "1,000,000", "speed_day": "1,000", "speed_night": "1,000", "tasix": "1,000", "reg": "0"},
]

BIZNET_PRO_PLANS = [
    {"name": "BizNET-Pro-1", "price": "600,000", "speed": "7", "tasix": "100"},
    {"name": "BizNET-Pro-2", "price": "700,000", "speed": "10", "tasix": "100"},
    {"name": "BizNET-Pro-3", "price": "1,200,000", "speed": "20", "tasix": "100"},
    {"name": "BizNET-Pro-4", "price": "1,500,000", "speed": "30", "tasix": "100"},
    {"name": "BizNET-Pro-5", "price": "1,800,000", "speed": "40", "tasix": "100"},
    {"name": "BizNET-Pro-6", "price": "2,000,000", "speed": "60", "tasix": "100"},
    {"name": "BizNET-Pro-7+", "price": "3,000,000", "speed": "100", "tasix": "100"},
]

TIJORAT_PLANS = [
    {"name": "Tijorat-1", "price": "320,000", "speed_day": "6", "speed_night": "2", "tasix": "100"},
    {"name": "Tijorat-2", "price": "360,000", "speed_day": "10", "speed_night": "3", "tasix": "100"},
    {"name": "Tijorat-3", "price": "480,000", "speed_day": "20", "speed_night": "6", "tasix": "100"},
    {"name": "Tijorat-4", "price": "800,000", "speed_day": "40", "speed_night": "12", "tasix": "100"},
    {"name": "Tijorat-5", "price": "1,120,000", "speed_day": "60", "speed_night": "20", "tasix": "100"},
    {"name": "Tijorat-100", "price": "1,760,000", "speed_day": "100", "speed_night": "50", "tasix": "100"},
    {"name": "Tijorat-300", "price": "5,280,000", "speed_day": "300", "speed_night": "150", "tasix": "300"},
    {"name": "Tijorat-500", "price": "8,800,000", "speed_day": "500", "speed_night": "300", "tasix": "500"},
    {"name": "Tijorat-1000", "price": "14,850,000", "speed_day": "1,000", "speed_night": "700", "tasix": "1,000"},
]

def get_client_tariff_selection_keyboard(connection_type: str, lang: str = 'uz') -> InlineKeyboardMarkup:
    """Tariff selection keyboard for client"""
    
    back_text = "◀️ Orqaga" if lang == 'uz' else "◀️ Назад"
    
    if connection_type == "b2c":
        # B2C plans - 2 per row
        keyboard = []
        for i in range(0, len(B2C_PLANS), 2):
            row = []
            row.append(InlineKeyboardButton(
                text=f"{B2C_PLANS[i]['name']} - {B2C_PLANS[i]['price']} so'm", 
                callback_data=f"b2c_plan_{i}"
            ))
            if i+1 < len(B2C_PLANS):
                row.append(InlineKeyboardButton(
                    text=f"{B2C_PLANS[i+1]['name']} - {B2C_PLANS[i+1]['price']} so'm", 
                    callback_data=f"b2c_plan_{i+1}"
                ))
            keyboard.append(row)
        # Add back button for B2C
        keyboard.append([InlineKeyboardButton(text=back_text, callback_data="back_to_connection_type")])
    else:
        # B2B - show BizNET-Pro and Tijorat options (side by side)
        keyboard = [
            [InlineKeyboardButton(text="BizNET-Pro", callback_data="biznet_select")],
            [InlineKeyboardButton(text="Tijorat", callback_data="tijorat_select")]
        ]
        # Add back button for B2B
        keyboard.append([InlineKeyboardButton(text=back_text, callback_data="back_to_connection_type")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_biznet_tariff_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    """BizNET-Pro tariff selection keyboard"""
    keyboard = []
    # 2 buttons per row
    for i in range(0, len(BIZNET_PRO_PLANS), 2):
        row = []
        row.append(InlineKeyboardButton(
            text=f"{BIZNET_PRO_PLANS[i]['name']} - {BIZNET_PRO_PLANS[i]['price']} so'm", 
            callback_data=f"biznet_plan_{i}"
        ))
        if i+1 < len(BIZNET_PRO_PLANS):
            row.append(InlineKeyboardButton(
                text=f"{BIZNET_PRO_PLANS[i+1]['name']} - {BIZNET_PRO_PLANS[i+1]['price']} so'm", 
                callback_data=f"biznet_plan_{i+1}"
            ))
        keyboard.append(row)
    
    back_text = "◀️ Orqaga" if lang == 'uz' else "◀️ Назад"
    keyboard.append([InlineKeyboardButton(text=back_text, callback_data="back_to_tariff_selection")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_tijorat_tariff_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    """Tijorat tariff selection keyboard"""
    keyboard = []
    # 2 buttons per row
    for i in range(0, len(TIJORAT_PLANS), 2):
        row = []
        row.append(InlineKeyboardButton(
            text=f"{TIJORAT_PLANS[i]['name']} - {TIJORAT_PLANS[i]['price']} so'm", 
            callback_data=f"tijorat_plan_{i}"
        ))
        if i+1 < len(TIJORAT_PLANS):
            row.append(InlineKeyboardButton(
                text=f"{TIJORAT_PLANS[i+1]['name']} - {TIJORAT_PLANS[i+1]['price']} so'm", 
                callback_data=f"tijorat_plan_{i+1}"
            ))
        keyboard.append(row)
    
    back_text = "◀️ Orqaga" if lang == 'uz' else "◀️ Назад"
    keyboard.append([InlineKeyboardButton(text=back_text, callback_data="back_to_tariff_selection")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_client_regions_keyboard(lang: str = 'uz') -> InlineKeyboardMarkup:
    """Regions selection keyboard for client (UZ/RU labels, stable callback_data)."""

    labels_uz = {
        "toshkent_city": "Toshkent shahri",
        "toshkent_region": "Toshkent viloyati",
        "andijon": "Andijon",
        "fergana": "Farg'ona",
        "namangan": "Namangan",
        "sirdaryo": "Sirdaryo",
        "jizzax": "Jizzax",
        "samarkand": "Samarqand",
        "bukhara": "Buxoro",
        "navoi": "Navoiy",
        "kashkadarya": "Qashqadaryo",
        "surkhandarya": "Surxondaryo",
        "khorezm": "Xorazm",
        "karakalpakstan": "Qoraqalpog'iston",
    }

    labels_ru = {
        "toshkent_city": "г. Ташкент",
        "toshkent_region": "Ташкентская область",
        "andijon": "Андижан",
        "fergana": "Фергана",
        "namangan": "Наманган",
        "sirdaryo": "Сырдарья",
        "jizzax": "Джизак",
        "samarkand": "Самарканд",
        "bukhara": "Бухара",
        "navoi": "Навои",
        "kashkadarya": "Кашкадарья",
        "surkhandarya": "Сурхандарья",
        "khorezm": "Хорезм",
        "karakalpakstan": "Каракалпакстан",
    }

    L = labels_ru if lang == 'ru' else labels_uz

    rows = [
        [("toshkent_city",), ("toshkent_region",)],
        [("andijon",), ("fergana",)],
        [("namangan",), ("sirdaryo",)],
        [("jizzax",), ("samarkand",)],
        [("bukhara",), ("navoi",)],
        [("kashkadarya",), ("surkhandarya",)],
        [("khorezm",), ("karakalpakstan",)],
    ]

    keyboard = []
    for row in rows:
        keyboard.append([
            InlineKeyboardButton(
                text=L[key],
                callback_data=f"region_{key}"
            ) for (key,) in row
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_contact_options_keyboard(lang: str = "uz", telegram_id: int = None):
    """Contact options keyboard with webapp button"""
    call_text = "📞 Qo'ng'iroq qilish" if lang == "uz" else "📞 Позвонить"
    chat_text = "💬 Onlayn chat" if lang == "uz" else "💬 Онлайн-чат"
    back_text = "◀️ Orqaga" if lang == "uz" else "◀️ Назад"
    
    webapp_url = settings.WEBAPP_URL
    
    # Telegram ID ni URL'ga qo'shish (fallback uchun)
    if telegram_id and webapp_url.startswith("https://"):
        # URL'ga query parameter qo'shish
        separator = "&" if "?" in webapp_url else "?"
        webapp_url_with_id = f"{webapp_url}{separator}telegram_id={telegram_id}"
    else:
        webapp_url_with_id = webapp_url
    
    # Telegram WebApp faqat HTTPS URL larni qabul qiladi
    # HTTP bo'lsa oddiy text button qilish kerak
    if webapp_url.startswith("https://"):
        chat_button = KeyboardButton(text=chat_text, web_app=WebAppInfo(url=webapp_url_with_id))
    else:
        # HTTP URL uchun oddiy text button (WebApp button yaratilmaydi)
        chat_button = KeyboardButton(text=chat_text)
    
    reply_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=call_text)],
            [chat_button],
            [KeyboardButton(text=back_text)],
        ],
        resize_keyboard=True,
    )

    return reply_keyboard

def get_client_profile_reply_keyboard(lang: str = 'uz') -> ReplyKeyboardMarkup:
    """Reply keyboard for client profile (cabinet) section"""
    view_info_text = "👀 Ma'lumotlarni ko'rish" if lang == 'uz' else "👀 Просмотр информации"
    view_orders_text = "📋 Mening arizalarim" if lang == 'uz' else "📋 Мои заявки"
    edit_name_text = "✏️ Ismni o'zgartirish" if lang == 'uz' else "✏️ Изменить имя"
    back_text = "◀️ Orqaga" if lang == 'uz' else "◀️ Назад"

    keyboard = [
        [KeyboardButton(text=view_info_text)],
        [KeyboardButton(text=view_orders_text)],
        [KeyboardButton(text=edit_name_text)],
        [KeyboardButton(text=back_text)],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_smart_service_categories_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Smart Service kategoriyalarini tanlash klaviaturasi - 2 tilda"""
    if lang == "uz":
        keyboard = [
            [InlineKeyboardButton(text="🏠 Aqlli uy va avtomatlashtirilgan xizmatlar", callback_data="cat_smart_home")],
            [InlineKeyboardButton(text="🔒 Xavfsizlik va kuzatuv tizimlari", callback_data="cat_security")],
            [InlineKeyboardButton(text="🌐 Internet va tarmoq xizmatlari", callback_data="cat_internet")],
            [InlineKeyboardButton(text="⚡ Energiya va yashil texnologiyalar", callback_data="cat_energy")],
            [InlineKeyboardButton(text="📺 Multimediya va aloqa tizimlari", callback_data="cat_multimedia")],
            [InlineKeyboardButton(text="🔧 Maxsus va qo'shimcha xizmatlar", callback_data="cat_special")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="🏠 Умный дом и автоматизация", callback_data="cat_smart_home")],
            [InlineKeyboardButton(text="🔒 Безопасность и видеонаблюдение", callback_data="cat_security")],
            [InlineKeyboardButton(text="🌐 Интернет и сети", callback_data="cat_internet")],
            [InlineKeyboardButton(text="⚡ Энергия и зелёные технологии", callback_data="cat_energy")],
            [InlineKeyboardButton(text="📺 Мультимедиа и коммуникации", callback_data="cat_multimedia")],
            [InlineKeyboardButton(text="🔧 Специальные и доп. услуги", callback_data="cat_special")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Old label dictionaries were removed; buttons are now defined inline per language



def get_smart_service_types_keyboard(category_key: str, lang: str = "uz") -> InlineKeyboardMarkup:
    """Tanlangan kategoriya bo'yicha service type klaviaturasi - 2 tilda"""
    if lang == "uz":
        uz_services_map = {
            "cat_smart_home": [
                ("Aqlli uy tizimlarini o'rnatish va sozlash", "srv_smart_home_setup"),
                ("Aqlli yoritish (Smart Lighting) tizimlari", "srv_smart_lighting"),
                ("Aqlli termostat va iqlim nazarati", "srv_smart_thermostat"),
                ("Smart Lock — internet orqali boshqariladigan qulflar", "srv_smart_lock"),
                ("Aqlli rozetalar va energiya monitoringi", "srv_smart_outlets"),
                ("Uyni masofadan boshqarish qurilmalari", "srv_remote_control"),
                ("Aqlli pardalar va jaluzlar", "srv_smart_curtains"),
                ("Aqlli maishiy texnika integratsiyasi", "srv_appliance_integration"),
            ],
            "cat_security": [
                ("Videokuzatuv kameralarini o'rnatish (IP/analog)", "srv_cctv_cameras"),
                ("Kamera arxiv tizimlari, bulutli saqlash", "srv_camera_storage"),
                ("Domofon tizimlari", "srv_intercom"),
                ("Xavfsizlik signalizatsiyasi va sensorlar", "srv_security_alarm"),
                ("Yong'in signalizatsiyasi tizimlari", "srv_fire_alarm"),
                ("Gaz sizishi/suv toshqiniga qarshi tizimlar", "srv_gas_flood_protection"),
                ("Yuzni tanish (Face Recognition) tizimlari", "srv_face_recognition"),
                ("Avtomatik eshik/darvoza boshqaruvi", "srv_automatic_gates"),
            ],
            "cat_internet": [
                ("Wi-Fi tarmoqlarini o'rnatish va sozlash", "srv_wifi_setup"),
                ("Wi-Fi qamrovini kengaytirish (Access Point)", "srv_wifi_extender"),
                ("Mobil aloqa signalini kuchaytirish (Repeater)", "srv_signal_booster"),
                ("Ofis/uy uchun lokal tarmoq (LAN) qurish", "srv_lan_setup"),
                ("Internet provayder xizmatlarini ulash", "srv_internet_provider"),
                ("Server va NAS qurilmalarini o'rnatish", "srv_server_nas"),
                ("Bulutli fayl almashish va zaxira", "srv_cloud_storage"),
                ("VPN va xavfsiz ulanishlar", "srv_vpn_setup"),
            ],
            "cat_energy": [
                ("Quyosh panellarini o'rnatish va ulash", "srv_solar_panels"),
                ("Quyosh batareyalari bilan energiya saqlash", "srv_solar_batteries"),
                ("Shamol generatorlarini o'rnatish", "srv_wind_generators"),
                ("Energiya tejamkor yoritish tizimlari", "srv_energy_saving_lighting"),
                ("Avtomatik sug'orish (Smart Irrigation)", "srv_smart_irrigation"),
            ],
            "cat_multimedia": [
                ("Smart TV o'rnatish va ulash", "srv_smart_tv"),
                ("Uy kinoteatri tizimlari", "srv_home_cinema"),
                ("Audio tizimlar (multiroom)", "srv_multiroom_audio"),
                ("IP-telefoniya, mini-ATS", "srv_ip_telephony"),
                ("Video konferensiya tizimlari", "srv_video_conference"),
                ("Interaktiv taqdimot (proyektor/LED)", "srv_presentation_systems"),
            ],
            "cat_special": [
                ("Aqlli ofis tizimlari", "srv_smart_office"),
                ("Data-markaz (Server room) loyihalash va montaj", "srv_data_center"),
                ("Qurilma/tizimlar uchun texnik xizmat", "srv_technical_support"),
                ("Dasturiy ta'minotni o'rnatish/yangilash", "srv_software_install"),
                ("IoT qurilmalarini integratsiya qilish", "srv_iot_integration"),
                ("Masofaviy boshqaruv tizimlari", "srv_remote_management"),
                ("Sun'iy intellekt asosidagi boshqaruv", "srv_ai_management"),
            ],
        }
        services = uz_services_map.get(category_key, [])
    else:
        ru_services_map = {
            "cat_smart_home": [
                ("Установка и настройка системы умного дома", "srv_smart_home_setup"),
                ("Умное освещение (Smart Lighting)", "srv_smart_lighting"),
                ("Умный термостат и климат-контроль", "srv_smart_thermostat"),
                ("Smart Lock — умный замок (через интернет)", "srv_smart_lock"),
                ("Умные розетки и мониторинг энергии", "srv_smart_outlets"),
                ("Дистанционное управление домом", "srv_remote_control"),
                ("Умные шторы и жалюзи", "srv_smart_curtains"),
                ("Интеграция умной бытовой техники", "srv_appliance_integration"),
            ],
            "cat_security": [
                ("Установка видеонаблюдения (IP/аналог)", "srv_cctv_cameras"),
                ("Архив и облачное хранение видео", "srv_camera_storage"),
                ("Домофонные системы", "srv_intercom"),
                ("Охранная сигнализация и датчики", "srv_security_alarm"),
                ("Пожарная сигнализация", "srv_fire_alarm"),
                ("Системы защиты от утечки газа/потопа", "srv_gas_flood_protection"),
                ("Распознавание лиц (Face Recognition)", "srv_face_recognition"),
                ("Автоматические двери/ворота", "srv_automatic_gates"),
            ],
            "cat_internet": [
                ("Установка и настройка Wi-Fi", "srv_wifi_setup"),
                ("Расширение покрытия Wi-Fi (Access Point)", "srv_wifi_extender"),
                ("Усиление мобильной связи (Repeater)", "srv_signal_booster"),
                ("Построение локальной сети (LAN)", "srv_lan_setup"),
                ("Подключение услуг интернет-провайдера", "srv_internet_provider"),
                ("Установка серверов и NAS", "srv_server_nas"),
                ("Обмен файлами и резервное копирование в облаке", "srv_cloud_storage"),
                ("VPN и защищённые подключения", "srv_vpn_setup"),
            ],
            "cat_energy": [
                ("Установка и подключение солнечных панелей", "srv_solar_panels"),
                ("Хранение энергии на солнечных батареях", "srv_solar_batteries"),
                ("Установка ветрогенераторов", "srv_wind_generators"),
                ("Энергоэффективное освещение", "srv_energy_saving_lighting"),
                ("Автополив (Smart Irrigation)", "srv_smart_irrigation"),
            ],
            "cat_multimedia": [
                ("Установка и подключение Smart TV", "srv_smart_tv"),
                ("Домашний кинотеатр", "srv_home_cinema"),
                ("Аудиосистемы (multiroom)", "srv_multiroom_audio"),
                ("IP-телефония, мини-АТС", "srv_ip_telephony"),
                ("Системы видеоконференций", "srv_video_conference"),
                ("Интерактивные презентации (проектор/LED)", "srv_presentation_systems"),
            ],
            "cat_special": [
                ("Системы умного офиса", "srv_smart_office"),
                ("Дата-центр (Server room): проектирование и монтаж", "srv_data_center"),
                ("Техобслуживание устройств/систем", "srv_technical_support"),
                ("Установка/обновление ПО", "srv_software_install"),
                ("Интеграция IoT-устройств", "srv_iot_integration"),
                ("Системы удалённого управления", "srv_remote_management"),
                ("AI-управление домом/офисом", "srv_ai_management"),
            ],
        }
        services = ru_services_map.get(category_key, [])

    # Single-button per row for better readability
    keyboard = [[InlineKeyboardButton(text=text, callback_data=cb)] for text, cb in services]

    back_text = "⬅️ Orqaga" if lang == "uz" else "⬅️ Назад"
    keyboard.append([InlineKeyboardButton(text=back_text, callback_data="back_to_categories")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_smart_service_confirmation_keyboard(lang="uz"):
    """Smart Service tasdiqlash klaviaturasi - 2 tilda"""
    confirm_text = "✅ Tasdiqlash" if lang == "uz" else "✅ Подтвердить"
    cancel_text = "❌ Bekor qilish" if lang == "uz" else "❌ Отменить"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=confirm_text, callback_data="confirm_smart_service"),
            InlineKeyboardButton(text=cancel_text, callback_data="cancel_smart_service")
        ]
    ])
    return keyboard

def get_rating_keyboard(request_id: int, request_type: str) -> InlineKeyboardMarkup:
    """
    Reyting keyboard yaratish (1-5 yulduz)
    """
    keyboard = []
    
    # Yulduzlar qatorlari
    for i in range(1, 6):
        stars_text = "⭐" * i
        keyboard.append([
            InlineKeyboardButton(
                text=stars_text,
                callback_data=f"rate:{request_id}:{request_type}:{i}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_skip_comment_keyboard(request_id: int, request_type: str, lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Izoh o'tkazib yuborish keyboard
    """
    skip_text = "O'tkazib yuborish" if lang == "uz" else "Пропустить"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=skip_text,
                callback_data=f"skip_comment:{request_id}:{request_type}"
            )
        ]
    ])
    return keyboard
