from aiogram import Router

from . import (
    export,
    inbox,
    inventory,
    orders,
    language,
    statistics,
    technician_to_give_maerial,
    technician_material_balance,
    technician_used_materials,
)

router = Router()

router.include_routers(
    export.router,
    inbox.router,
    inventory.router,
    orders.router,
    language.router,
    statistics.router,
    technician_to_give_maerial.router,
    technician_material_balance.router,
    technician_used_materials.router,
)
