from aiogram import Router

from . import (
    inbox,
    reports,
    language,
)

router = Router()

router.include_routers(
    inbox.router,
    reports.router,
    language.router,
)
