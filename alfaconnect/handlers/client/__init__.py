from aiogram import Router

from . import (
    bot_guide,
    connection_order,
    contact,
    language,
    profile,
    service_order,
    smart_service,
)

router = Router()

router.include_routers(
    bot_guide.router,
    connection_order.router,
    contact.router,
    language.router,
    profile.router,
    service_order.router,
    smart_service.router,
)