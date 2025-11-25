# database/call_center_supervisor/inbox.py
import asyncpg
from typing import List, Dict, Any, Optional
from config import settings

# ---------- CCS INBOX FUNKSIYALARI ----------

async def _conn():
    """Database connection"""
    return await asyncpg.connect(settings.DB_URL)

# ==================== TECHNICIAN ORDERS (Controllerdan kelgan) ====================

async def ccs_count_technician_orders() -> int:
    """Controllerdan kelgan texnik arizalar soni."""
    conn = await _conn()
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM technician_orders
            WHERE status = 'in_call_center_supervisor'
              AND COALESCE(is_active, TRUE) = TRUE
            """
        )
        return int(count or 0)
    finally:
        await conn.close()


async def ccs_fetch_technician_orders(
    offset: int = 0,
    limit: int = 1,
    *,
    order_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Controllerdan kelgan texnik arizalarni olish."""
    conn = await _conn()
    try:
        if order_id is not None:
            row = await conn.fetchrow(
                """
                SELECT 
                    tech_orders.id,
                    tech_orders.application_number,
                    tech_orders.user_id,
                    tech_orders.region,
                    tech_orders.abonent_id,
                    tech_orders.address,
                    tech_orders.media,
                    tech_orders.description,
                    tech_orders.description_operator,
                    tech_orders.status,
                    tech_orders.created_at,
                    tech_orders.updated_at,
                    tech_orders.business_type,
                    u.full_name AS client_name,
                    u.phone AS client_phone,
                    u.telegram_id AS client_telegram_id,
                    CASE 
                        WHEN tech_orders.media IS NOT NULL THEN 'photo'
                        ELSE NULL
                    END AS media_type
                FROM technician_orders tech_orders
                LEFT JOIN users u ON u.id = tech_orders.user_id
                WHERE tech_orders.status = 'in_call_center_supervisor'
                  AND COALESCE(tech_orders.is_active, TRUE) = TRUE
                  AND tech_orders.id = $1
                LIMIT 1
                """,
                order_id,
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT 
                    tech_orders.id,
                    tech_orders.application_number,
                    tech_orders.user_id,
                    tech_orders.region,
                    tech_orders.abonent_id,
                    tech_orders.address,
                    tech_orders.media,
                    tech_orders.description,
                    tech_orders.description_operator,
                    tech_orders.status,
                    tech_orders.created_at,
                    tech_orders.updated_at,
                    tech_orders.business_type,
                    u.full_name AS client_name,
                    u.phone AS client_phone,
                    u.telegram_id AS client_telegram_id,
                    CASE 
                        WHEN tech_orders.media IS NOT NULL THEN 'photo'
                        ELSE NULL
                    END AS media_type
                FROM technician_orders tech_orders
                LEFT JOIN users u ON u.id = tech_orders.user_id
                WHERE tech_orders.status = 'in_call_center_supervisor'
                  AND COALESCE(tech_orders.is_active, TRUE) = TRUE
                ORDER BY tech_orders.created_at ASC, tech_orders.id ASC
                OFFSET $1 LIMIT $2
                """,
                offset,
                limit,
            )

        return dict(row) if row else None
    finally:
        await conn.close()

# ==================== STAFF ORDERS (Operatordan kelgan) ====================

async def ccs_count_staff_orders() -> int:
    """Operatordan kelgan staff arizalar soni"""
    conn = await _conn()
    try:
        count = await conn.fetchval("""
            SELECT COUNT(*)
            FROM staff_orders
            WHERE status = 'in_call_center_supervisor'
              AND is_active = TRUE
        """)
        return int(count or 0)
    finally:
        await conn.close()

async def ccs_fetch_staff_orders(offset: int = 0, limit: int = 1) -> Optional[Dict[str, Any]]:
    """Operatordan kelgan staff arizalarni olish"""
    conn = await _conn()
    try:
        row = await conn.fetchrow("""
            SELECT 
                so.id,
                so.application_number,
                so.user_id,
                so.phone,
                so.region,
                so.abonent_id,
                so.address,
                so.tarif_id,
                so.description,
                so.type_of_zayavka,
                so.status,
                so.created_at,
                so.updated_at,
                
                -- Client ma'lumotlari
                COALESCE(client_user.full_name, 'Mijoz') as client_name,
                COALESCE(client_user.phone, so.phone) as client_phone,
                client_user.telegram_id as client_telegram_id,
                
                -- Yaratuvchi operator ma'lumotlari
                creator.full_name as operator_name,
                creator.phone as operator_phone,
                creator.role as operator_role,
                
                -- Tariff yoki muammo
                CASE 
                    WHEN so.type_of_zayavka = 'connection' THEN t.name
                    WHEN so.type_of_zayavka = 'technician' THEN so.description
                    ELSE NULL
                END as tariff_or_problem
                
            FROM staff_orders so
            LEFT JOIN users creator ON creator.id = so.user_id
            LEFT JOIN users client_user ON client_user.id::text = so.abonent_id
            LEFT JOIN tarif t ON t.id = so.tarif_id
            WHERE so.status = 'in_call_center_supervisor'
              AND so.is_active = TRUE
            ORDER BY so.created_at ASC
            OFFSET $1 LIMIT $2
        """, offset, limit)
        
        return dict(row) if row else None
    finally:
        await conn.close()

# ==================== OPERATOR ORDERS (Call Center operatordan kelgan) ====================

async def ccs_count_operator_orders() -> int:
    """Call Center operatordan kelgan arizalar soni"""
    conn = await _conn()
    try:
        count = await conn.fetchval("""
            SELECT COUNT(*)
            FROM staff_orders
            WHERE status = 'in_call_center_supervisor'
              AND is_active = TRUE
              AND user_id IN (
                  SELECT id FROM users WHERE role = 'callcenter_operator'
              )
        """)
        return int(count or 0)
    finally:
        await conn.close()

async def ccs_fetch_operator_orders(offset: int = 0, limit: int = 1) -> Optional[Dict[str, Any]]:
    """Call Center operatordan kelgan arizalarni olish"""
    conn = await _conn()
    try:
        row = await conn.fetchrow("""
            SELECT 
                so.id,
                so.application_number,
                so.user_id,
                so.region,
                so.abonent_id,
                so.address,
                so.description,
                so.business_type,
                so.type_of_zayavka,
                so.status,
                so.created_at,
                so.updated_at,
                
                -- Client ma'lumotlari
                COALESCE(client_user.full_name, 'Mijoz') as client_name,
                COALESCE(client_user.phone, so.phone) as client_phone,
                client_user.telegram_id as client_telegram_id,
                
                -- Yaratuvchi operator ma'lumotlari
                creator.full_name as operator_name,
                creator.phone as operator_phone,
                creator.role as operator_role,
                
                -- Tariff yoki muammo
                CASE 
                    WHEN so.type_of_zayavka = 'connection' THEN t.name
                    WHEN so.type_of_zayavka = 'technician' THEN so.description
                    ELSE NULL
                END as tariff_or_problem
                
            FROM staff_orders so
            LEFT JOIN users creator ON creator.id = so.user_id
            LEFT JOIN users client_user ON client_user.id::text = so.abonent_id
            LEFT JOIN tarif t ON t.id = so.tarif_id
            WHERE so.status = 'in_call_center_supervisor'
              AND so.is_active = TRUE
              AND creator.role = 'callcenter_operator'
            ORDER BY so.created_at ASC
            OFFSET $1 LIMIT $2
        """, offset, limit)
        
        return dict(row) if row else None
    finally:
        await conn.close()

# ==================== SEND TO CONTROLLER FUNCTIONS ====================

async def ccs_send_technician_to_controller(order_id: int, supervisor_telegram_id: int) -> bool:
    """Texnik arizani controllerga yuborish"""
    conn = await _conn()
    try:
        async with conn.transaction():
            # Get supervisor user ID
            supervisor = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", supervisor_telegram_id)
            if not supervisor:
                return False
            
            supervisor_id = supervisor['id']
            
            # Update technician order status
            result = await conn.execute("""
                UPDATE technician_orders
                SET status = 'in_controller',
                    updated_at = NOW()
                WHERE id = $1 AND status = 'in_call_center_supervisor'
            """, order_id)
            
            if result == "UPDATE 0":
                return False
            
            # Get controller ID
            controller = await conn.fetchrow("SELECT id FROM users WHERE role = 'controller' LIMIT 1")
            if not controller:
                return False
            
            controller_id = controller['id']
            
            # Get application_number
            app_info = await conn.fetchrow("SELECT application_number FROM technician_orders WHERE id = $1", order_id)
            
            # Create connection record
            await conn.execute("""
                INSERT INTO connections(
                    application_number,
                    sender_id, recipient_id,
                    sender_status, recipient_status,
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, 'in_call_center_supervisor', 'in_controller', NOW(), NOW())
            """, app_info['application_number'] if app_info else None, supervisor_id, controller_id)
            
            return True
    finally:
        await conn.close()

async def ccs_send_staff_to_controller(order_id: int, supervisor_telegram_id: int) -> bool:
    """Staff arizani controllerga yuborish"""
    conn = await _conn()
    try:
        async with conn.transaction():
            # Get supervisor user ID
            supervisor = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", supervisor_telegram_id)
            if not supervisor:
                return False
            
            supervisor_id = supervisor['id']
            
            # Update staff order status
            result = await conn.execute("""
                UPDATE staff_orders
                SET status = 'in_controller',
                    updated_at = NOW()
                WHERE id = $1 AND status = 'in_call_center_supervisor'
            """, order_id)
            
            if result == "UPDATE 0":
                return False
            
            # Get controller ID
            controller = await conn.fetchrow("SELECT id FROM users WHERE role = 'controller' LIMIT 1")
            if not controller:
                return False
            
            controller_id = controller['id']
            
            # Get application_number
            app_info = await conn.fetchrow("SELECT application_number FROM staff_orders WHERE id = $1", order_id)
            
            # Create connection record
            await conn.execute("""
                INSERT INTO connections(
                    application_number,
                    sender_id, recipient_id,
                    sender_status, recipient_status,
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, 'in_call_center_supervisor', 'in_controller', NOW(), NOW())
            """, app_info['application_number'] if app_info else None, supervisor_id, controller_id)
            
            return True
    finally:
        await conn.close()

# ==================== SEND TO OPERATOR FUNCTIONS ====================

async def ccs_send_technician_to_operator(order_id: int, supervisor_telegram_id: int) -> bool:
    """Controller'dan kelgan texnik arizani operator'ga yuborish"""
    conn = await _conn()
    try:
        async with conn.transaction():
            # Get supervisor user ID
            supervisor = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", supervisor_telegram_id)
            if not supervisor:
                return False
            
            supervisor_id = supervisor['id']
            
            # Update technician order status
            result = await conn.execute("""
                UPDATE technician_orders
                SET status = 'in_call_center_operator',
                    updated_at = NOW()
                WHERE id = $1 AND status = 'in_call_center_supervisor'
            """, order_id)
            
            if result == "UPDATE 0":
                return False
            
            # Get any operator ID
            operator = await conn.fetchrow("SELECT id FROM users WHERE role = 'callcenter_operator' LIMIT 1")
            if not operator:
                return False
            
            operator_id = operator['id']
            
            # Get application_number
            app_info = await conn.fetchrow("SELECT application_number FROM technician_orders WHERE id = $1", order_id)
            if not app_info:
                return False
            
            # Create connection record
            await conn.execute("""
                INSERT INTO connections(
                    application_number, sender_id, recipient_id,
                    sender_status, recipient_status,
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, 'in_call_center_supervisor', 'in_call_center_operator', NOW(), NOW())
            """, app_info["application_number"], supervisor_id, operator_id)
            
            return True
    finally:
        await conn.close()

async def ccs_send_staff_to_operator(order_id: int, supervisor_telegram_id: int) -> bool:
    """Controller'dan kelgan staff arizani operator'ga yuborish"""
    conn = await _conn()
    try:
        async with conn.transaction():
            # Get supervisor user ID
            supervisor = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", supervisor_telegram_id)
            if not supervisor:
                return False
            
            supervisor_id = supervisor['id']
            
            # Update staff order status
            result = await conn.execute("""
                UPDATE staff_orders
                SET status = 'in_call_center_operator',
                    updated_at = NOW()
                WHERE id = $1 AND status = 'in_call_center_supervisor'
            """, order_id)
            
            if result == "UPDATE 0":
                return False
            
            # Get any operator ID
            operator = await conn.fetchrow("SELECT id FROM users WHERE role = 'callcenter_operator' LIMIT 1")
            if not operator:
                return False
            
            operator_id = operator['id']
            
            # Get application_number
            app_info = await conn.fetchrow("SELECT application_number FROM staff_orders WHERE id = $1", order_id)
            if not app_info:
                return False
            
            # Create connection record
            await conn.execute("""
                INSERT INTO connections(
                    application_number, sender_id, recipient_id,
                    sender_status, recipient_status,
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, 'in_call_center_supervisor', 'in_call_center_operator', NOW(), NOW())
            """, app_info["application_number"], supervisor_id, operator_id)
            
            return True
    finally:
        await conn.close()

# ==================== COMPLETE FUNCTIONS ====================

async def ccs_complete_technician_order(order_id: int, supervisor_telegram_id: int) -> bool:
    """Texnik arizani yakunlash"""
    conn = await _conn()
    try:
        async with conn.transaction():
            # Get supervisor user ID
            supervisor = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", supervisor_telegram_id)
            if not supervisor:
                return False
            
            supervisor_id = supervisor['id']
            
            # Update technician order status
            result = await conn.execute("""
                UPDATE technician_orders
                SET status = 'completed',
                    updated_at = NOW()
                WHERE id = $1 AND status = 'in_call_center_supervisor'
            """, order_id)
            
            if result == "UPDATE 0":
                return False
            
            # Get application_number
            app_info = await conn.fetchrow("SELECT application_number FROM technician_orders WHERE id = $1", order_id)
            
            # Create connection record for completion
            await conn.execute("""
                INSERT INTO connections(
                    application_number,
                    sender_id, recipient_id,
                    sender_status, recipient_status,
                    created_at, updated_at
                )
                VALUES ($1, $2, $2, 'in_call_center_supervisor', 'completed', NOW(), NOW())
            """, app_info['application_number'] if app_info else None, supervisor_id)
            
            return True
    finally:
        await conn.close()

async def ccs_complete_staff_order(order_id: int, supervisor_telegram_id: int) -> bool:
    """Staff arizani yakunlash"""
    conn = await _conn()
    try:
        async with conn.transaction():
            # Get supervisor user ID
            supervisor = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", supervisor_telegram_id)
            if not supervisor:
                return False
            
            supervisor_id = supervisor['id']
            
            # Update staff order status
            result = await conn.execute("""
                UPDATE staff_orders
                SET status = 'completed',
                    updated_at = NOW()
                WHERE id = $1 AND status = 'in_call_center_supervisor'
            """, order_id)
            
            if result == "UPDATE 0":
                return False
            
            # Get application_number
            app_info = await conn.fetchrow("SELECT application_number FROM staff_orders WHERE id = $1", order_id)
            
            # Create connection record for completion
            await conn.execute("""
                INSERT INTO connections(
                    application_number,
                    sender_id, recipient_id,
                    sender_status, recipient_status,
                    created_at, updated_at
                )
                VALUES ($1, $2, $2, 'in_call_center_supervisor', 'completed', NOW(), NOW())
            """, app_info['application_number'] if app_info else None, supervisor_id)
            
            return True
    finally:
        await conn.close()

# ==================== CANCEL FUNCTIONS ====================

async def ccs_cancel_technician_order(order_id: int) -> bool:
    """Texnik arizani bekor qilish"""
    conn = await _conn()
    try:
        result = await conn.execute("""
            UPDATE technician_orders
            SET status = 'cancelled',
                is_active = FALSE,
                updated_at = NOW()
            WHERE id = $1 AND status = 'in_call_center_supervisor'
        """, order_id)
        
        return result == "UPDATE 1"
    finally:
        await conn.close()

async def ccs_cancel_staff_order(order_id: int) -> bool:
    """Staff arizani bekor qilish"""
    conn = await _conn()
    try:
        result = await conn.execute("""
            UPDATE staff_orders
            SET status = 'cancelled',
                is_active = FALSE,
                updated_at = NOW()
            WHERE id = $1 AND status = 'in_call_center_supervisor'
        """, order_id)
        
        return result == "UPDATE 1"
    finally:
        await conn.close()