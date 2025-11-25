# database/technician/orders.py
import asyncpg
from typing import Optional
from config import settings


# ----------------- YORDAMCHI -----------------
async def _conn():
    return await asyncpg.connect(settings.DB_URL)


# ======================= CONNECTION ORDERS STATUS =======================
async def cancel_technician_request(applications_id: int,
                                    technician_user_id: Optional[int] = None, *,
                                    technician_id: Optional[int] = None) -> None:
    _ = technician_user_id if technician_user_id is not None else technician_id  # alias, bu yerda ishlatilmaydi
    conn = await _conn()
    try:
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE connection_orders
                   SET is_active = FALSE,
                       updated_at = NOW()
                 WHERE id = $1
                """,
                applications_id
            )
    finally:
        await conn.close()


async def accept_technician_work(applications_id: int,
                                 technician_user_id: Optional[int] = None, *,
                                 technician_id: Optional[int] = None) -> bool:
    """between_controller_technician -> in_technician"""
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("accept_technician_work(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        async with conn.transaction():
            row_old = await conn.fetchrow(
                "SELECT status FROM connection_orders WHERE id=$1 FOR UPDATE",
                applications_id
            )
            if not row_old or row_old["status"] != 'between_controller_technician':
                return False

            row_new = await conn.fetchrow(
                """
                UPDATE connection_orders
                   SET status = 'in_technician'::connection_order_status,
                       updated_at = NOW()
                 WHERE id=$1 AND status='between_controller_technician'::connection_order_status
             RETURNING status, application_number
                """,
                applications_id
            )
            if not row_new:
                return False
            
            # Get application_number
            app_number = row_new["application_number"]

            await conn.execute(
                """
                INSERT INTO connections (
                    application_number,
                    sender_id, recipient_id,
                    sender_status, recipient_status, created_at, updated_at
                )
                VALUES ($1, $2, $2,
                        'between_controller_technician'::connection_order_status,
                        'in_technician'::connection_order_status,
                        NOW(), NOW())
                """,
                app_number, uid
            )
            return True
    finally:
        await conn.close()


async def start_technician_work(applications_id: int,
                                technician_user_id: Optional[int] = None, *,
                                technician_id: Optional[int] = None) -> bool:
    """in_technician -> in_technician_work"""
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("start_technician_work(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        async with conn.transaction():
            row_old = await conn.fetchrow(
                "SELECT status FROM connection_orders WHERE id=$1 FOR UPDATE",
                applications_id
            )
            if not row_old or row_old["status"] != 'in_technician':
                return False

            row_new = await conn.fetchrow(
                """
                UPDATE connection_orders
                   SET status='in_technician_work'::connection_order_status,
                       updated_at=NOW()
                 WHERE id=$1 AND status='in_technician'::connection_order_status
             RETURNING status, application_number
                """,
                applications_id
            )
            if not row_new:
                return False
            
            app_number = row_new["application_number"]

            await conn.execute(
                """
                INSERT INTO connections(
                    application_number,
                    sender_id, recipient_id,
                    sender_status, recipient_status,
                    created_at, updated_at
                )
                VALUES ($1, $2, $2,
                        'in_technician'::connection_order_status,
                        'in_technician_work'::connection_order_status,
                        NOW(), NOW())
                """,
                app_number, uid
            )
            return True
    finally:
        await conn.close()


async def finish_technician_work(applications_id: int,
                                 technician_user_id: Optional[int] = None, *,
                                 technician_id: Optional[int] = None) -> bool:
    """in_technician_work -> completed"""
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("finish_technician_work(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        async with conn.transaction():
            row_old = await conn.fetchrow(
                "SELECT status FROM connection_orders WHERE id=$1 FOR UPDATE",
                applications_id
            )
            if not row_old or row_old["status"] != 'in_technician_work':
                return False

            ok = await conn.fetchrow(
                """
                UPDATE connection_orders
                   SET status = 'completed'::connection_order_status,
                       updated_at = NOW()
                 WHERE id = $1 AND status = 'in_technician_work'::connection_order_status
             RETURNING id, application_number
                """,
                applications_id
            )
            if not ok:
                return False
            
            app_number = ok["application_number"]

            await conn.execute(
                """
                INSERT INTO connections (
                    application_number,
                    sender_id, recipient_id,
                    sender_status, recipient_status, created_at, updated_at
                )
                VALUES ($1, $2, $2,
                        'in_technician_work'::connection_order_status,
                        'completed'::connection_order_status,
                        NOW(), NOW())
                """,
                app_number, uid
            )
            
            # Texnikda mavjud materiallar uchun material kamaytirish endi kerak emas,
            # chunki ular material_requests ga yozilmaydi va darhol kamaytiriladi
            
            return True
    finally:
        await conn.close()


# ======================= TECHNICIAN ORDERS STATUS =======================
async def accept_technician_work_for_tech(applications_id: int,
                                          technician_user_id: Optional[int] = None, *,
                                          technician_id: Optional[int] = None) -> bool:
    """Technician_orders: between_controller_technician -> in_technician (connections.technician_id to'ldiriladi)"""
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("accept_technician_work_for_tech(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        async with conn.transaction():
            row_old = await conn.fetchrow(
                "SELECT status FROM technician_orders WHERE id=$1 FOR UPDATE",
                applications_id
            )
            if not row_old or row_old["status"] != 'between_controller_technician':
                return False

            row_new = await conn.fetchrow(
                """
                UPDATE technician_orders
                   SET status = 'in_technician',
                       updated_at = NOW()
                 WHERE id=$1 AND status='between_controller_technician'
             RETURNING status, application_number
                """,
                applications_id
            )
            if not row_new:
                return False
            
            app_number = row_new["application_number"]

            try:
                await conn.execute(
                    """
                    INSERT INTO connections(
                        application_number,
                        sender_id, recipient_id,
                        sender_status, recipient_status, created_at, updated_at
                    )
                    VALUES ($1, $2, $2, 'between_controller_technician', 'in_technician', NOW(), NOW())
                    """,
                    app_number, uid
                )
            except Exception:
                pass
            return True
    finally:
        await conn.close()


async def start_technician_work_for_tech(applications_id: int,
                                         technician_user_id: Optional[int] = None, *,
                                         technician_id: Optional[int] = None) -> bool:
    """Technician_orders: in_technician -> in_technician_work"""
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("start_technician_work_for_tech(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        async with conn.transaction():
            row_old = await conn.fetchrow(
                "SELECT status FROM technician_orders WHERE id=$1 FOR UPDATE",
                applications_id
            )
            if not row_old or row_old["status"] != 'in_technician':
                return False

            row_new = await conn.fetchrow(
                """
                UPDATE technician_orders
                   SET status='in_technician_work',
                       updated_at=NOW()
                 WHERE id=$1 AND status='in_technician'
             RETURNING status, application_number
                """,
                applications_id
            )
            if not row_new:
                return False
            
            app_number = row_new["application_number"]

            try:
                await conn.execute(
                    """
                    INSERT INTO connections(
                        application_number,
                        sender_id, recipient_id,
                        sender_status, recipient_status, created_at, updated_at
                    )
                    VALUES ($1, $2, $2, 'in_technician', 'in_technician_work', NOW(), NOW())
                    """,
                    app_number, uid
                )
            except Exception:
                pass
            return True
    finally:
        await conn.close()


async def save_technician_diagnosis(applications_id: int,
                                    technician_user_id: Optional[int] = None, *,
                                    technician_id: Optional[int] = None,
                                    text: str = "") -> None:
    _ = technician_user_id if technician_user_id is not None else technician_id  # alias, bu yerda ishlatilmaydi
    conn = await _conn()
    try:
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE technician_orders
                   SET description_ish = $2,
                       updated_at = NOW()
                 WHERE id = $1
                """,
                applications_id, text
            )
    finally:
        await conn.close()


async def cancel_technician_request_for_tech(applications_id: int,
                                             technician_user_id: Optional[int] = None, *,
                                             technician_id: Optional[int] = None) -> None:
    _ = technician_user_id if technician_user_id is not None else technician_id  # alias, bu yerda ishlatilmaydi
    conn = await _conn()
    try:
        async with conn.transaction():
            await conn.execute(
                "UPDATE technician_orders SET is_active = FALSE, updated_at = NOW() WHERE id=$1",
                applications_id
            )
    finally:
        await conn.close()


async def finish_technician_work_for_tech(applications_id: int,
                                          technician_user_id: Optional[int] = None, *,
                                          technician_id: Optional[int] = None) -> bool:
    """Technician_orders: in_technician_work -> completed (connections.technician_id to'ldiriladi)"""
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("finish_technician_work_for_tech(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        async with conn.transaction():
            row_old = await conn.fetchrow(
                "SELECT status FROM technician_orders WHERE id=$1 FOR UPDATE",
                applications_id
            )
            if not row_old or row_old["status"] != 'in_technician_work':
                return False

            ok = await conn.fetchrow(
                """
                UPDATE technician_orders
                   SET status='completed',
                       updated_at=NOW()
                 WHERE id=$1 AND status='in_technician_work'
             RETURNING id, application_number
                """,
                applications_id
            )
            if not ok:
                return False
            
            app_number = ok["application_number"]

            try:
                await conn.execute(
                    """
                    INSERT INTO connections(
                        application_number,
                        sender_id, recipient_id,
                        sender_status, recipient_status, created_at, updated_at
                    )
                    VALUES ($1, $2, $2, 'in_technician_work', 'completed', NOW(), NOW())
                    """,
                    app_number, uid
                )
            except Exception:
                pass

            # Texnikda mavjud materiallar uchun material kamaytirish endi kerak emas,
            # chunki ular material_requests ga yozilmaydi va darhol kamaytiriladi

            return True
    finally:
        await conn.close()


# ======================= STAFF ORDERS STATUS =======================
async def accept_technician_work_for_staff(applications_id: int,
                                          technician_user_id: Optional[int] = None, *,
                                          technician_id: Optional[int] = None) -> bool:
    """staff order: between_controller_technician -> in_technician (connections.staff_id = applications_id)"""
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("accept_technician_work_for_staff(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        async with conn.transaction():
            row_old = await conn.fetchrow(
                "SELECT status FROM staff_orders WHERE id=$1 FOR UPDATE",
                applications_id
            )
            if not row_old or row_old["status"] != 'between_controller_technician':
                return False

            row_new = await conn.fetchrow(
                """
                UPDATE staff_orders
                   SET status = 'in_technician',
                       updated_at = NOW()
                 WHERE id=$1 AND status='between_controller_technician'
             RETURNING status, application_number
                """,
                applications_id
            )
            if not row_new:
                return False
            
            app_number = row_new["application_number"]

            await conn.execute(
                """
                INSERT INTO connections(
                    application_number,
                    sender_id, recipient_id,
                    sender_status, recipient_status, created_at, updated_at
                )
                VALUES ($1, $2, $2, 'between_controller_technician', 'in_technician', NOW(), NOW())
                """,
                app_number, uid
            )

            return True
    finally:
        await conn.close()


async def start_technician_work_for_staff(applications_id: int,
                                         technician_user_id: Optional[int] = None, *,
                                         technician_id: Optional[int] = None) -> bool:
    """staff order: in_technician -> in_technician_work"""
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("start_technician_work_for_staff(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        async with conn.transaction():
            row_old = await conn.fetchrow(
                "SELECT status FROM staff_orders WHERE id=$1 FOR UPDATE",
                applications_id
            )
            if not row_old or row_old["status"] != 'in_technician':
                return False

            row_new = await conn.fetchrow(
                """
                UPDATE staff_orders
                   SET status='in_technician_work',
                       updated_at=NOW()
                 WHERE id=$1 AND status='in_technician'
             RETURNING status, application_number
                """,
                applications_id
            )
            if not row_new:
                return False
            
            app_number = row_new["application_number"]

            await conn.execute(
                """
                INSERT INTO connections(
                    application_number,
                    sender_id, recipient_id,
                    sender_status, recipient_status, created_at, updated_at
                )
                VALUES ($1, $2, $2, 'in_technician', 'in_technician_work', NOW(), NOW())
                """,
                app_number, uid
            )

            return True
    finally:
        await conn.close()


async def finish_technician_work_for_staff(applications_id: int,
                                          technician_user_id: Optional[int] = None, *,
                                          technician_id: Optional[int] = None) -> bool:
    """staff order: in_technician_work -> completed"""
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("finish_technician_work_for_staff(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        async with conn.transaction():
            row_old = await conn.fetchrow(
                "SELECT status FROM staff_orders WHERE id=$1 FOR UPDATE",
                applications_id
            )
            if not row_old or row_old["status"] != 'in_technician_work':
                return False

            row_new = await conn.fetchrow(
                """
                UPDATE staff_orders
                   SET status = 'completed',
                       updated_at = NOW()
                 WHERE id = $1 AND status = 'in_technician_work'
             RETURNING id, application_number
                """,
                applications_id
            )
            if not row_new:
                return False
            
            app_number = row_new["application_number"]

            try:
                await conn.execute(
                    """
                    INSERT INTO connections(
                        application_number,
                        sender_id, recipient_id,
                        sender_status, recipient_status, created_at, updated_at
                    )
                    VALUES ($1, $2, $2, 'in_technician_work', 'completed', NOW(), NOW())
                    """,
                    app_number, uid
                )
            except Exception:
                pass

            # Texnikda mavjud materiallar uchun material kamaytirish endi kerak emas,
            # chunki ular material_requests ga yozilmaydi va darhol kamaytiriladi

            return True
    finally:
        await conn.close()
