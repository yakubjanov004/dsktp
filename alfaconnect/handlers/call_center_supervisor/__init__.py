from aiogram import Router

from . import (
    connection_order_ccs,
    export,
    inbox,
    language,
    orders,
    staff_activity,
    statistics,
    technicial_order_ccs,
)

router = Router()

router.include_routers(
    connection_order_ccs.router,
    export.router,
    inbox.router,
    language.router,
    orders.router,
    staff_activity.router,
    statistics.router,
    technicial_order_ccs.router,
)
