from aiogram import Router

from . import (
    client_search,
    connection_order_cc,
    inbox,
    language,
    statistics,
    technician_order_cc,
    webapp,
)

router = Router()

router.include_routers(
    client_search.router,
    connection_order_cc.router,
    inbox.router,
    language.router,
    statistics.router,
    technician_order_cc.router,
    webapp.router,
)
