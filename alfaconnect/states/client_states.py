from aiogram.fsm.state import State, StatesGroup

class ConnectionOrderStates(StatesGroup):
    """Connection order states for client"""
    selecting_region = State()
    selecting_connection_type = State()
    selecting_tariff = State()
    entering_address = State()
    asking_for_geo = State()
    waiting_for_geo = State()
    confirming_connection = State()

class ServiceOrderStates(StatesGroup):
    """Service order states for client"""
    selecting_region = State()
    selecting_abonent_type = State()
    waiting_for_contact = State()
    entering_description = State()
    entering_reason = State()
    entering_address = State()
    asking_for_media = State()
    waiting_for_media = State()
    asking_for_location = State()
    waiting_for_location = State()
    confirming_service = State()

class ProfileEditStates(StatesGroup):
    """Profile edit states for client"""
    waiting_for_new_name = State()

class SmartServiceStates(StatesGroup):
    """Smart service order states for client"""
    selecting_category = State()
    selecting_service_type = State()
    entering_address = State()
    asking_for_location = State()
    waiting_for_location = State()
    confirming_order = State()

class RatingStates(StatesGroup):
    """Rating states for client"""
    waiting_for_comment = State()