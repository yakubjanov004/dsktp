# database/warehouse/inbox.py
import asyncpg
from typing import List, Dict, Any, Optional
from config import settings

async def _conn():
    """Database connection helper"""
    return await asyncpg.connect(settings.DB_URL)

# ==================== CONNECTION ORDERS ====================

async def fetch_warehouse_connection_orders(
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Omborda turgan ulanish arizalari (connection_orders) - status: 'in_warehouse'
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT
                co.id,
                co.address,
                co.region,
                co.status,
                co.created_at,
                co.updated_at,
                co.jm_notes,
                u.full_name AS client_name,
                u.phone AS client_phone,
                u.telegram_id AS client_telegram_id,
                t.name AS tariff_name
            FROM connection_orders co
            LEFT JOIN users u ON u.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            WHERE co.status = 'in_warehouse'
              AND co.is_active = TRUE
            ORDER BY co.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def fetch_warehouse_connection_orders_with_materials(
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Ombordan material so'ralgan ulanish arizalari
    YANGI: Status tekshirmaydi, faqat material_requests mavjudligini tekshiradi
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT
                co.id,
                co.application_number,
                co.address,
                co.region,
                co.status,
                co.created_at,
                co.updated_at,
                co.jm_notes,
                u.full_name AS client_name,
                u.phone AS client_phone,
                u.telegram_id AS client_telegram_id,
                t.name AS tariff_name,
                COUNT(mr.id) as material_count
            FROM material_requests mr
            JOIN connection_orders co ON co.application_number = mr.application_number
            LEFT JOIN users u ON u.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            WHERE mr.source_type = 'warehouse'
              AND COALESCE(mr.warehouse_approved, false) = false
              AND co.is_active = TRUE
            GROUP BY co.id, co.application_number, co.address, co.region, co.status, co.created_at, co.updated_at, 
                     co.jm_notes, u.full_name, u.phone, u.telegram_id, t.name
            ORDER BY co.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def count_warehouse_connection_orders_with_materials() -> int:
    """
    Ombordan material so'ralgan ulanish arizalari soni
    YANGI: Status tekshirmaydi, faqat tasdiqlash kutayotgan materiallar
    """
    conn = await _conn()
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT co.id)
            FROM material_requests mr
            JOIN connection_orders co ON co.application_number = mr.application_number
            WHERE mr.source_type = 'warehouse'
              AND COALESCE(mr.warehouse_approved, false) = false
              AND co.is_active = TRUE
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def count_warehouse_technician_orders() -> int:
    """
    Ombordan material so'ralgan texnik arizalari soni
    YANGI: Status tekshirmaydi, faqat tasdiqlash kutayotgan materiallar
    """
    conn = await _conn()
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT t_orders.id)
            FROM material_requests mr
            JOIN technician_orders t_orders ON t_orders.application_number = mr.application_number
            WHERE mr.source_type = 'warehouse'
              AND COALESCE(mr.warehouse_approved, false) = false
              AND t_orders.is_active = TRUE
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def count_warehouse_staff_orders() -> int:
    """
    Ombordan material so'ralgan xodim arizalari soni
    YANGI: Status tekshirmaydi, faqat tasdiqlash kutayotgan materiallar
    """
    conn = await _conn()
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT so.id)
            FROM material_requests mr
            JOIN staff_orders so ON so.application_number = mr.application_number
            WHERE mr.source_type = 'warehouse'
              AND COALESCE(mr.warehouse_approved, false) = false
              AND so.is_active = TRUE
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def fetch_materials_for_connection_order(connection_order_id: int) -> List[Dict[str, Any]]:
    """
    Ulanish arizasi uchun materiallar ro'yxati
    YANGI: Faqat source_type='warehouse' bo'lgan materiallarni ko'rsatadi
    """
    conn = await _conn()
    try:
        app_number = await conn.fetchval(
            "SELECT application_number FROM connection_orders WHERE id = $1",
            connection_order_id
        )
        
        if not app_number:
            return []
            
        rows = await conn.fetch(
            """
            SELECT
                mr.material_id,
                m.name as material_name,
                mr.quantity,
                COALESCE(m.price, 0) as price,
                mr.total_price,
                mr.source_type,
                COALESCE(mr.warehouse_approved, false) as warehouse_approved,
                COALESCE(m.material_unit, 'dona') as material_unit
            FROM material_requests mr
            JOIN materials m ON m.id = mr.material_id
            WHERE mr.application_number = $1
              AND mr.source_type = 'warehouse'
            ORDER BY m.name
            """,
            app_number
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# ==================== TECHNICIAN ORDERS ====================

async def fetch_warehouse_technician_orders(
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Ombordan material so'ralgan texnik arizalari
    YANGI: Status tekshirmaydi, faqat material_requests mavjudligini tekshiradi
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT
                t_orders.id,
                t_orders.application_number,
                t_orders.address,
                t_orders.region,
                t_orders.status,
                t_orders.created_at,
                t_orders.updated_at,
                t_orders.description,
                t_orders.media,
                u.full_name AS client_name,
                u.phone AS client_phone,
                u.telegram_id AS client_telegram_id
            FROM material_requests mr
            JOIN technician_orders t_orders ON t_orders.application_number = mr.application_number
            LEFT JOIN users u ON u.id = t_orders.user_id
            WHERE mr.source_type = 'warehouse'
              AND COALESCE(mr.warehouse_approved, false) = false
              AND t_orders.is_active = TRUE
            GROUP BY t_orders.id, t_orders.application_number, t_orders.address, t_orders.region, t_orders.status,
                     t_orders.created_at, t_orders.updated_at, t_orders.description, t_orders.media,
                     u.full_name, u.phone, u.telegram_id
            ORDER BY t_orders.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def fetch_warehouse_technician_orders_with_materials(
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Omborda turgan texnik arizalari materiallar bilan
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT
                t_orders.id,
                t_orders.address,
                t_orders.region,
                t_orders.status,
                t_orders.created_at,
                t_orders.updated_at,
                t_orders.description,
                t_orders.media,
                u.full_name AS client_name,
                u.phone AS client_phone,
                u.telegram_id AS client_telegram_id,
                COUNT(mr.id) as material_count
            FROM technician_orders t_orders
            LEFT JOIN users u ON u.id = t_orders.user_id
            LEFT JOIN material_requests mr ON mr.application_number = t_orders.application_number
            WHERE t_orders.status = 'in_warehouse'
              AND t_orders.is_active = TRUE
            GROUP BY t_orders.id, t_orders.address, t_orders.region, t_orders.status, t_orders.created_at, t_orders.updated_at, 
                     t_orders.description, t_orders.media, u.full_name, u.phone, u.telegram_id
            ORDER BY t_orders.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def count_warehouse_technician_orders_with_materials() -> int:
    """
    Ombordan material so'ralgan texnik arizalari soni
    YANGI: Status tekshirmaydi, faqat tasdiqlash kutayotgan materiallar
    """
    conn = await _conn()
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT t_orders.id)
            FROM material_requests mr
            JOIN technician_orders t_orders ON t_orders.application_number = mr.application_number
            WHERE mr.source_type = 'warehouse'
              AND COALESCE(mr.warehouse_approved, false) = false
              AND t_orders.is_active = TRUE
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def fetch_materials_for_technician_order(technician_order_id: int) -> List[Dict[str, Any]]:
    """
    Texnik arizasi uchun materiallar ro'yxati
    YANGI: Faqat source_type='warehouse' bo'lgan materiallarni ko'rsatadi
    """
    conn = await _conn()
    try:
        # Get application_number from technician_orders
        app_number = await conn.fetchval(
            "SELECT application_number FROM technician_orders WHERE id = $1",
            technician_order_id
        )
        
        if not app_number:
            return []
            
        rows = await conn.fetch(
            """
            SELECT
                mr.material_id,
                m.name as material_name,
                mr.quantity,
                COALESCE(m.price, 0) as price,
                mr.total_price,
                mr.source_type,
                COALESCE(mr.warehouse_approved, false) as warehouse_approved,
                COALESCE(m.material_unit, 'dona') as material_unit
            FROM material_requests mr
            JOIN materials m ON m.id = mr.material_id
            WHERE mr.application_number = $1
              AND mr.source_type = 'warehouse'
            ORDER BY m.name
            """,
            app_number
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# ==================== STAFF ORDERS ====================

async def fetch_warehouse_staff_orders(
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Ombordan material so'ralgan xodim arizalari
    YANGI: Status tekshirmaydi, faqat material_requests mavjudligini tekshiradi
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT
                so.id,
                so.application_number,
                so.address,
                so.region,
                so.status,
                so.created_at,
                so.updated_at,
                so.description,
                so.type_of_zayavka,
                u.full_name AS client_name,
                u.phone AS client_phone,
                u.telegram_id AS client_telegram_id
            FROM material_requests mr
            JOIN staff_orders so ON so.application_number = mr.application_number
            LEFT JOIN users u ON u.id = so.user_id
            WHERE mr.source_type = 'warehouse'
              AND COALESCE(mr.warehouse_approved, false) = false
              AND so.is_active = TRUE
            GROUP BY so.id, so.application_number, so.address, so.region, so.status,
                     so.created_at, so.updated_at, so.description, so.type_of_zayavka,
                     u.full_name, u.phone, u.telegram_id
            ORDER BY so.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def fetch_warehouse_staff_orders_with_materials(
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Omborda turgan xodim arizalari materiallar bilan
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT
                so.id,
                so.application_number,
                so.address,
                so.region,
                so.status,
                so.created_at,
                so.updated_at,
                so.description,
                so.phone,
                so.abonent_id,
                u.full_name AS client_name,
                u.phone AS client_phone,
                u.telegram_id AS client_telegram_id,
                COUNT(mr.id) as material_count
            FROM staff_orders so
            LEFT JOIN users u ON u.id = so.user_id
            LEFT JOIN material_requests mr ON mr.application_number = so.application_number
            WHERE so.status = 'in_warehouse'
              AND so.is_active = TRUE
            GROUP BY so.id, so.application_number, so.address, so.region, so.status, so.created_at, so.updated_at, 
                     so.description, so.phone, so.abonent_id, u.full_name, u.phone, u.telegram_id
            ORDER BY so.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def count_warehouse_staff_orders_with_materials() -> int:
    """
    Ombordan material so'ralgan xodim arizalari soni
    YANGI: Status tekshirmaydi, faqat tasdiqlash kutayotgan materiallar
    """
    conn = await _conn()
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT so.id)
            FROM material_requests mr
            JOIN staff_orders so ON so.application_number = mr.application_number
            WHERE mr.source_type = 'warehouse'
              AND COALESCE(mr.warehouse_approved, false) = false
              AND so.is_active = TRUE
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def fetch_materials_for_staff_order(staff_order_id: int) -> List[Dict[str, Any]]:
    """
    Xodim arizasi uchun materiallar ro'yxati
    YANGI: Faqat source_type='warehouse' bo'lgan materiallarni ko'rsatadi
    """
    conn = await _conn()
    try:
        # Get application_number from staff_orders
        app_number = await conn.fetchval(
            "SELECT application_number FROM staff_orders WHERE id = $1",
            staff_order_id
        )
        
        if not app_number:
            return []
            
        rows = await conn.fetch(
            """
            SELECT
                mr.material_id,
                m.name as material_name,
                mr.quantity,
                COALESCE(m.price, 0) as price,
                mr.total_price,
                mr.source_type,
                COALESCE(mr.warehouse_approved, false) as warehouse_approved,
                COALESCE(m.material_unit, 'dona') as material_unit
            FROM material_requests mr
            JOIN materials m ON m.id = mr.material_id
            WHERE mr.application_number = $1
              AND mr.source_type = 'warehouse'
            ORDER BY m.name
            """,
            app_number
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# ==================== MATERIAL REQUESTS ====================

async def fetch_material_requests_by_connection_orders(
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Ulanish arizalari uchun material so'rovlari
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT
                mr.id,
                mr.application_number,
                mr.material_id,
                mr.quantity,
                mr.price,
                mr.total_price,
                mr.created_at,
                m.name as material_name,
                co.address,
                co.region,
                u.full_name as client_name
            FROM material_requests mr
            JOIN materials m ON m.id = mr.material_id
            JOIN connection_orders co ON co.application_number = mr.application_number
            LEFT JOIN users u ON u.id = co.user_id
            WHERE co.status = 'in_warehouse'
              AND co.is_active = TRUE
            ORDER BY co.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def fetch_material_requests_by_technician_orders(
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Texnik arizalari uchun material so'rovlari
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT
                mr.id,
                mr.application_number,
                mr.material_id,
                mr.quantity,
                mr.price,
                mr.total_price,
                mr.created_at,
                m.name as material_name,
                t_orders.address,
                t_orders.region,
                u.full_name as client_name
            FROM material_requests mr
            JOIN materials m ON m.id = mr.material_id
            JOIN technician_orders t_orders ON t_orders.application_number = mr.application_number
            LEFT JOIN users u ON u.id = t_orders.user_id
            WHERE t_orders.status = 'in_warehouse'
              AND t_orders.is_active = TRUE
            ORDER BY t_orders.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def fetch_material_requests_by_staff_orders(
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Xodim arizalari uchun material so'rovlari
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT
                mr.id,
                mr.application_number,
                mr.material_id,
                mr.quantity,
                mr.price,
                mr.total_price,
                mr.created_at,
                m.name as material_name,
                so.address,
                so.region,
                u.full_name as client_name
            FROM material_requests mr
            JOIN materials m ON m.id = mr.material_id
            JOIN staff_orders so ON so.application_number = mr.application_number
            LEFT JOIN users u ON u.id = so.user_id
            WHERE so.status = 'in_warehouse'
              AND so.is_active = TRUE
            ORDER BY so.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def count_material_requests_by_connection_orders() -> int:
    """
    Ulanish arizalari uchun material so'rovlari soni
    """
    conn = await _conn()
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM material_requests mr
            JOIN connection_orders co ON co.application_number = mr.application_number
            WHERE co.status = 'in_warehouse'
              AND co.is_active = TRUE
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def count_material_requests_by_technician_orders() -> int:
    """
    Texnik arizalari uchun material so'rovlari soni
    """
    conn = await _conn()
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM material_requests mr
            JOIN technician_orders t_orders ON t_orders.application_number = mr.application_number
            WHERE t_orders.status = 'in_warehouse'
              AND t_orders.is_active = TRUE
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

async def count_material_requests_by_staff_orders() -> int:
    """
    Xodim arizalari uchun material so'rovlari soni
    """
    conn = await _conn()
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM material_requests mr
            JOIN staff_orders so ON so.application_number = mr.application_number
            WHERE so.status = 'in_warehouse'
              AND so.is_active = TRUE
            """
        )
        return int(count or 0)
    finally:
        await conn.close()

# ---------- AGGREGATE COUNT FUNCTIONS ----------

async def get_all_material_requests_count() -> Dict[str, int]:
    """Get counts for all material request types"""
    conn = await _conn()
    try:
        connection_count = await count_material_requests_by_connection_orders()
        technician_count = await count_material_requests_by_technician_orders()
        staff_count = await count_material_requests_by_staff_orders()
        
        return {
            'connection_orders': connection_count,
            'technician_orders': technician_count,
            'staff_orders': staff_count,
            'total': connection_count + technician_count + staff_count
        }
    finally:
        await conn.close()

async def get_all_warehouse_orders_count() -> Dict[str, int]:
    """Get counts for all warehouse order types"""
    conn = await _conn()
    try:
        connection_count = await count_warehouse_connection_orders_with_materials()
        technician_count = await count_warehouse_technician_orders_with_materials()
        staff_count = await count_warehouse_staff_orders_with_materials()
        
        return {
            'connection_orders': connection_count,
            'technician_orders': technician_count,
            'staff_orders': staff_count,
            'total': connection_count + technician_count + staff_count
        }
    finally:
        await conn.close()

# ==================== HELPER FUNCTIONS ====================

async def create_material_and_technician_entry(order_id: int, order_type: str, warehouse_user_id: int) -> bool:
    """
    Ariza tasdiqlangandan so'ng material_and_technician jadvaliga yozish
    issued_by va issued_at bir vaqtda yoziladi
    """
    conn = await _conn()
    try:
        # Order type ga qarab material_requests dan materiallarni olish
        if order_type == "connection":
            table_name = "connection_orders"
        elif order_type == "technician":
            table_name = "technician_orders"
        elif order_type == "staff":
            table_name = "staff_orders"
        else:
            return False
        
        # Get application_number and technician_id from the order table
        order_info = await conn.fetchrow(
            f"""
            SELECT user_id, application_number 
            FROM {table_name} 
            WHERE id = $1
            """,
            order_id
        )
        
        if not order_info:
            print(f"No order found for {order_type} order {order_id}")
            return False
            
        technician_id = order_info['user_id']
        application_number = order_info['application_number']
        
        if not application_number:
            print(f"No application_number found for {order_type} order {order_id}")
            return False
        
        # Material requests dan materiallarni olish
        material_requests = await conn.fetch(
            """
            SELECT mr.material_id, mr.quantity, mr.application_number, mr.source_type
            FROM material_requests mr
            WHERE mr.application_number = $1
            """,
            application_number
        )
        
        if not material_requests:
            print(f"No material requests found for {order_type} order {order_id}")
            return True  
        
        for mr in material_requests:
            material_id = mr['material_id']
            quantity = mr['quantity']
            source_type = mr.get('source_type', 'warehouse')
            
            if source_type == 'warehouse':
                # Get material details for the new columns
                material_info = await conn.fetchrow(
                    "SELECT name, price, COALESCE(material_unit, 'dona') as material_unit FROM materials WHERE id = $1",
                    material_id
                )
                
                if material_info:
                    material_name = material_info['name']
                    price = material_info['price'] or 0
                    material_unit = material_info.get('material_unit', 'dona')
                    total_price = price * quantity
                    
                    # Check if entry exists
                    existing = await conn.fetchrow(
                        "SELECT id, quantity, total_price FROM material_and_technician WHERE user_id = $1 AND material_id = $2",
                        technician_id, material_id
                    )
                    
                    if existing:
                        # Update existing entry - add quantity
                        # issued_by va issued_at yangilanadi
                        await conn.execute(
                            """
                            UPDATE material_and_technician 
                            SET quantity = quantity + $1,
                                application_number = $2,
                                material_name = $3,
                                price = $4,
                                total_price = total_price + $5,
                                issued_by = $6,
                                issued_at = NOW()
                            WHERE user_id = $7 AND material_id = $8
                            """,
                            quantity, application_number, material_name, price, total_price,
                            warehouse_user_id, technician_id, material_id
                        )
                    else:
                        # Insert new entry
                        # issued_by va issued_at bir vaqtda yoziladi
                        await conn.execute(
                            """
                            INSERT INTO material_and_technician 
                            (user_id, material_id, quantity, application_number, material_name, 
                             material_unit, price, total_price, issued_by, issued_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                            """,
                            technician_id, material_id, quantity, application_number, 
                            material_name, material_unit, price, total_price, warehouse_user_id
                        )
                
                # Ombor zaxirasini kamaytirish
                await conn.execute(
                    """
                    UPDATE materials 
                    SET quantity = GREATEST(0, quantity - $1)
                    WHERE id = $2
                    """,
                    quantity, material_id
                )
            
            # warehouse_approved ni TRUE qilish
            await conn.execute(
                """
                UPDATE material_requests 
                SET warehouse_approved = TRUE
                WHERE application_number = $1 AND material_id = $2
                """,
                application_number, material_id
            )
        
        return True
    except Exception as e:
        print(f"Error creating material_and_technician entries: {e}")
        return False
    finally:
        await conn.close()

# ==================== CONFIRMATION FUNCTIONS ====================

async def confirm_materials_and_update_status_for_connection(order_id: int, warehouse_user_id: int) -> bool:
    """
    Ulanish arizasi uchun materiallarni tasdiqlash
    YANGI: Status O'ZGARMAYDI! Faqat materiallarni texnikka berish va ombor zaxirasini kamaytirish
    issued_by va issued_at bir vaqtda yoziladi
    """
    conn = await _conn()
    try:
        # STATUS O'ZGARMAYDI! Texnik allaqachon in_technician_work da davom etmoqda
        # Faqat materiallarni texnikka beramiz
        
        # Material_and_technician jadvaliga yozish va ombor zaxirasini kamaytirish
        success = await create_material_and_technician_entry(order_id, "connection", warehouse_user_id)
        if not success:
            print(f"Failed to create material_and_technician entries for connection order {order_id}")
        
        return True
    except Exception as e:
        print(f"Error confirming connection order materials: {e}")
        return False
    finally:
        await conn.close()

async def confirm_materials_and_update_status_for_technician(order_id: int, warehouse_user_id: int) -> bool:
    """
    Texnik arizasi uchun materiallarni tasdiqlash
    YANGI: Status O'ZGARMAYDI! Faqat materiallarni texnikka berish va ombor zaxirasini kamaytirish
    issued_by va issued_at bir vaqtda yoziladi
    """
    conn = await _conn()
    try:
        # STATUS O'ZGARMAYDI! Texnik allaqachon in_technician_work da davom etmoqda
        # Faqat materiallarni texnikka beramiz
        
        # Material_and_technician jadvaliga yozish va ombor zaxirasini kamaytirish
        success = await create_material_and_technician_entry(order_id, "technician", warehouse_user_id)
        if not success:
            print(f"Failed to create material_and_technician entries for technician order {order_id}")
        
        return True
    except Exception as e:
        print(f"Error confirming technician order materials: {e}")
        return False
    finally:
        await conn.close()

async def confirm_materials_and_update_status_for_staff(order_id: int, warehouse_user_id: int) -> bool:
    """
    Xodim arizasi uchun materiallarni tasdiqlash
    YANGI: Status O'ZGARMAYDI! Faqat materiallarni texnikka berish va ombor zaxirasini kamaytirish
    issued_by va issued_at bir vaqtda yoziladi
    """
    conn = await _conn()
    try:
        # STATUS O'ZGARMAYDI! Texnik allaqachon in_technician_work da davom etmoqda
        # Faqat materiallarni texnikka beramiz
        
        # Material_and_technician jadvaliga yozish va ombor zaxirasini kamaytirish
        success = await create_material_and_technician_entry(order_id, "staff", warehouse_user_id)
        if not success:
            print(f"Failed to create material_and_technician entries for staff order {order_id}")
        
        return True
    except Exception as e:
        print(f"Error confirming staff order materials: {e}")
        return False
    finally:
        await conn.close()