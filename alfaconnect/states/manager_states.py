from aiogram.fsm.state import State, StatesGroup

class staffConnectionOrderStates(StatesGroup):
    waiting_client_phone = State()
    selecting_region = State()
    selecting_connection_type = State()
    selecting_tariff = State()
    entering_address = State()
    confirming_connection = State()

class staffTechnicianOrderStates(StatesGroup):
    selecting_technician = State()
    description= State()
    waiting_client_phone = State()
    selecting_region = State()
    entering_address = State()
    confirming_connection = State()

class ManagerExportStates(StatesGroup):
    selecting_export_type = State()
    selecting_export_format = State()
