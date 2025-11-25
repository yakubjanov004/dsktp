from aiogram import Router

from . import (
    connection_order,
    connection_service,
    export,
    inbox,
    language,
    monitoring,
    orders,
    realtime_monitoring,
    staff_activity,
    technician_order,
    technical_service,
    technicians,
)

router = Router()

router.include_routers(
    connection_order.router,
    connection_service.router,
    export.router,
    inbox.router,
    language.router,
    monitoring.router,
    orders.router,
    realtime_monitoring.router,
    staff_activity.router,
    technician_order.router,
    technical_service.router,
    technicians.router,
)
