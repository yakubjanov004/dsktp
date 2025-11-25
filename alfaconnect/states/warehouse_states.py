from aiogram.fsm.state import State, StatesGroup

class WarehouseStates(StatesGroup):
    inventory_menu = State()

class AddMaterialStates(StatesGroup):
    name = State()
    quantity = State()
    price = State()
    description = State()
    material_unit = State()

class UpdateMaterialStates(StatesGroup):
    search = State()
    select = State()
    quantity = State()  # Yangi state - faqat miqdor uchun
    name = State()
    description = State()

class TechnicianMaterialStates(StatesGroup):
    select_technician = State()
    select_material = State()
    enter_quantity = State()

class StatsStates(StatesGroup):
    waiting_range = State()

class MaterialRequestsStates(StatesGroup):
    """Material requests uchun holatlar"""
    main_menu = State()  # Material requests asosiy menusi
    connection_orders = State()  # Ulanish arizalari materiallari
    technician_orders = State()  # Texnik xizmat materiallari
    staff_orders = State()  # Xodim arizalari materiallari