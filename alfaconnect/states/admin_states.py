from aiogram.fsm.state import StatesGroup, State

class UserRoleChange(StatesGroup):
    waiting_for_search_method = State()
    waiting_for_telegram_id = State()
    waiting_for_phone = State()
    waiting_for_new_role = State()


class UsersPagination(StatesGroup):
    """Foydalanuvchilar paginatsiyasi uchun holatlar"""
    viewing_all_users = State()  # Barcha foydalanuvchilarni ko'rish
    viewing_staff_users = State()  # Xodimlarni ko'rish
    viewing_user_details = State()  # Foydalanuvchi tafsilotlarini ko'rish


class ApplicationsStates(StatesGroup):
    """Zayavkalar tizimi uchun holatlar"""
    main_menu = State()  # Asosiy zayavkalar menusi
    dashboard = State()  # Umumiy dashboard
    
    # Ulanish zayavkalari
    connection_orders = State()  # Ulanish zayavkalari bo'limi
    connection_list = State()  # Ulanish zayavkalari ro'yxati
    connection_search = State()  # Ulanish zayavkalarida qidiruv
    connection_filter = State()  # Ulanish zayavkalarini filterlash
    connection_details = State()  # Ulanish zayavkasi tafsilotlari
    
    # Texnik zayavkalar
    technician_orders = State()  # Texnik zayavkalar bo'limi
    technician_list = State()  # Texnik zayavkalar ro'yxati
    technician_search = State()  # Texnik zayavkalarda qidiruv
    technician_filter = State()  # Texnik zayavkalarni filterlash
    technician_details = State()  # Texnik zayavka tafsilotlari
    
    # Xodim zayavkalari
    staff_orders = State()  # Xodim zayavkalari bo'limi
    staff_list = State()  # Xodim zayavkalari ro'yxati
    staff_search = State()  # Xodim zayavkalarida qidiruv
    staff_filter = State()  # Xodim zayavkalarni filterlash
    staff_details = State()  # Xodim zayavkasi tafsilotlari
    
    # Umumiy holatlar
    waiting_for_search_query = State()  # Qidiruv so'rovi kutilmoqda
    waiting_for_filter_selection = State()  # Filter tanlash kutilmoqda
