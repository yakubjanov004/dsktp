from aiogram.fsm.state import State, StatesGroup

class CallCenterSupervisorExportStates(StatesGroup):
    selecting_export_type = State()
    selecting_export_format = State()
    processing_export = State()