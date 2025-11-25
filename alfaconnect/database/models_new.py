from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum, auto
from typing import ClassVar
from dataclasses import field

# ==================== ENUM LAR ====================
# PostgreSQL ENUM lariga mos keladigan Python Enumlari
# Bu enumlar ma'lumotlar bazasidagi ENUM tiplariga mos keladi

class ConnectionOrderStatus(Enum):
    """
    Ulanish arizalari (connection_orders) uchun statuslar
    """
    IN_MANAGER = "in_manager"                    # Managerga tayinlangan
    IN_JUNIOR_MANAGER = "in_junior_manager"      # Kichik managerga tayinlangan
    IN_CONTROLLER = "in_controller"              # Kontrollerga tayinlangan
    IN_TECHNICIAN = "in_technician"              # Texnikaga tayinlangan
    IN_REPAIRS = "in_repairs"                    # Ta'mirlashda
    IN_WAREHOUSE = "in_warehouse"                # Omborga tayinlangan
    IN_TECHNICIAN_WORK = "in_technician_work"    # Texnik ish bajarayapti
    COMPLETED = "completed"                      # Yakunlangan
    BETWEEN_CONTROLLER_TECHNICIAN = "between_controller_technician"  # Kontroller va texnik o'rtasida
    CANCELLED = "cancelled"                       # Bekor qilingan

class SmartServiceCategory(Enum):
    """
    Smart Service buyurtmalarining kategoriyalari
    Har bir kategoriya turli xil texnologik yechimlarni ifodalaydi
    """
    AQLLI_AVTOMATLASHTIRILGAN_XIZMATLAR = "aqlli_avtomatlashtirilgan_xizmatlar"  # Aqlli uy, aqlli ofis
    XAVFSIZLIK_KUZATUV_TIZIMLARI = "xavfsizlik_kuzatuv_tizimlari"                # Kamera, signalizatsiya
    INTERNET_TARMOQ_XIZMATLARI = "internet_tarmoq_xizmatlari"                   # Wi-Fi, LAN, repeater
    ENERGIYA_YASHIL_TEXNOLOGIYALAR = "energiya_yashil_texnologiyalar"            # Quyosh panel, energiya tejovchi
    MULTIMEDIYA_ALOQA_TIZIMLARI = "multimediya_aloqa_tizimlari"                 # TV, audio, video konferensiya
    MAXSUS_QOSHIMCHA_XIZMATLAR = "maxsus_qoshimcha_xizmatlar"                   # IoT, AI, maxsus yechimlar


class BusinessType(Enum):
    """
    Business types for orders (B2B - Business to Business, B2C - Business to Consumer)
    """
    B2B = "B2B"
    B2C = "B2C"


class OrderBase:
    """Base class for all order types with common fields"""
    _counters: ClassVar[dict] = {}  # Separate counter for each prefix
    _prefix: ClassVar[str] = ""  # Should be overridden by subclasses
    
    @classmethod
    def generate_application_number(cls, business_type: BusinessType) -> str:
        """Generate application number in format: PREFIX-BUSINESS_TYPE-NUMBER"""
        if cls._prefix not in cls._counters:
            cls._counters[cls._prefix] = 0
        cls._counters[cls._prefix] += 1
        return f"{cls._prefix}-{business_type.value}-{cls._counters[cls._prefix]}"

class TechnicianOrderStatus(Enum):
    """
    Texnik buyurtmalari (technician_orders) uchun statuslar
    Texnik xizmat ko'rsatish jarayonining bosqichlarini ifodalaydi
    """
    IN_CONTROLLER = "in_controller"              # Kontrollerga tayinlangan
    IN_TECHNICIAN = "in_technician"              # Texnikaga tayinlangan
    IN_DIAGNOSTICS = "in_diagnostics"            # Diagnostikada
    IN_REPAIRS = "in_repairs"                    # Ta'mirlashda
    IN_WAREHOUSE = "in_warehouse"                # Omborga tayinlangan
    IN_TECHNICIAN_WORK = "in_technician_work"    # Texnik ish bajarayapti
    COMPLETED = "completed"                      # Yakunlangan
    BETWEEN_CONTROLLER_TECHNICIAN = "between_controller_technician"  # Kontroller va texnik o'rtasida
    IN_CALL_CENTER_SUPERVISOR = "in_call_center_supervisor"         # Call center nazoratchisiga tayinlangan
    IN_CALL_CENTER_OPERATOR = "in_call_center_operator"             # Call center operatoriga tayinlangan
    CANCELLED = "cancelled"                       # Bekor qilingan

class StaffOrderStatus(Enum):
    """
    staff buyurtmalari uchun statuslar
    Turli foydalanuvchilar tomonidan yaratilgan va ko'rib chiqiladigan buyurtmalar
    """
    # Yaratish bosqichlari
    NEW = "new"                                  # Yangi ariza
    IN_CALL_CENTER_OPERATOR = "in_call_center_operator"      # Call center operatoriga tayinlangan
    IN_CALL_CENTER_SUPERVISOR = "in_call_center_supervisor"  # Call center nazoratchisiga tayinlangan
    
    # Ko'rib chiqish va tasdiqlash bosqichlari
    IN_MANAGER = "in_manager"                    # Managerga tayinlangan
    IN_JUNIOR_MANAGER = "in_junior_manager"      # Kichik managerga tayinlangan
    IN_CONTROLLER = "in_controller"              # Kontrollerga tayinlangan
    
    # Bajarish bosqichlari
    IN_TECHNICIAN = "in_technician"              # Texnikaga tayinlangan
    IN_DIAGNOSTICS = "in_diagnostics"            # Diagnostikada
    IN_REPAIRS = "in_repairs"                    # Ta'mirlashda
    IN_WAREHOUSE = "in_warehouse"                # Omborga tayinlangan
    IN_TECHNICIAN_WORK = "in_technician_work"    # Texnik ish bajarayapti
    
    # Qo'shimcha statuslar
    IN_PROGRESS = "in_progress"                  # Jarayonda
    ASSIGNED_TO_TECHNICIAN = "assigned_to_technician"  # Texnikaga tayinlangan
    
    # Yakunlash
    COMPLETED = "completed"                      # Yakunlangan
    CANCELLED = "cancelled"                      # Bekor qilingan
    BETWEEN_CONTROLLER_TECHNICIAN = "between_controller_technician"  # Kontroller va texnik o'rtasida

class StaffOrderTypeOfZayavka(Enum):
    """
    Staff buyurtmalarining ariza turlari
    Call center orqali kelgan so'rovlarning turini aniqlaydi
    """
    CONNECTION = "connection"    # Internet ulanish arizasi
    TECHNICIAN = "technician"    # Texnik xizmat arizasi


class UserRole(Enum):
    """
    Foydalanuvchi rollari - tizimdagi foydalanuvchilarning vazifalarini aniqlaydi
    Har bir rol tizimda ma'lum huquqlar va mas'uliyatlarga ega
    """
    ADMIN = "admin"                          # Administrator 
    CLIENT = "client"                        # Mijoz  
    MANAGER = "manager"                      # Manager 
    JUNIOR_MANAGER = "junior_manager"        # Kichik manager 
    CONTROLLER = "controller"                # Kontroller 
    TECHNICIAN = "technician"                # Texnik 
    WAREHOUSE = "warehouse"                  # Omborchi 
    CALLCENTER_SUPERVISOR = "callcenter_supervisor"  # Call center nazoratchisi
    CALLCENTER_OPERATOR = "callcenter_operator"      # Call center operatori

# ==================== DOMAIN VALIDATSIYA ====================
# Smart Service Type DOMAIN uchun to'liq 42 ta validatsiya
# Bu ro'yxat PostgreSQL bazasidagi smart_service_type DOMAIN qiymatlari bilan mos keladi
SMART_SERVICE_TYPES = [
    'aqlli_uy_tizimlarini_ornatish_sozlash',                                    # Aqlli uy tizimlari o'rnatish
    'aqlli_yoritish_smart_lighting_tizimlari',                                  # Aqlli yoritish tizimlari
    'aqlli_termostat_iqlim_nazarati_tizimlari',                                 # Aqlli termostat tizimlari
    'smart_lock_internet_orqali_boshqariladigan_eshik_qulfi_tizimlari',         # Smart lock tizimlari
    'aqlli_rozetalar_energiya_monitoring_tizimlari',                            # Aqlli rozetka tizimlari
    'uyni_masofadan_boshqarish_qurilmalari_yagona_uzim_orqali_boshqarish',      # Masofaviy boshqarish
    'aqlli_pardalari_jaluz_tizimlari',                                          # Aqlli parda/jaluz tizimlari
    'aqlli_malahiy_texnika_integratsiyasi',                                     # Aqlli maishiy texnika
    'videokuzatuv_kameralarini_ornatish_ip_va_analog',                          # Video kuzatuv kameralari
    'kamera_arxiv_tizimlari_bulutli_saqlash_xizmatlari',                        # Kamera arxiv tizimlari
    'domofon_tizimlari_ornatish',                                               # Domofon tizimlari
    'xavfsizlik_signalizatsiyasi_harakat_sensorlarini_ornatish',                # Xavfsizlik signalizatsiyasi
    'yong_signalizatsiyasi_tizimlari',                                          # Yong'in signalizatsiyasi
    'gaz_sizish_sav_toshqinliqqa_qarshi_tizimlar',                              # Gaz/o't o'tkazmaydigan tizimlar
    'yuzni_tanish_face_recognition_tizimlari',                                  # Yuzni tanish tizimlari
    'avtomatik_eshik_darvoza_boshqaruv_tizimlari',                              # Avtomatik eshik tizimlari
    'wi_fi_tarmoqlarini_ornatish_sozlash',                                      # Wi-Fi tarmoq o'rnatish
    'wi_fi_qamrov_zonasini_kengaytirish_access_point',                          # Wi-Fi qamrov kengaytirish
    'mobil_aloqa_signalini_kuchaytirish_repeater',                              # Signal kuchaytirish
    'ofis_va_uy_uchun_lokal_tarmoq_lan_qurish',                                 # LAN tarmoq qurish
    'internet_provayder_xizmatlarini_ulash',                                    # Internet provayder xizmatlari
    'server_va_nas_qurilmalarini_ornatish',                                     # Server/NAS qurilmalari
    'bulutli_fayl_almashish_zaxira_tizimlari',                                  # Bulutli fayl almashish
    'vpn_va_xavfsiz_internet_ulanishlarini_tashkil_qilish',                     # VPN tashkil qilish
    'quyosh_panellarini_ornatish_ulash',                                        # Quyosh panel o'rnatish
    'quyosh_batareyalari_orqali_energiya_saqlash_tizimlari',                    # Quyosh batareya tizimlari
    'shamol_generatorlarini_ornatish',                                          # Shamol generatorlari
    'elektr_energiyasini_tejovchi_yoritish_tizimlari',                          # Energiya tejovchi yoritish
    'avtomatik_suv_orish_tizimlari_smart_irrigation',                           # Smart sug'orish tizimlari
    'smart_tv_ornatish_ulash',                                                  # Smart TV o'rnatish
    'uy_kinoteatri_tizimlari_ornatish',                                         # Uy kinoteatri tizimlari
    'audio_tizimlar_multiroom',                                                 # Multiroom audio tizimlari
    'ip_telefoniya_mini_ats_tizimlarini_tashkil_qilish',                        # IP telefoniya tizimlari
    'video_konferensiya_tizimlari',                                             # Video konferensiya tizimlari
    'interaktiv_taqdimot_tizimlari_proyektor_led_ekran',                        # Interaktiv taqdimot tizimlari
    'aqlli_ofis_tizimlarini_ornatish',                                          # Aqlli ofis tizimlari
    'data_markaz_server_room_loyihalash_montaj_qilish',                         # Data markaz loyihalash
    'qurilma_tizimlar_uchun_texnik_xizmat_korsatish',                           # Qurilma texnik xizmati
    'dasturiy_taminotni_ornatish_yangilash',                                    # Dasturiy ta'minot o'rnatish
    'iot_internet_of_things_qurilmalarini_integratsiya_qilish',                 # IoT qurilmalarni integratsiya
    'qurilmalarni_masofadan_boshqarish_tizimlarini_sozlash',                    # Masofaviy boshqarish tizimlari
    'suniy_intellekt_asosidagi_uy_ofis_boshqaruv_tizimlari'                     # AI boshqaruv tizimlari
]

def validate_smart_service_type(value: str) -> bool:
    """
    Smart service type qiymatini validatsiya qilish
    Qiymat ro'yxatda mavjudligini tekshiradi
    
    Args:
        value (str): Tekshiriladigan service type qiymati
        
    Returns:
        bool: Qiymat ro'yxatda mavjud bo'lsa True, aks holda False
    """
    return value in SMART_SERVICE_TYPES

# ==================== ASOSIY MODELLAR ====================
@dataclass
class BaseModel:
    """
    Barcha ma'lumotlar bazasi modellarining asosiy klassi
    Umumiy maydonlarni o'z ichiga oladi
    """
    id: Optional[int] = field(default=None)                    # Jadval yozuvi IDsi (PRIMARY KEY)
    created_at: Optional[datetime] = field(default=None)       # Yozuv yaratilgan vaqt
    updated_at: Optional[datetime] = field(default=None)       # Yozuv oxirgi marta yangilangan vaqt

@dataclass
class Users(BaseModel):
    """
    Foydalanuvchilar jadvali modeli
    Tizim foydalanuvchilari haqida ma'lumot saqlaydi
    """
    telegram_id: Optional[int] = None           # Telegram foydalanuvchi IDsi (UNIQUE)
    full_name: Optional[str] = None             # Foydalanuvchi to'liq ismi
    username: Optional[str] = None              # Telegram username
    phone: Optional[str] = None                 # Telefon raqami
    language: str = "uz"                        # Til sozlamasi (default: uz)
    region: Optional[str] = None                # Hudud kodi (masalan: 'tashkent_city', 'samarkand')
    address: Optional[str] = None               # Manzil
    role: Optional[UserRole] = None             # Foydalanuvchi roli (ENUM)
    abonent_id: Optional[str] = None            # Abonent identifikatori
    is_blocked: bool = False                    # Foydalanuvchi bloklanganmi?
    
    # Region validation
    _valid_regions = {
        'tashkent_city', 'tashkent_region', 'andijon', 'fergana', 
        'namangan', 'sirdaryo', 'jizzax', 'samarkand', 'bukhara', 
        'navoi', 'kashkadarya', 'surkhandarya', 'khorezm', 'karakalpakstan'
    }
    
    def __post_init__(self):
        if self.region and self.region not in self._valid_regions:
            raise ValueError(f"Invalid region. Must be one of: {', '.join(sorted(self._valid_regions))}")
            
    @property
    def region_display_name(self, lang: str = 'uz') -> Optional[str]:
        """Get the display name of the region in the specified language"""
        if not self.region:
            return None
            
        # Map of region codes to their display names in different languages
        display_names = {
            'tashkent_city': {'uz': 'Toshkent shahri', 'ru': 'г. Ташкент'},
            'tashkent_region': {'uz': 'Toshkent viloyati', 'ru': 'Ташкентская область'},
            'andijon': {'uz': 'Andijon', 'ru': 'Андижан'},
            'fergana': {'uz': 'Farg\'ona', 'ru': 'Фергана'},
            'namangan': {'uz': 'Namangan', 'ru': 'Наманган'},
            'sirdaryo': {'uz': 'Sirdaryo', 'ru': 'Сырдарья'},
            'jizzax': {'uz': 'Jizzax', 'ru': 'Джизак'},
            'samarkand': {'uz': 'Samarqand', 'ru': 'Самарканд'},
            'bukhara': {'uz': 'Buxoro', 'ru': 'Бухара'},
            'navoi': {'uz': 'Navoiy', 'ru': 'Навои'},
            'kashkadarya': {'uz': 'Qashqadaryo', 'ru': 'Кашкадарья'},
            'surkhandarya': {'uz': 'Surxondaryo', 'ru': 'Сурхандарья'},
            'khorezm': {'uz': 'Xorazm', 'ru': 'Хорезм'},
            'karakalpakstan': {'uz': 'Qoraqalpog\'iston', 'ru': 'Каракалпакстан'},
        }
        
        # Default to Uzbek if language not found
        return display_names.get(self.region, {}).get(lang, display_names.get(self.region, {}).get('uz'))

@dataclass
class Tarif(BaseModel):
    """
    Internet tariflari jadvali modeli
    Mavjud tarif rejalari haqida ma'lumot saqlaydi
    """
    name: Optional[str] = None                  # Tarif nomi
    picture: Optional[str] = None               # Tarif rasmi (fayl yo'li)

@dataclass
class ConnectionOrders(BaseModel, OrderBase):
    """Internet ulanish arizalari jadvali modeli
    Yangi ulanish so'rovlari haqida ma'lumot saqlaydi
    """
    _prefix: ClassVar[str] = "CONN"  # Prefix for connection orders
    application_number: Optional[str] = None  # Format: CONN-B2C-1001
    """
    Internet ulanish arizalari jadvali modeli
    Yangi ulanish so'rovlari haqida ma'lumot saqlaydi
    """
    user_id: Optional[int] = None               # Foydalanuvchi IDsi (FK users.id)
    region: Optional[str] = None                # Hudud nomi
    address: Optional[str] = None               # To'liq manzil
    tarif_id: Optional[int] = None              # Tanlangan tarif IDsi (FK tarif.id)
    business_type: BusinessType = BusinessType.B2C  # Business type (B2B/B2C)
    longitude: Optional[float] = None           # Uzunlik (GPS koordinata)
    latitude: Optional[float] = None            # Kenglik (GPS koordinata)
    jm_notes: Optional[str] = None              # Junior manager izohlari
    cancellation_note: Optional[str] = None     # Bekor qilish sababi
    is_active: bool = True                      # Ariza faolmi?
    status: ConnectionOrderStatus = ConnectionOrderStatus.IN_MANAGER  # Ariza statusi

@dataclass
class TechnicianOrders(BaseModel, OrderBase):
    """Texnik xizmat buyurtmalari jadvali modeli
    Texnik xizmat so'rovlari haqida ma'lumot saqlaydi
    """
    _prefix: ClassVar[str] = "TECH"  # Prefix for technician orders
    application_number: Optional[str] = None  # Format: TECH-B2C-1001
    """
    Texnik xizmat buyurtmalari jadvali modeli
    Texnik xizmat so'rovlari haqida ma'lumot saqlaydi
    Migration 034 da diagnostics maydoni olib tashlangan
    """
    user_id: Optional[int] = None               # Foydalanuvchi IDsi (FK users.id)
    region: Optional[str] = None                # Hudud IDsi
    abonent_id: Optional[str] = None            # Abonent identifikatori
    address: Optional[str] = None               # Manzil
    media: Optional[str] = None                 # Media fayllar (rasm/video yo'li)
    business_type: BusinessType = BusinessType.B2C  # Business type (B2B/B2C)
    longitude: Optional[float] = None           # Uzunlik (GPS koordinata)
    latitude: Optional[float] = None            # Kenglik (GPS koordinata)
    description: Optional[str] = None           # mijoz tavsifi
    description_ish: Optional[str] = None       # Bajarilgan ish tavsifi
    description_operator: Optional[str] = None  # Operator izohlari
    cancellation_note: Optional[str] = None      # Bekor qilish sababi
    status: TechnicianOrderStatus = TechnicianOrderStatus.IN_CONTROLLER  # Buyurtma statusi
    is_active: bool = True                      # Buyurtma faolmi?

@dataclass
class StaffOrders(BaseModel, OrderBase):
    """Staff (Call Center) buyurtmalari jadvali modeli
    Turli foydalanuvchilar tomonidan yaratilgan so'rovlarni saqlaydi
    """
    _prefix: ClassVar[str] = "STAFF"  # Prefix for staff orders
    application_number: Optional[str] = None  # Format: STAFF-B2B-1001
    """
    Staff (Call Center) buyurtmalari jadvali modeli
    Turli foydalanuvchilar tomonidan yaratilgan so'rovlarni saqlaydi
    """
    user_id: Optional[int] = None               # Foydalanuvchi IDsi (FK users.id) - Yaratuvchi
    phone: Optional[str] = None                 # Telefon raqami
    region: Optional[str] = None                # Hudud nomi
    abonent_id: Optional[str] = None            # Abonent identifikatori
    tarif_id: Optional[int] = None              # Tarif IDsi (FK tarif.id) - Faqat ulanish uchun
    address: Optional[str] = None               # Manzil
    description: Optional[str] = None           # Umumiy tavsif
    problem_description: Optional[str] = None   # Muammo haqida batafsil (texnik xizmat uchun)
    diagnostics: Optional[str] = None           # Diagnostika natijalari (texnik xizmat uchun)
    business_type: BusinessType = BusinessType.B2C  # Business type (B2B/B2C)
    status: StaffOrderStatus = StaffOrderStatus.NEW  # Boshlang'ich status
    type_of_zayavka: StaffOrderTypeOfZayavka = StaffOrderTypeOfZayavka.CONNECTION  # Ariza turi
    is_active: bool = True                      # Ariza faolmi?
    created_by_role: Optional[UserRole] = None  # Kim tomonidan yaratilgani (qo'shimcha)
    
    def __post_init__(self):
        """Ariza turiga qarab maydonlarni sozlash"""
        if self.type_of_zayavka == StaffOrderTypeOfZayavka.TECHNICIAN:
            # Texnik xizmat uchun kerakli maydonlar
            if not self.problem_description:
                self.problem_description = ""

@dataclass
class SmartServiceOrders(BaseModel):
    """
    Smart Service buyurtmalari jadvali modeli
    Aqlli texnologiyalar bo'yicha so'rovlarni saqlaydi
    """
    application_number: Optional[str] = None    # Format: SMA-0001
    user_id: Optional[int] = None               # Foydalanuvchi IDsi (FK users.id)
    category: SmartServiceCategory = None       # Xizmat kategoriyasi (ENUM)
    service_type: str = None                    # Xizmat turi (DOMAIN qiymat)
    address: str = ""                           # Manzil
    longitude: Optional[float] = None           # Uzunlik (GPS koordinata)
    latitude: Optional[float] = None            # Kenglik (GPS koordinata)
    is_active: bool = True                      # Buyurtma faolmi?

    def __post_init__(self):
        """
        Smart service type qiymatini validatsiya qilish
        Qiymat ro'yxatda mavjudligini tekshiradi
        """
        if self.service_type and not validate_smart_service_type(self.service_type):
            raise ValueError(f"Invalid smart service type: {self.service_type}")

@dataclass
class Connections(BaseModel):
    """
    Buyurtmalarni bog'lash jadvali modeli
    Har xil turdagi buyurtmalarni foydalanuvchilar bilan bog'laydi
    application_number orqali bog'langan
    """
    sender_id: Optional[int] = None             # Yuboruvchi foydalanuvchi IDsi (FK users.id)
    recipient_id: Optional[int] = None          # Qabul qiluvchi foydalanuvchi IDsi (FK users.id)
    application_number: Optional[str] = None     # Arizalar uchun asosiy identifikator (CONN-B2C-0001, TECH-B2C-0001, STAFF-B2C-0001)
    sender_status: Optional[str] = None          # Yuboruvchi statusi
    recipient_status: Optional[str] = None       # Qabul qiluvchi statusi

@dataclass
class Materials(BaseModel):
    """
    Materiallar jadvali modeli
    Omborda mavjud materiallar haqida ma'lumot saqlaydi
    """
    name: Optional[str] = None                  # Material nomi
    price: Optional[float] = None               # Narxi (so'mda)
    description: Optional[str] = None           # Tavsif
    quantity: int = 0                           # Miqdori
    serial_number: Optional[str] = None         # Seriya raqami (UNIQUE)
    material_unit: str = "dona"                 # O'lchov birligi (dona, metr, litr, kg)

@dataclass
class MaterialRequests(BaseModel):
    """
    Material so'rovlari jadvali modeli
    Texniklar tomonidan material so'rovlari haqida ma'lumot saqlaydi
    application_number orqali bog'langan
    """
    user_id: Optional[int] = None               # Foydalanuvchi IDsi (FK users.id)
    material_id: Optional[int] = None           # Material IDsi (FK materials.id)
    quantity: int = 1                           # So'ralgan miqdor
    price: float = 0.0                          # Birlik narxi
    total_price: float = 0.0                    # Umumiy narx
    source_type: str = "warehouse"              # Manba turi (warehouse, technician_stock)
    warehouse_approved: bool = False            # Ombor tomonidan tasdiqlanganmi?
    application_number: Optional[str] = None    # Ariza raqami - Format: CONN-B2C-0001, TECH-B2C-0001, STAFF-B2C-0001

@dataclass
class MaterialAndTechnician(BaseModel):
    """
    Texnik va materiallar bog'lanishi jadvali modeli
    Har bir texnik qaysi materiallardan foydalanganini kuzatib boradi
    application_number orqali request_type aniqlanadi (CONN-, TECH-, STAFF- prefikslari)
    """
    user_id: Optional[int] = None               # Texnik foydalanuvchi IDsi (FK users.id)
    material_id: Optional[int] = None           # Material IDsi (FK materials.id)
    quantity: Optional[int] = None              # Foydalangan miqdor
    application_number: Optional[str] = None     # Ariza raqami - Format: CONN-B2C-0001, TECH-B2C-0001, STAFF-B2C-0001
    issued_by: Optional[int] = None              # Kim tomonidan berilgan (FK users.id) - bir vaqtda issued_at bilan yoziladi
    issued_at: Optional[datetime] = None         # Qachon berilgan - bir vaqtda issued_by bilan yoziladi
    material_name: Optional[str] = None         # Material nomi
    material_unit: str = "dona"                  # O'lchov birligi (default: 'dona')
    price: float = 0.0                           # Birlik narxi (numeric(10,2), default: 0.0)
    total_price: float = 0.0                     # Umumiy narx (numeric(10,2), default: 0.0)


@dataclass
class MaterialIssued(BaseModel):
    """Ishlatilgan materiallar jadvali modeli
    Har bir arizaga qo'shilgan materiallar haqida to'liq ma'lumot saqlaydi
    """
    # Asosiy ma'lumotlar
    material_id: int                           # Material IDsi (FK materials.id)
    quantity: int                              # Miqdori
    price: float                              # Birlik narxi
    total_price: float                        # Umumiy summa (quantity * price)
    
    # Kim tomonidan berilgani
    issued_by: int                            # Kim tomonidan berilgan (FK users.id)
    issued_at: datetime = field(default_factory=datetime.now)  # Qachon berilgan
    
    # Material haqida ma'lumot (avtomatik to'ldiriladi)
    material_name: Optional[str] = None        # Material nomi
    material_unit: Optional[str] = None        # O'lchov birligi (dona, metr, litr, kg)
    
    # Qo'shimcha ma'lumotlar (database dan kelgan)
    application_number: Optional[str] = None   # Ariza raqami
    request_type: str = "connection"          # So'rov turi (connection, technician, staff)

@dataclass
class Reports(BaseModel):
    """
    Hisobotlar jadvali modeli
    Managerlar tomonidan yaratilgan hisobotlarni saqlaydi
    """
    title: str = ""                             # Hisobot sarlavhasi
    description: Optional[str] = None           # Hisobot tavsifi
    created_by: Optional[int] = None            # Yaratuvchi foydalanuvchi IDsi (FK users.id)

@dataclass
class AktDocuments(BaseModel):
    """
    AKT hujjatlari jadvali modeli
    Bajarilgan ishlarning rasmiy hujjatlarini saqlaydi
    """
    request_id: Optional[int] = None            # So'rov IDsi
    request_type: Optional[str] = None          # So'rov turi ('connection', 'technician', 'staff')
    akt_number: str = ""                        # AKT raqami (AKT-{request_id}-{YYYYMMDD})
    file_path: str = ""                         # Fayl yo'li
    file_hash: str = ""                         # Fayl SHA256 hash
    sent_to_client_at: Optional[datetime] = None  # Mijozga yuborilgan vaqt
    application_number: str = ""                 # Ariza raqami (NOT NULL) - Format: CONN-B2C-0001, TECH-B2C-0001, STAFF-B2C-0001

    def __post_init__(self):
        """
        So'rov turi qiymatini validatsiya qilish
        Qiymat ruxsat etilganlar ro'yxatida bo'lishi kerak
        """
        if self.request_type and self.request_type not in ['connection', 'technician', 'staff']:
            raise ValueError("Invalid request type")

@dataclass
class AktRatings(BaseModel):
    """
    AKT reytinglari jadvali modeli
    Mijozlarning bajarilgan ishlarga bergan reytinglarini saqlaydi
    """
    request_id: Optional[int] = None            # So'rov IDsi
    request_type: Optional[str] = None          # So'rov turi ('connection', 'technician', 'staff')
    rating: int = 0                             # Reyting (0-5)
    comment: Optional[str] = None               # Mijoz izohlari
    application_number: str = ""                # Ariza raqami (NOT NULL) - Format: CONN-B2C-0001, TECH-B2C-0001, STAFF-B2C-0001

    def __post_init__(self):
        """
        So'rov turi va reyting qiymatlarini validatsiya qilish
        """
        if self.request_type and self.request_type not in ['connection', 'technician', 'staff']:
            raise ValueError("Invalid request type")
        if not (0 <= self.rating <= 5):
            raise ValueError("Rating must be between 0 and 5")
        
def validate_request_type(value: str) -> bool:
    """
    So'rov turi qiymatini validatsiya qilish
    
    Args:
        value (str): Tekshiriladigan so'rov turi
        
    Returns:
        bool: Qiymat ruxsat etilganlar ro'yxatida bo'lsa True, aks holda False
    """
    return value in ['connection', 'technician', 'staff']

@dataclass
class MediaFiles(BaseModel):
    """
    Media fayllar uchun markazlashtirilgan model
    Barcha turdagi fayllarni saqlash uchun ishlatiladi
    """
    file_path: str = ""                          # "media/2024/01/orders/attachments/file.jpg"
    file_type: Optional[str] = None              # 'image', 'video', 'document', 'archive'
    file_size: Optional[int] = None              # bytes
    original_name: Optional[str] = None          # foydalanuvchi ko'radi
    mime_type: Optional[str] = None              # 'image/jpeg', 'application/pdf'
    category: Optional[str] = None               # 'order_attachment', 'akt', 'report', 'export'
    related_table: Optional[str] = None          # 'connection_orders', 'technician_orders'
    related_id: Optional[int] = None             # bog'langan yozuv ID
    uploaded_by: Optional[int] = None            # foydalanuvchi ID (FK users.id)
    is_active: bool = True                       # fayl faolmi?

# ==================== DATABASE KONFIGURATSIYA ====================
# Database konfiguratsiyasi - jadvallar va enumlar ro'yxati
DATABASE_CONFIG = {
    "tables": [
        "users", "tarif", "connection_orders", "technician_orders", 
        "staff_orders", "smart_service_orders", "connections", 
        "materials", "material_requests", "material_and_technician",
        "reports", "akt_documents", "akt_ratings", "media_files"  # Qo'shilgan
    ],
    "enums": {
        "connection_order_status": [status.value for status in ConnectionOrderStatus],
        "smart_service_category": [category.value for category in SmartServiceCategory],
        "technician_order_status": [status.value for status in TechnicianOrderStatus],
        "staff_order_status": [status.value for status in StaffOrderStatus],
        "staff_order_type_of_zayavka": [zayavka.value for zayavka in StaffOrderTypeOfZayavka],
        "type_of_zayavka": [zayavka.value for zayavka in StaffOrderTypeOfZayavka],
        "user_role": [role.value for role in UserRole]
}
}


# ==================== HELPER FUNKSIYALAR ====================
def get_table_name(model_class) -> str:
    """
    Model klass nomidan jadval nomini olish
    Klass nomini kichik harflarga o'girib qaytaradi
    
    Args:
        model_class: Model klassi
        
    Returns:
        str: Jadval nomi (masalan: Users -> users, Tarif -> tarif)
    """
    class_name = model_class.__name__
    if class_name.endswith('s'):
        return class_name.lower()
    return f"{class_name.lower()}s"

def validate_rating(value: int) -> bool:
    """
    Reyting qiymatini validatsiya qilish (0-5 oralig'i)
    
    Args:
        value (int): Tekshiriladigan reyting qiymati
        
    Returns:
        bool: Qiymat 0-5 oralig'ida bo'lsa True, aks holda False
    """
    return 0 <= value <= 5

def validate_request_type(value: str) -> bool:
    """
    So'rov turi qiymatini validatsiya qilish
    
    Args:
        value (str): Tekshiriladigan so'rov turi
        
    Returns:
        bool: Qiymat ruxsat etilganlar ro'yxatida bo'lsa True, aks holda False
    """
    return value in ['connection', 'technician', 'staff']

# ==================== DATABASE FUNCTIONS ====================
# PostgreSQL funksiyalari uchun Python wrapper'lar

def get_sequential_user_functions() -> dict:
    """
    Sequential user ID funksiyalari haqida ma'lumot
    
    Returns:
        dict: Funksiyalar haqida ma'lumot
    """
    return {
        "create_user_sequential": {
            "description": "Ketma-ket ID bilan foydalanuvchi yaratish",
            "parameters": {
                "p_telegram_id": "BIGINT - Telegram foydalanuvchi IDsi",
                "p_username": "TEXT - Username (ixtiyoriy)",
                "p_full_name": "TEXT - To'liq ism (ixtiyoriy)", 
                "p_phone": "TEXT - Telefon raqami (ixtiyoriy)",
                "p_role": "user_role - Foydalanuvchi roli (default: 'client')"
            },
            "returns": "TABLE with user data",
            "usage": "SELECT * FROM create_user_sequential($1, $2, $3, $4, $5)"
        },
        "get_next_sequential_user_id": {
            "description": "Keyingi ketma-ket user ID ni olish",
            "parameters": {},
            "returns": "INTEGER - Keyingi ID",
            "usage": "SELECT get_next_sequential_user_id()"
        },
        "reset_user_sequential_sequence": {
            "description": "Sequence ni mavjud ma'lumotlarga moslashtirish",
            "parameters": {},
            "returns": "VOID",
            "usage": "SELECT reset_user_sequential_sequence()"
        }
    }

def get_database_sequences() -> dict:
    """
    Database sequence'lari haqida ma'lumot
    
    Returns:
        dict: Sequence'lar haqida ma'lumot
    """
    return {
        "user_sequential_id_seq": {
            "description": "Foydalanuvchilar uchun ketma-ket ID generator",
            "start_value": 1,
            "purpose": "users jadvali uchun ketma-ket ID yaratish"
        }
    }