from aiogram import Router

from . import (
    inbox,
    client_search,
    connection_order,
    language,
    orders,
    statistics,
)

router = Router()

router.include_routers(
    inbox.router,
    client_search.router,
    connection_order.router,
    language.router,
    orders.router,
    statistics.router,
)
