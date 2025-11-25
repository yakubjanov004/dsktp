from datetime import datetime
from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, Location
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from keyboards.client_buttons import (
    get_client_main_menu,
    get_smart_service_categories_keyboard,
    get_smart_service_types_keyboard,
    get_smart_service_confirmation_keyboard,
    geolocation_keyboard
)
from states.client_states import SmartServiceStates
from database.basic.user import get_user_by_telegram_id
from database.basic.language import get_user_language
from database.client.orders import create_smart_service_order
from config import settings
from loader import bot
import asyncpg

import logging

logger = logging.getLogger(__name__)
router = Router()

CATEGORY_MAPPING = {
    "cat_smart_home": {
        "uz": "aqlli_avtomatlashtirilgan_xizmatlar",
        "ru": "aqlli_avtomatlashtirilgan_xizmatlar"  
    },
    "cat_security": {
        "uz": "xavfsizlik_kuzatuv_tizimlari", 
        "ru": "xavfsizlik_kuzatuv_tizimlari"  
    },
    "cat_internet": {
        "uz": "internet_tarmoq_xizmatlari",
        "ru": "internet_tarmoq_xizmatlari"  
    },
    "cat_energy": {
        "uz": "energiya_yashil_texnologiyalar",
        "ru": "energiya_yashil_texnologiyalar" 
    },
    "cat_multimedia": {
        "uz": "multimediya_aloqa_tizimlari",
        "ru": "multimediya_aloqa_tizimlari"  
    },
    "cat_special": {
        "uz": "maxsus_qoshimcha_xizmatlar",
        "ru": "maxsus_qoshimcha_xizmatlar"  
    },
}

def resolve_category_label(category_key: str, lang: str) -> str:
    if lang == "uz":
        labels = {
            "cat_smart_home": "🏠 Aqlli uy va avtomatlashtirilgan xizmatlar",
            "cat_security": "🔒 Xavfsizlik va kuzatuv tizimlari",
            "cat_internet": "🌐 Internet va tarmoq xizmatlari",
            "cat_energy": "⚡ Energiya va yashil texnologiyalar",
            "cat_multimedia": "📺 Multimediya va aloqa tizimlari",
            "cat_special": "🔧 Maxsus va qo'shimcha xizmatlar",
        }
    else:
        labels = {
            "cat_smart_home": "🏠 Умный дом и автоматизация",
            "cat_security": "🔒 Безопасность и видеонаблюдение",
            "cat_internet": "🌐 Интернет и сети",
            "cat_energy": "⚡ Энергия и зелёные технологии",
            "cat_multimedia": "📺 Мультимедиа и коммуникации",
            "cat_special": "🔧 Специальные и доп. услуги",
        }
    return labels.get(category_key, category_key)


def resolve_service_label(service_key: str, lang: str) -> str:
    if lang == "uz":
        labels = {
            # Smart Home
            "srv_smart_home_setup": "Aqlli uy tizimlarini o'rnatish va sozlash",
            "srv_smart_lighting": "Aqlli yoritish (Smart Lighting) tizimlari",
            "srv_smart_thermostat": "Aqlli termostat va iqlim nazarati",
            "srv_smart_lock": "Smart Lock — internet orqali boshqariladigan qulflar",
            "srv_smart_outlets": "Aqlli rozetalar va energiya monitoringi",
            "srv_remote_control": "Uyni masofadan boshqarish qurilmalari",
            "srv_smart_curtains": "Aqlli pardalar va jaluzlar",
            "srv_appliance_integration": "Aqlli maishiy texnika integratsiyasi",
            # Security
            "srv_cctv_cameras": "Videokuzatuv kameralarini o'rnatish (IP/analog)",
            "srv_camera_storage": "Kamera arxiv tizimlari, bulutli saqlash",
            "srv_intercom": "Domofon tizimlari",
            "srv_security_alarm": "Xavfsizlik signalizatsiyasi va sensorlar",
            "srv_fire_alarm": "Yong'in signalizatsiyasi tizimlari",
            "srv_gas_flood_protection": "Gaz sizishi/suv toshqiniga qarshi tizimlar",
            "srv_face_recognition": "Yuzni tanish (Face Recognition) tizimlari",
            "srv_automatic_gates": "Avtomatik eshik/darvoza boshqaruvi",
            # Internet
            "srv_wifi_setup": "Wi-Fi tarmoqlarini o'rnatish va sozlash",
            "srv_wifi_extender": "Wi-Fi qamrovini kengaytirish (Access Point)",
            "srv_signal_booster": "Mobil aloqa signalini kuchaytirish (Repeater)",
            "srv_lan_setup": "Ofis/uy uchun lokal tarmoq (LAN) qurish",
            "srv_internet_provider": "Internet provayder xizmatlarini ulash",
            "srv_server_nas": "Server va NAS qurilmalarini o'rnatish",
            "srv_cloud_storage": "Bulutli fayl almashish va zaxira",
            "srv_vpn_setup": "VPN va xavfsiz ulanishlar",
            # Energy
            "srv_solar_panels": "Quyosh panellarini o'rnatish va ulash",
            "srv_solar_batteries": "Quyosh batareyalari bilan energiya saqlash",
            "srv_wind_generators": "Shamol generatorlarini o'rnatish",
            "srv_energy_saving_lighting": "Energiya tejamkor yoritish tizimlari",
            "srv_smart_irrigation": "Avtomatik sug'orish (Smart Irrigation)",
            # Multimedia
            "srv_smart_tv": "Smart TV o'rnatish va ulash",
            "srv_home_cinema": "Uy kinoteatri tizimlari",
            "srv_multiroom_audio": "Audio tizimlar (multiroom)",
            "srv_ip_telephony": "IP-telefoniya, mini-ATS",
            "srv_video_conference": "Video konferensiya tizimlari",
            "srv_presentation_systems": "Interaktiv taqdimot (proyektor/LED)",
            # Special
            "srv_smart_office": "Aqlli ofis tizimlari",
            "srv_data_center": "Data-markaz (Server room) loyihalash va montaj",
            "srv_technical_support": "Qurilma/tizimlar uchun texnik xizmat",
            "srv_software_install": "Dasturiy ta'minotni o'rnatish/yangilash",
            "srv_iot_integration": "IoT qurilmalarini integratsiya qilish",
            "srv_remote_management": "Masofaviy boshqaruv tizimlari",
            "srv_ai_management": "Sun'iy intellekt asosidagi boshqaruv",
        }
    else:
        labels = {
            # Smart Home
            "srv_smart_home_setup": "Установка и настройка системы умного дома",
            "srv_smart_lighting": "Умное освещение (Smart Lighting)",
            "srv_smart_thermostat": "Умный термостат и климат-контроль",
            "srv_smart_lock": "Smart Lock — умный замок (через интернет)",
            "srv_smart_outlets": "Умные розетки и мониторинг энергии",
            "srv_remote_control": "Дистанционное управление домом",
            "srv_smart_curtains": "Умные шторы и жалюзи",
            "srv_appliance_integration": "Интеграция умной бытовой техники",
            # Security
            "srv_cctv_cameras": "Установка видеонаблюдения (IP/аналог)",
            "srv_camera_storage": "Архив и облачное хранение видео",
            "srv_intercom": "Домофонные системы",
            "srv_security_alarm": "Охранная сигнализация и датчики",
            "srv_fire_alarm": "Пожарная сигнализация",
            "srv_gas_flood_protection": "Системы защиты от утечки газа/потопа",
            "srv_face_recognition": "Распознавание лиц (Face Recognition)",
            "srv_automatic_gates": "Автоматические двери/ворота",
            # Internet
            "srv_wifi_setup": "Установка и настройка Wi-Fi",
            "srv_wifi_extender": "Расширение покрытия Wi-Fi (Access Point)",
            "srv_signal_booster": "Усиление мобильной связи (Repeater)",
            "srv_lan_setup": "Построение локальной сети (LAN)",
            "srv_internet_provider": "Подключение услуг интернет-провайдера",
            "srv_server_nas": "Установка серверов и NAS",
            "srv_cloud_storage": "Обмен файлами и резервное копирование в облаке",
            "srv_vpn_setup": "VPN и защищённые подключения",
            # Energy
            "srv_solar_panels": "Установка и подключение солнечных панелей",
            "srv_solar_batteries": "Хранение энергии на солнечных батареях",
            "srv_wind_generators": "Установка ветрогенераторов",
            "srv_energy_saving_lighting": "Энергоэффективное освещение",
            "srv_smart_irrigation": "Автополив (Smart Irrigation)",
            # Multimedia
            "srv_smart_tv": "Установка и подключение Smart TV",
            "srv_home_cinema": "Домашний кинотеатр",
            "srv_multiroom_audio": "Аудиосистемы (multiroom)",
            "srv_ip_telephony": "IP-телефония, мини-АТС",
            "srv_video_conference": "Системы видеоконференций",
            "srv_presentation_systems": "Интерактивные презентации (проектор/LED)",
            # Special
            "srv_smart_office": "Системы умного офиса",
            "srv_data_center": "Дата-центр (Server room): проектирование и монтаж",
            "srv_technical_support": "Техобслуживание устройств/систем",
            "srv_software_install": "Установка/обновление ПО",
            "srv_iot_integration": "Интеграция IoT-устройств",
            "srv_remote_management": "Системы удалённого управления",
            "srv_ai_management": "AI-управление домом/офисом",
        }
    return labels.get(service_key, service_key)

# Map UI category keys to DB enum values
def map_category_key_to_db_value(category_key: str, language: str = 'uz') -> str:
    """Map category key to database value based on user language"""
    category_data = CATEGORY_MAPPING.get(category_key, {})
    return category_data.get(language, category_data.get('uz', category_key))

def map_service_key_to_db_value(service_key: str, language: str = 'uz') -> str:
    """Map service key to database value based on user language"""
    mapping = {
        # Smart Home
        "srv_smart_home_setup": "aqlli_uy_tizimlarini_ornatish_sozlash",
        "srv_smart_lighting": "aqlli_yoritish_smart_lighting_tizimlari",
        "srv_smart_thermostat": "aqlli_termostat_iqlim_nazarati_tizimlari",
        "srv_smart_lock": "smart_lock_internet_orqali_boshqariladigan_eshik_qulfi_tizimlari",
        "srv_smart_outlets": "aqlli_rozetalar_energiya_monitoring_tizimlari",
        "srv_remote_control": "uyni_masofadan_boshqarish_qurilmalari_yagona_uzim_orqali_boshqarish",
        "srv_smart_curtains": "aqlli_pardalari_jaluz_tizimlari",
        "srv_appliance_integration": "aqlli_malahiy_texnika_integratsiyasi",
        # Security
        "srv_cctv_cameras": "videokuzatuv_kameralarini_ornatish_ip_va_analog",
        "srv_camera_storage": "kamera_arxiv_tizimlari_bulutli_saqlash_xizmatlari",
        "srv_intercom": "domofon_tizimlari_ornatish",
        "srv_security_alarm": "xavfsizlik_signalizatsiyasi_harakat_sensorlarini_ornatish",
        "srv_fire_alarm": "yong_signalizatsiyasi_tizimlari",
        "srv_gas_flood_protection": "gaz_sizish_sav_toshqinliqqa_qarshi_tizimlar",
        "srv_face_recognition": "yuzni_tanish_face_recognition_tizimlari",
        "srv_automatic_gates": "avtomatik_eshik_darvoza_boshqaruv_tizimlari",
        # Internet
        "srv_wifi_setup": "wi_fi_tarmoqlarini_ornatish_sozlash",
        "srv_wifi_extender": "wi_fi_qamrov_zonasini_kengaytirish_access_point",
        "srv_signal_booster": "mobil_aloqa_signalini_kuchaytirish_repeater",
        "srv_lan_setup": "ofis_va_uy_uchun_lokal_tarmoq_lan_qurish",
        "srv_internet_provider": "internet_provayder_xizmatlarini_ulash",
        "srv_server_nas": "server_va_nas_qurilmalarini_ornatish",
        "srv_cloud_storage": "bulutli_fayl_almashish_zaxira_tizimlari",
        "srv_vpn_setup": "vpn_va_xavfsiz_internet_ulanishlarini_tashkil_qilish",
        # Energy
        "srv_solar_panels": "quyosh_panellarini_ornatish_ulash",
        "srv_solar_batteries": "quyosh_batareyalari_orqali_energiya_saqlash_tizimlari",
        "srv_wind_generators": "shamol_generatorlarini_ornatish",
        "srv_energy_saving_lighting": "elektr_energiyasini_tejovchi_yoritish_tizimlari",
        "srv_smart_irrigation": "avtomatik_suv_orish_tizimlari_smart_irrigation",
        # Multimedia
        "srv_smart_tv": "smart_tv_ornatish_ulash",
        "srv_home_cinema": "uy_kinoteatri_tizimlari_ornatish",
        "srv_multiroom_audio": "audio_tizimlar_multiroom",
        "srv_ip_telephony": "ip_telefoniya_mini_ats_tizimlarini_tashkil_qilish",
        "srv_video_conference": "video_konferensiya_tizimlari",
        "srv_presentation_systems": "interaktiv_taqdimot_tizimlari_proyektor_led_ekran",
        # Special
        "srv_smart_office": "aqlli_ofis_tizimlarini_ornatish",
        "srv_data_center": "data_markaz_server_room_loyihalash_montaj_qilish",
        "srv_technical_support": "qurilma_tizimlar_uchun_texnik_xizmat_korsatish",
        "srv_software_install": "dasturiy_taminotni_ornatish_yangilash",
        "srv_iot_integration": "iot_internet_of_things_qurilmalarini_integratsiya_qilish",
        "srv_remote_management": "qurilmalarni_masofadan_boshqarish_tizimlarini_sozlash",
        "srv_ai_management": "suniy_intellekt_asosidagi_uy_ofis_boshqaruv_tizimlari",
    }
    
    return mapping.get(service_key, service_key)

SERVICE_TYPE_MAPPING = {
    # Smart Home Services
    "srv_smart_home_setup": "aqlli_uy_tizimlarini_ornatish_sozlash",
    "srv_smart_lighting": "aqlli_yoritish_smart_lighting_tizimlari",
    "srv_smart_thermostat": "aqlli_termostat_iqlim_nazarati_tizimlari",
    "srv_smart_lock": "smart_lock_internet_orqali_boshqariladigan_eshik_qulfi_tizimlari",
    "srv_smart_outlets": "aqlli_rozetalar_energiya_monitoring_tizimlari",
    "srv_remote_control": "uyni_masofadan_boshqarish_qurilmalari_yagona_uzim_orqali_boshqarish",
    "srv_smart_curtains": "aqlli_pardalari_jaluz_tizimlari",
    "srv_appliance_integration": "aqlli_malahiy_texnika_integratsiyasi",
    
    # Security Services
    "srv_cctv_cameras": "videokuzatuv_kameralari_ornatish_ip_va_analog",
    "srv_camera_storage": "kamera_arxiv_tizimlari_bulutli_saqlash_xizmatlari",
    "srv_intercom": "domofon_tizimlari_ornatish",
    "srv_security_alarm": "xavfsizlik_signalizatsiyasi_harakat_sensorlarini_ornatish",
    "srv_fire_alarm": "yong_signalizatsiyasi_tizimlari",
    "srv_gas_flood_protection": "gaz_sizish_sav_toshqinliqqa_qarshi_tizimlar",
    "srv_face_recognition": "yuzni_tanish_face_recognition_tizimlari",
    "srv_automatic_gates": "avtomatik_eshik_darvoza_boshqaruv_tizimlari",
    
    # Internet Services
    "srv_wifi_setup": "wi_fi_tarmoqlarini_ornatish_sozlash",
    "srv_wifi_extender": "wi_fi_qamrov_zonasini_kengaytirish_access_point",
    "srv_signal_booster": "mobil_aloqa_signalini_kuchaytirish_repeater",
    "srv_lan_setup": "ofis_va_uy_uchun_lokal_tarmoq_lan_qurish",
    "srv_internet_provider": "internet_provayder_xizmatlarini_ulash",
    "srv_server_nas": "server_va_nas_qurilmalarini_ornatish",
    "srv_cloud_storage": "bulutli_fayl_almashish_zaxira_tizimlari",
    "srv_vpn_setup": "vpn_va_xavfsiz_internet_ulanishlarini_tashkil_qilish",
    
    # Energy Services
    "srv_solar_panels": "quyosh_panellarini_ornatish_ulash",
    "srv_solar_batteries": "quyosh_batareyalari_orqali_energiya_saqlash_tizimlari",
    "srv_wind_generators": "shamol_generatorlarini_ornatish",
    "srv_energy_saving_lighting": "elektr_energiyasini_tejovchi_yoritish_tizimlari",
    "srv_smart_irrigation": "avtomatik_suv_orish_tizimlari_smart_irrigation",
    
    # Multimedia Services
    "srv_smart_tv": "smart_tv_ornatish_ulash",
    "srv_home_cinema": "uy_kinoteatri_tizimlari_ornatish",
    "srv_multiroom_audio": "audio_tizimlar_multiroom",
    "srv_ip_telephony": "ip_telefoniya_mini_ats_tizimlarini_tashkil_qilish",
    "srv_video_conference": "video_konferensiya_tizimlari",
    "srv_presentation_systems": "interaktiv_taqdimot_tizimlari_proyektor_led_ekran",
    
    # Special Services
    "srv_smart_office": "aqlli_ofis_tizimlarini_ornatish",
    "srv_data_center": "data_markaz_server_room_loyihalash_montaj_qilish",
    "srv_technical_support": "qurilma_tizimlar_uchun_texnik_xizmat_korsatish",
    "srv_software_install": "dasturiy_taminotni_ornatish_yangilash",
    "srv_iot_integration": "iot_internet_of_things_qurilmalarini_integratsiya_qilish",
    "srv_remote_management": "qurilmalarni_masofadan_boshqarish_tizimlarini_sozlash",
    "srv_ai_management": "suniy_intellekt_asosidagi_uy_ofis_boshqaruv_tizimlari"
}

@router.message(F.text.in_(["🛜 Smart Service"]))
async def start_smart_service(message: Message, state: FSMContext):
    try:
        await state.update_data(telegram_id=message.from_user.id)
        
        user_lang = await get_user_language(message.from_user.id)
        await state.update_data(user_lang=user_lang)
        
        welcome_text = (
            "🛜 <b>Smart Service</b>\n\n"
            "Quyidagi kategoriyalardan birini tanlang:"
        ) if user_lang == "uz" else (
            "🛜 <b>Smart Service</b>\n\n"
            "Выберите одну из следующих категорий:"
        )
        
        await message.answer(
            welcome_text,
            reply_markup=get_smart_service_categories_keyboard(user_lang),
            parse_mode='HTML'
        )
        await state.set_state(SmartServiceStates.selecting_category)
        
    except Exception as e:
        logger.error(f"Error in start_smart_service: {e}")
        try:
            lang_fallback = await get_user_language(message.from_user.id) or "uz"
        except Exception:
            lang_fallback = "uz"
        error_text = "❌ Xatolik yuz berdi." if lang_fallback == "uz" else "❌ Произошла ошибка."
        await message.answer(error_text)

# Kategoriya tanlash
@router.callback_query(F.data.startswith("cat_"), StateFilter(SmartServiceStates.selecting_category))
async def handle_category_selection(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
        
        callback_data = callback.data
        data = await state.get_data()
        user_lang = data.get('user_lang') or await get_user_language(callback.from_user.id)
        
        # Kategoriya nomini olish (bilingual)
        category_name = resolve_category_label(callback_data, user_lang)
        
        await state.update_data(selected_category=callback_data)
        
        service_selection_text = (
            f"📋 <b>{category_name}</b>\n\n"
            "Quyidagi xizmat turlaridan birini tanlang:"
        ) if user_lang == "uz" else (
            f"📋 <b>{category_name}</b>\n\n"
            "Выберите один из следующих типов услуг:"
        )
        
        await callback.message.edit_text(
            service_selection_text,
            reply_markup=get_smart_service_types_keyboard(callback_data, user_lang),
            parse_mode='HTML'
        )
        await state.set_state(SmartServiceStates.selecting_service_type)
        
    except Exception as e:
        logger.error(f"Error in handle_category_selection: {e}")
        try:
            lang_fallback = (await state.get_data()).get('user_lang') or await get_user_language(callback.from_user.id) or "uz"
        except Exception:
            lang_fallback = "uz"
        error_text = "❌ Xatolik yuz berdi." if lang_fallback == "uz" else "❌ Произошла ошибка."
        await callback.answer(error_text, show_alert=True)

# Fallback handler for old callback data format
@router.callback_query(F.data.startswith("category_"), StateFilter(SmartServiceStates.selecting_category))
async def handle_old_category_selection(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
        
        callback_data = callback.data
        logger.info(f"Received old callback data: {callback_data}")
        
        # Extract category from old format
        category = callback.data.replace("category_", "")
        
        # Map old category names to new ones
        old_to_new_mapping = {
            "aqlli_avtomatlashtirilgan_xizmatlar": "cat_smart_home",
            "xavfsizlik_kuzatuv_tizimlari": "cat_security", 
            "internet_tarmoq_xizmatlari": "cat_internet",
            "energiya_yashil_texnologiyalar": "cat_energy",
            "multimediya_aloqa_tizimlari": "cat_multimedia",
            "maxsus_qoshimcha_xizmatlar": "cat_special"
        }
        
        new_callback = old_to_new_mapping.get(category)
        if new_callback:
            data = await state.get_data()
            user_lang = data.get('user_lang') or await get_user_language(callback.from_user.id)
            category_name = resolve_category_label(new_callback, user_lang)

            await state.update_data(selected_category=new_callback)

            await callback.message.edit_text(
                (
                    "🛜 <b>Smart Service</b>\n\n"  # align with new copy
                    f"📂 <b>Kategoriya:</b> {category_name}\n\n"
                    "Quyidagi xizmat turlaridan birini tanlang:" if user_lang == "uz" else f"📂 <b>Категория:</b> {category_name}\n\nВыберите один из следующих типов услуг:"
                ),
                reply_markup=get_smart_service_types_keyboard(new_callback, user_lang),
                parse_mode='HTML'
            )
            await state.set_state(SmartServiceStates.selecting_service_type)
            return
        
        data = await state.get_data()
        user_lang = data.get('user_lang') or await get_user_language(callback.from_user.id)
        await callback.answer(
            "Eski format - qayta urinib ko'ring" if user_lang == "uz" else "Старый формат — попробуйте ещё раз",
            show_alert=True
        )
        
    except Exception as e:
        logger.error(f"Error in handle_old_category_selection: {e}")
        user_lang = await get_user_language(callback.from_user.id)
        await callback.answer(
            "Xatolik yuz berdi" if user_lang == "uz" else "Произошла ошибка",
            show_alert=True
        )

# Xizmat turi tanlash
@router.callback_query(F.data.startswith("srv_"), StateFilter(SmartServiceStates.selecting_service_type))
async def handle_service_type_selection(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
        
        service_key = callback.data
        user_lang = await get_user_language(callback.from_user.id)
        
        # Service type nomini olish (bilingual)
        service_name = resolve_service_label(service_key, user_lang)
        
        await state.update_data(selected_service_type=service_key)
        
        address_request_text = (
            f"📍 <b>Tanlangan xizmat:</b> {service_name}\n\n"
            "Iltimos, xizmat ko'rsatiladigan manzilni kiriting:"
        ) if user_lang == "uz" else (
            f"📍 <b>Выбранная услуга:</b> {service_name}\n\n"
            "Пожалуйста, введите адрес оказания услуги:"
        )
        
        await callback.message.edit_text(
            address_request_text,
            parse_mode='HTML'
        )
        await state.set_state(SmartServiceStates.entering_address)
        
    except Exception as e:
        logger.error(f"Error in handle_service_type_selection: {e}")
        try:
            lang_fallback = (await state.get_data()).get('user_lang') or await get_user_language(callback.from_user.id) or "uz"
        except Exception:
            lang_fallback = "uz"
        error_text = "❌ Xatolik yuz berdi." if lang_fallback == "uz" else "❌ Произошла ошибка."
        await callback.answer(error_text, show_alert=True)

# Fallback handler for old service callback data format
@router.callback_query(F.data.startswith("service_"), StateFilter(SmartServiceStates.selecting_service_type))
async def handle_old_service_type_selection(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
        
        callback_data = callback.data
        logger.info(f"Received old service callback data: {callback_data}")
        
        # Extract service type from old format
        service_type = callback.data.replace("service_", "")
        await state.update_data(selected_service_type=service_type)
        
        await callback.message.edit_text(
            "🛜 <b>SmartService</b>\n\n"
            "📍 <b>Manzil kiriting:</b>\n"
            "Xizmat ko'rsatish kerak bo'lgan to'liq manzilni yozing.",
            parse_mode='HTML'
        )
        await state.set_state(SmartServiceStates.entering_address)
        
    except Exception as e:
        logger.error(f"Error in handle_old_service_type_selection: {e}")
        await callback.answer("Xatolik yuz berdi", show_alert=True)

# Orqaga qaytish
@router.callback_query(F.data == "back_to_categories", StateFilter(SmartServiceStates.selecting_service_type))
async def back_to_categories(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
        
        user_lang = await get_user_language(callback.from_user.id)
        
        welcome_text = (
            "🛜 <b>Smart Service</b>\n\n"
            "Quyidagi kategoriyalardan birini tanlang:"
        ) if user_lang == "uz" else (
            "🛜 <b>Smart Service</b>\n\n"
            "Выберите одну из следующих категорий:"
        )
        
        await callback.message.edit_text(
            welcome_text,
            reply_markup=get_smart_service_categories_keyboard(user_lang),
            parse_mode='HTML'
        )
        await state.set_state(SmartServiceStates.selecting_category)
        
    except Exception as e:
        logger.error(f"Error in back_to_categories: {e}")
        try:
            lang_fallback = (await state.get_data()).get('user_lang') or await get_user_language(callback.from_user.id) or "uz"
        except Exception:
            lang_fallback = "uz"
        error_text = "❌ Xatolik yuz berdi." if lang_fallback == "uz" else "❌ Произошла ошибка."
        await callback.answer(error_text, show_alert=True)

# Manzil kiritish
@router.message(StateFilter(SmartServiceStates.entering_address))
async def handle_address_input(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        user_lang = data.get('user_lang') or await get_user_language(message.from_user.id) or "uz"

        # Validate that text exists and is non-empty
        if not getattr(message, 'text', None) or not message.text:
            prompt_text = (
                "❌ Iltimos, manzilni matn ko'rinishida yuboring." if user_lang == "uz"
                else "❌ Пожалуйста, отправьте адрес текстом."
            )
            await message.answer(prompt_text)
            return

        address = message.text.strip()
        
        if len(address) < 10:
            error_text = (
                "❌ Manzil juda qisqa. Iltimos, to'liq manzilni kiriting." if user_lang == "uz"
                else "❌ Адрес слишком короткий. Пожалуйста, введите полный адрес."
            )
            await message.answer(error_text)
            return
            
        await state.update_data(address=address)
        
        location_request_text = (
            "📍 <b>Manzil qabul qilindi!</b>\n\n"
            "Geolokatsiyangizni yuborishni xohlaysizmi?\n"
            "Bu bizga aniq joylashuvni aniqlashga yordam beradi."
        ) if user_lang == "uz" else (
            "📍 <b>Адрес принят!</b>\n\n"
            "Хотите ли вы отправить свою геолокацию?\n"
            "Это поможет нам определить точное местоположение."
        )
        
        await message.answer(
            location_request_text,
            reply_markup=geolocation_keyboard(user_lang),
            parse_mode='HTML'
        )
        await state.set_state(SmartServiceStates.asking_for_location)
        
    except Exception as e:
        logger.error(f"Error in handle_address_input: {e}")
        try:
            data = await state.get_data()
            user_lang = data.get('user_lang')
            if not user_lang:
                user_lang = await get_user_language(message.from_user.id) or "uz"
        except Exception:
            user_lang = "uz"
        
        error_text = "❌ Xatolik yuz berdi." if user_lang == "uz" else "❌ Произошла ошибка."
        await message.answer(error_text)

# Lokatsiya so'rash
@router.callback_query(F.data.in_(["send_location_yes", "send_location_no"]), StateFilter(SmartServiceStates.asking_for_location))
async def handle_location_request(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
        
        data = await state.get_data()
        user_lang = data.get('user_lang') or await get_user_language(callback.from_user.id)
        
        if callback.data == "send_location_yes":
            location_instruction_text = (
                "📍 <b>Geolokatsiya yuborish</b>\n\n"
                "Iltimos, telefon orqali geolokatsiyangizni yuboring.\n"
                "Buning uchun 📎 tugmasini bosib, 'Location' ni tanlang." if user_lang == "uz"
                else "📍 <b>Отправка геолокации</b>\n\n"
                "Пожалуйста, отправьте свою геолокацию через телефон.\n"
                "Для этого нажмите кнопку 📎 и выберите 'Location'."
            )
            
            await callback.message.edit_text(
                location_instruction_text,
                parse_mode='HTML'
            )
            await state.set_state(SmartServiceStates.waiting_for_location)
        else:
            await state.update_data(longitude=None, latitude=None)
            skip_text = (
                "🚫 Geolokatsiya yuborilmadi." if user_lang == "uz" else "🚫 Геолокация не отправлена."
            )
            # Remove inline keyboard by editing the same message
            try:
                await callback.message.edit_text(skip_text, parse_mode='HTML')
            except Exception:
                pass
            await show_confirmation(callback.message, state)
            
    except Exception as e:
        logger.error(f"Error in handle_location_request: {e}")
        user_lang = await get_user_language(callback.from_user.id)
        error_text = "❌ Xatolik yuz berdi." if user_lang == "uz" else "❌ Произошла ошибка."
        await callback.answer(error_text, show_alert=True)

# Lokatsiya qabul qilish
@router.message(F.location, StateFilter(SmartServiceStates.waiting_for_location))
async def handle_location(message: Message, state: FSMContext):
    try:
        location = message.location
        data = await state.get_data()
        user_lang = data.get('user_lang') or await get_user_language(message.from_user.id)
        
        await state.update_data(
            longitude=location.longitude,
            latitude=location.latitude
        )
        
        success_text = (
            "✅ Geolokatsiya qabul qilindi!"
        ) if user_lang == "uz" else (
            "✅ Геолокация получена!"
        )
        
        await message.answer(success_text)
        await show_confirmation(message, state)
        
    except Exception as e:
        logger.error(f"Error in handle_location: {e}")
        try:
            lang_fallback = (await state.get_data()).get('user_lang') or await get_user_language(message.from_user.id) or "uz"
        except Exception:
            lang_fallback = "uz"
        error_text = "❌ Xatolik yuz berdi." if lang_fallback == "uz" else "❌ Произошла ошибка."
        await message.answer(error_text)

# Tasdiqlash ko'rsatish
async def show_confirmation(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        user_lang = data.get('user_lang') or await get_user_language(message.from_user.id)
        
        selected_category = data.get('selected_category')
        selected_service_type = data.get('selected_service_type')
        address = data.get('address')
        longitude = data.get('longitude')
        latitude = data.get('latitude')
        
        category_name = resolve_category_label(selected_category, user_lang)
        service_name = resolve_service_label(selected_service_type, user_lang)
        
        location_info = ""
        if longitude and latitude:
            if user_lang == "uz":
                location_info = (
                    f"🌍 <b>Geolokatsiya:</b> {latitude:.6f}, {longitude:.6f}\n"
                )
            else:
                location_info = (
                    f"🌍 <b>Геолокация:</b> {latitude:.6f}, {longitude:.6f}\n"
                )
        
        confirmation_text = (
            "📋 <b>Buyurtma ma'lumotlari</b>\n\n"
            f"📂 <b>Kategoriya:</b> {category_name}\n"
            f"🔧 <b>Xizmat turi:</b> {service_name}\n"
            f"📍 <b>Manzil:</b> {address}\n"
            f"{location_info}\n"
            "Barcha ma'lumotlar to'g'rimi?"
        ) if user_lang == "uz" else (
            "📋 <b>Данные заказа</b>\n\n"
            f"📂 <b>Категория:</b> {category_name}\n"
            f"🔧 <b>Тип услуги:</b> {service_name}\n"
            f"📍 <b>Адрес:</b> {address}\n"
            f"{location_info}\n"
            "Все данные верны?"
        )
        
        await message.answer(
            confirmation_text,
            reply_markup=get_smart_service_confirmation_keyboard(user_lang),
            parse_mode='HTML'
        )
        await state.set_state(SmartServiceStates.confirming_order)
        
    except Exception as e:
        logger.error(f"Error in show_confirmation: {e}")
        try:
            lang_fallback = (await state.get_data()).get('user_lang') or await get_user_language(message.from_user.id) or "uz"
        except Exception:
            lang_fallback = "uz"
        error_text = "❌ Xatolik yuz berdi." if lang_fallback == "uz" else "❌ Произошла ошибка."
        await message.answer(error_text)

# Tasdiqlash
@router.callback_query(F.data.in_(["confirm_smart_service", "cancel_smart_service"]), StateFilter(SmartServiceStates.confirming_order))
async def handle_confirmation(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
        
        data = await state.get_data()
        user_lang = data.get('user_lang') or await get_user_language(callback.from_user.id)
        
        if callback.data == "confirm_smart_service":
            await finish_smart_service_order(callback, state)
        else:
            cancel_text = (
                "❌ Buyurtma bekor qilindi.\n"
                "Yangi buyurtma berish uchun /start buyrug'ini yuboring."
            ) if user_lang == "uz" else (
                "❌ Заказ отменён.\n"
                "Для создания нового заказа отправьте команду /start."
            )
            
            await callback.message.edit_text(cancel_text)
            await state.clear()
            
    except Exception as e:
        logger.error(f"Error in handle_confirmation: {e}")
        try:
            lang_fallback = (await state.get_data()).get('user_lang') or await get_user_language(callback.from_user.id) or "uz"
        except Exception:
            lang_fallback = "uz"
        error_text = "❌ Xatolik yuz berdi." if lang_fallback == "uz" else "❌ Произошла ошибка."
        await callback.answer(error_text, show_alert=True)


async def finish_smart_service_order(callback_or_message, state: FSMContext):
    try:
        # Prevent bot from creating smart service orders
        logger.info(f"Smart service order attempt - User ID: {callback_or_message.from_user.id}, Bot ID: {settings.BOT_ID}, Username: {callback_or_message.from_user.username}, Full name: {callback_or_message.from_user.full_name}")
        
        if callback_or_message.from_user.id == settings.BOT_ID:
            logger.warning(f"Bot attempted to create smart service order, ignoring - this might be a bot loop issue")
            return
            
        if not callback_or_message.from_user.username and not callback_or_message.from_user.full_name:
            logger.warning(f"User with no username/full_name attempted to create smart service order, ignoring")
            return
            
        data = await state.get_data()
        telegram_id = callback_or_message.from_user.id
        user_lang = (await state.get_data()).get('user_lang') or await get_user_language(telegram_id)
        
        # Ensure we have the correct user ID
        logger.info(f"Processing smart service order for user ID: {telegram_id}, Username: {callback_or_message.from_user.username}, Full name: {callback_or_message.from_user.full_name}")
        
        from database.basic.user import ensure_user
        ensured = await ensure_user(
            telegram_id=telegram_id,
            full_name=callback_or_message.from_user.full_name,
            username=callback_or_message.from_user.username,
            role='client'
        )
        
        if ensured is None or ensured.get('id') == 0:
            error_msg = "❌ Foydalanuvchi ma'lumotlari yaratilmadi. Qaytadan urinib ko'ring." if user_lang == "uz" else "❌ Не удалось создать данные пользователя. Попробуйте еще раз."
            if hasattr(callback_or_message, 'message'):
                # It's a CallbackQuery
                await callback_or_message.message.answer(error_msg)
            else:
                # It's a Message
                await callback_or_message.answer(error_msg)
            await state.clear()
            return
            
        user = dict(ensured)
        
        # Validatsiya: user_id bo'lishi shart
        user_id = user.get('id')
        if not user_id or user_id == 0:
            error_msg = "❌ Foydalanuvchi ma'lumotlari topilmadi. Qaytadan urinib ko'ring." if user_lang == "uz" else "❌ Данные пользователя не найдены. Попробуйте еще раз."
            if hasattr(callback_or_message, 'message'):
                await callback_or_message.message.answer(error_msg)
            else:
                await callback_or_message.answer(error_msg)
            await state.clear()
            return
        
        order_data = {
            'user_id': user_id,
            'category': map_category_key_to_db_value(data.get('selected_category'), user_lang),
            'service_type': map_service_key_to_db_value(data.get('selected_service_type'), user_lang),
            'address': data.get('address'),
            'longitude': data.get('longitude'),
            'latitude': data.get('latitude'),
            'is_active': True
        }
        
        try:
            order_id = await create_smart_service_order(order_data)
        except ValueError as e:
            error_msg = "❌ Xatolik: Foydalanuvchi ma'lumotlari to'liq emas." if user_lang == "uz" else "❌ Ошибка: Данные пользователя неполные."
            if hasattr(callback_or_message, 'message'):
                await callback_or_message.message.answer(error_msg)
            else:
                await callback_or_message.answer(error_msg)
            await state.clear()
            return

        if order_id:
            conn = await asyncpg.connect(settings.DB_URL)
            try:
                app_number_result = await conn.fetchrow(
                    "SELECT application_number FROM smart_service_orders WHERE id = $1",
                    order_id
                )
                application_number = app_number_result['application_number'] if app_number_result else f"SMA-{order_id:04d}"
            finally:
                await conn.close()

            category_name = resolve_category_label(data.get('selected_category'), user_lang)
            service_name = resolve_service_label(data.get('selected_service_type'), user_lang)

            # Send group notification
            group_notification_sent = False
            if settings.ZAYAVKA_GROUP_ID:
                try:
                    location_text = ""
                    if data.get('latitude') and data.get('longitude'):
                        location_text = f"\n📍 <b>Lokatsiya:</b> <a href='https://maps.google.com/?q={data['latitude']},{data['longitude']}'>Google Maps</a>"

                    address_text = (data.get('address') or '')[:80]
                    if len(address_text) < len(data.get('address') or ''):
                        address_text += "..."

                    # Default values for f-string
                    default_name = "Noma'lum"
                    client_full_name = user.get('full_name') or callback_or_message.from_user.full_name or default_name
                    client_phone = user.get('phone', default_name)

                    group_msg = (
                        f"🛜 <b>YANGI SMARTSERVICE ARIZASI</b>\n"
                        f"{'='*30}\n"
                        f"🆔 <b>ID:</b> <code>{application_number}</code>\n"
                        f"👤 <b>Mijoz:</b> {client_full_name}\n"
                        f"📞 <b>Telefon:</b> {client_phone}\n"
                        f"📂 <b>Kategoriya:</b> {category_name}\n"
                        f"🔧 <b>Xizmat turi:</b> {service_name}\n"
                        f"📍 <b>Manzil:</b> {address_text}"
                        f"{location_text}\n"
                        f"🕐 <b>Vaqt:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                        f"{'='*30}"
                    )
                    
                    logger.info(f"Sending smart service group notification for order {application_number}")
                    await bot.send_message(
                        chat_id=settings.ZAYAVKA_GROUP_ID,
                        text=group_msg,
                        parse_mode='HTML'
                    )
                    group_notification_sent = True
                    logger.info(f"Smart service group notification sent successfully for order {application_number}")
                    
                except Exception as group_error:
                    logger.error(f"Smart service group notification error: {group_error}")
            else:
                logger.warning("ZAYAVKA_GROUP_ID not configured - skipping smart service group notification")
            
            if user_lang == "uz":
                success_text = (
                    f"✅ <b>Smart Service buyurtmasi muvaffaqiyatli yaratildi!</b>\n\n"
                    f"📋 <b>Buyurtma raqami:</b> {application_number}\n"
                    f"📂 <b>Kategoriya:</b> {category_name}\n"
                    f"🔧 <b>Xizmat turi:</b> {service_name}\n"
                    f"📍 <b>Manzil:</b> {data.get('address')}\n\n"
                    f"Tez orada mutaxassislarimiz siz bilan bog'lanishadi."
                )
            else:
                success_text = (
                    f"✅ <b>Заказ Smart Service успешно создан!</b>\n\n"
                    f"📋 <b>Номер заказа:</b> {application_number}\n"
                    f"📂 <b>Категория:</b> {category_name}\n"
                    f"🔧 <b>Тип услуги:</b> {service_name}\n"
                    f"📍 <b>Адрес:</b> {data.get('address')}\n\n"
                    f"В ближайшее время наши специалисты свяжутся с вами."
                )
            
            if hasattr(callback_or_message, 'message'):
                # It's a CallbackQuery
                await callback_or_message.message.edit_text(
                    success_text,
                    parse_mode='HTML'
                )
            else:
                # It's a Message
                await callback_or_message.edit_text(
                    success_text,
                    parse_mode='HTML'
                )
        else:
            # Use the user_lang that was already determined at the beginning of the function
            if user_lang == "uz":
                error_text = (
                    "❌ Buyurtmani saqlashda xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
                )
            else:
                error_text = (
                    "❌ Ошибка при сохранении заказа. Пожалуйста, попробуйте снова."
                )
            await message.answer(error_text)
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in finish_smart_service_order: {e}")
        try:
            data = await state.get_data()
            telegram_id = data.get('telegram_id')
            user_lang = data.get('user_lang') or await get_user_language(telegram_id)
        except:
            user_lang = "uz" 
        
        error_text = "❌ Xatolik yuz berdi." if user_lang == "uz" else "❌ Произошла ошибка."
        await message.answer(error_text)
        await state.clear()