# states/controller_states.py
from aiogram.fsm.state import StatesGroup, State

class ControllerConnectionOrderStates(StatesGroup):
    """
    Controller -> 'connection' arizasi oqimi:
    phone -> region -> conn_type -> tariff -> address -> confirm
    """
    waiting_client_phone = State()
    selecting_region = State()
    selecting_connection_type = State()
    selecting_tariff = State()
    entering_address = State()
    confirming_connection = State()


class ControllerTechnicianOrderStates(StatesGroup):
    """
    Controller -> 'technician' (texnik xizmat) arizasi oqimi:
    phone -> region -> description -> address -> confirm
    """
    waiting_client_phone = State()
    selecting_region = State()
    description= State()
    entering_address = State()
    confirming_connection = State()
