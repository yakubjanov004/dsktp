from aiogram import Router

from handlers.admin import (
    export,
    language,
    orders,
    statistics,
    status,
    users,
    backup,
)

router = Router()

router.include_routers(
    export.router,
    language.router,
    orders.router,
    statistics.router,
    status.router,
    users.router,
    backup.router,
)
