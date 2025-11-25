# handlers/__init__.py
from aiogram import Router

from . import (
    start_handler,
    client_rating,  # Bu qatorni qo'shing
    # 1) Ombor router(lar)i admin'dan OLDIN turishi kerak
    warehouse,
    # agar inventarizatsiya alohida fayl bo'lsa, uni ham qo'shing:
    # warehouse_inventory,  # masalan: from .warehouse import inventory as warehouse_inventory

    admin,
    client,
    manager,
    junior_manager,
    controller,
    technician,
    call_center,
    call_center_supervisor,
)

router = Router()

router.include_routers(
    start_handler.router,
    client_rating.router,  # Bu qatorni qo'shing

    # Omborni oldin ulaymiz
    warehouse.router,
    # warehouse_inventory.router,  # agar alohida router bo'lsa, shu yerga qo'shing

    # Keyin admin
    admin.router,

    client.router,
    manager.router,
    junior_manager.router,
    controller.router,
    technician.router,
    call_center.router,
    call_center_supervisor.router,
)
