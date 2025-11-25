# states/technician_states.py
from aiogram.fsm.state import State, StatesGroup

class QtyStates(StatesGroup):
    waiting_qty = State()

class CustomQtyStates(StatesGroup):
    waiting_qty = State()

class DiagStates(StatesGroup):
    waiting_text = State()

class CancellationStates(StatesGroup):
    waiting_note = State()

class SourceTypeStates(StatesGroup):
    waiting_source_type = State()
