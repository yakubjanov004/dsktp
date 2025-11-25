from aiogram import Router

from . import (
    applications,
    connection_order,
    export,
    inbox,
    language,
    realtime_monitoring,
    smart_service_manager,
    staff_activity,
    technician_order,
)

router = Router()

router.include_routers(
    applications.router,
    connection_order.router,
    export.router,
    inbox.router,
    language.router,
    realtime_monitoring.router,
    smart_service_manager.router,
    staff_activity.router,
    technician_order.router,
)
