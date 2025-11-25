# database/technician/materials.py
import asyncpg
from typing import List, Dict, Any, Optional
from config import settings
import logging
logger = logging.getLogger(__name__)


# ----------------- YORDAMCHI -----------------
async def _conn():
    return await asyncpg.connect(settings.DB_URL)

def _as_dicts(rows):
    return [dict(r) for r in rows]


# ======================= MATERIALLAR (SELECTION) =======================
async def fetch_technician_materials(user_id: int = None, current_application_id: int = None, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
    """
    current_application_id - joriy ariza ID, bu arizadagi tanlovlarni hisobga olmaslik
    """
    conn = await _conn()
    try:
        if user_id is not None:
            rows = await conn.fetch(
                """
                SELECT
                  m.id          AS material_id,
                  m.name,
                  m.price,
                  m.serial_number,
                  t.quantity    AS assigned_quantity,
                  0 AS pending_usage,  -- Texnikda mavjud materiallar uchun pending_usage yo'q
                  t.quantity AS stock_quantity  -- Texnikda mavjud materiallar uchun to'liq miqdor
                FROM material_and_technician t
                JOIN materials m ON m.id = t.material_id
                WHERE t.user_id = $1
                  AND t.quantity > 0
                ORDER BY m.name
                LIMIT $2 OFFSET $3
                """,
                user_id, limit, offset
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                  m.id          AS material_id,
                  m.name,
                  m.price,
                  m.serial_number,
                  t.quantity    AS assigned_quantity,
                  0 AS pending_usage,  -- Texnikda mavjud materiallar uchun pending_usage yo'q
                  t.quantity AS stock_quantity  -- Texnikda mavjud materiallar uchun to'liq miqdor
                FROM material_and_technician t
                JOIN materials m ON m.id = t.material_id
                WHERE t.quantity > 0
                ORDER BY m.name
                LIMIT $1 OFFSET $2
                """,
                limit, offset
            )
        return _as_dicts(rows)
    finally:
        await conn.close()


async def fetch_all_materials(limit: int = 200, offset: int = 0) -> list[dict]:
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT
                m.id   AS material_id,
                m.name,
                COALESCE(m.price, 0) AS price
            FROM materials m
            ORDER BY m.name
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def fetch_materials_not_assigned_to_technician(user_id: int, limit: int = 200, offset: int = 0) -> list[dict]:
    """
    Materials jadvalida bor lekin material_technician jadvalida yo'q bo'lgan materiallarni olish.
    Ya'ni texnikka biriktirilmagan materiallar.
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT
                m.id AS material_id,
                m.name,
                COALESCE(m.price, 0) AS price,
                COALESCE(m.quantity, 0) AS stock_quantity
            FROM materials m
            LEFT JOIN material_and_technician mt ON m.id = mt.material_id AND mt.user_id = $1
            WHERE mt.material_id IS NULL
            ORDER BY m.name
            LIMIT $2 OFFSET $3
            """,
            user_id, limit, offset
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def fetch_material_by_id(material_id: int) -> Optional[Dict[str, Any]]:
    conn = await _conn()
    try:
        row = await conn.fetchrow(
            "SELECT id, name, price, serial_number FROM materials WHERE id=$1",
            material_id
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def fetch_assigned_qty(user_id: int, material_id: int) -> int:
    """Texnikka biriktirilgan joriy qoldiq."""
    conn = await _conn()
    try:
        row = await conn.fetchrow(
            """
            SELECT COALESCE(quantity, 0) AS qty
            FROM material_and_technician
            WHERE user_id = $1 AND material_id = $2
            """,
            user_id, material_id
        )
        return int(row["qty"]) if row else 0
    finally:
        await conn.close()


# Bu funksiya endi ishlatilmaydi, chunki texnikda mavjud materiallar uchun 
# material_requests ga yozilmaydi va pending_usage hisoblanmaydi


# --- MUHIM: Tanlovni jamlamay, aynan o'rnatuvchi upsert (OVERWRITE) ---

async def _has_column(conn, table: str, column: str) -> bool:
    """
    Checks if a column exists in a given table.
    """
    sql = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = $1 AND column_name = $2
        )
    """
    return await conn.fetchval(sql, table, column)

async def _get_application_number_for_material_issued(conn, applications_id: int, request_type: str) -> str:
    """Material_issued uchun application_number ni olish"""
    try:
        if request_type == "technician":
            result = await conn.fetchval(
                "SELECT application_number FROM technician_orders WHERE id = $1",
                applications_id
            )
        elif request_type == "staff":
            result = await conn.fetchval(
                "SELECT application_number FROM staff_orders WHERE id = $1",
                applications_id
            )
        else:  # connection
            result = await conn.fetchval(
                "SELECT application_number FROM connection_orders WHERE id = $1",
                applications_id
            )
        
        return result or str(applications_id)  # Fallback to ID if application_number not found
    except Exception:
        return str(applications_id)  # Fallback to ID on error

async def _insert_material_issued(
    conn, 
    material_id: int, 
    quantity: int, 
    price: float, 
    total_price: float, 
    issued_by: int, 
    application_number: str, 
    request_type: str, 
    material_name: str
) -> None:
    """Material_issued jadvaliga yozish - soddalashtirilgan versiya (is_approved olib tashlandi)"""

    await conn.execute(
        """
        INSERT INTO material_issued (
            material_id, quantity, price, total_price, issued_by, issued_at,
            material_name, material_unit, application_number, request_type
        ) VALUES ($1, $2, $3, $4, $5, NOW(), $6, 'dona', $7, $8)
        """,
        material_id, quantity, price, total_price, issued_by,
        material_name, application_number, request_type
    )

async def upsert_material_selection(
    user_id: int,
    application_id: int,  
    material_id: int,
    qty: int,
    request_type: str = "connection",
    source_type: str = "warehouse"
) -> None:
    """
    Material tanlash funksiyasi - REFACTORED for application_number schema.
    
    source_type='technician_stock': Texnikda mavjud material - darhol kamaytiriladi va material_requests ga yoziladi
    source_type='warehouse': Ombordan so'ralgan material - material_requests ga yoziladi
    
    MUHIM: Barcha material tanlovlari darhol material_requests ga yoziladi!
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"upsert_material_selection called: user_id={user_id}, application_id={application_id}, material_id={material_id}, qty={qty}, source_type={source_type}")
    
    if qty <= 0:
        raise ValueError("Miqdor 0 dan katta bo'lishi kerak")

    conn = await _conn()
    try:
        async with conn.transaction():
            # Material ma'lumotlarini olish
            material_info = await conn.fetchrow(
                "SELECT name, COALESCE(price, 0) as price FROM materials WHERE id=$1",
                material_id
            )
            if not material_info:
                raise ValueError(f"Material {material_id} topilmadi")
            
            price = material_info['price']
            material_name = material_info['name']
            total = price * qty

            # Texnikda mavjud material uchun tekshirish
            if source_type == 'technician_stock':
                current_qty = await conn.fetchval(
                    """
                    SELECT COALESCE(quantity, 0) 
                    FROM material_and_technician 
                    WHERE user_id = $1 AND material_id = $2
                    """,
                    user_id, material_id
                )
                
                if current_qty is None:
                    raise ValueError(f"Texnikda bu material yo'q")
                
                if current_qty < qty:
                    raise ValueError(
                        f"Texnikda yetarli material yo'q. "
                        f"Mavjud: {current_qty}, Kerak: {qty}"
                    )

            # Get application_number from the order tables
            application_number = await _get_application_number_for_material_issued(conn, application_id, request_type)
            
            if not application_number:
                raise ValueError(f"Application number not found for {request_type} order {application_id}")
            
            # Barcha material tanlovlari uchun material_requests ga DARHOL yozish
            logger.info(f"Writing to material_requests: user_id={user_id}, application_id={application_id}, material_id={material_id}, qty={qty}, price={price}, total={total}, source_type={source_type}, application_number={application_number}")
            
            has_updated_at = await _has_column(conn, "material_requests", "updated_at")
            logger.info(f"has_updated_at column: {has_updated_at}")

            # Check if record exists first - using application_number instead of applications_id
            existing_record = await conn.fetchrow(
                "SELECT id FROM material_requests WHERE user_id = $1 AND application_number = $2 AND material_id = $3",
                user_id, application_number, material_id
            )
            logger.info(f"Existing record: {existing_record}")

            if existing_record:
                # Update existing record - QO'SHISH (qty ni qo'shish)
                logger.info(f"Updating existing record with id: {existing_record['id']} - adding {qty} to existing quantity")
                
                # Avval joriy ma'lumotlarni olish
                current_record = await conn.fetchrow(
                    "SELECT quantity, price FROM material_requests WHERE id = $1",
                    existing_record['id']
                )
                new_quantity = current_record['quantity'] + qty
                new_total = new_quantity * price
                
                if has_updated_at:
                    await conn.execute(
                        """
                        UPDATE material_requests 
                        SET quantity = $1, price = $2, total_price = $3, source_type = $4, 
                            application_number = $5, updated_at = NOW()
                        WHERE id = $6
                        """,
                        new_quantity, price, new_total, source_type, application_number, existing_record['id']
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE material_requests 
                        SET quantity = $1, price = $2, total_price = $3, source_type = $4,
                            application_number = $5
                        WHERE id = $6
                        """,
                        new_quantity, price, new_total, source_type, application_number, existing_record['id']
                    )
                logger.info("Record updated successfully - quantity added")
            else:
                # Insert new record
                logger.info("Inserting new record")
                if has_updated_at:
                    await conn.execute(
                        """
                        INSERT INTO material_requests (user_id, material_id, quantity, price, total_price, source_type, 
                            application_number, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                        """,
                        user_id, material_id, qty, price, total, source_type, application_number
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO material_requests (user_id, material_id, quantity, price, total_price, source_type,
                            application_number)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        user_id, material_id, qty, price, total, source_type, application_number
                    )
                logger.info("Record inserted successfully")

            # Texnikda mavjud materiallar uchun darhol kamaytirish
            if source_type == 'technician_stock':
                await conn.execute(
                    """
                    UPDATE material_and_technician 
                    SET quantity = quantity - $1
                    WHERE user_id = $2 AND material_id = $3
                    """,
                    qty, user_id, material_id
                )
                logger.info(f"Decreased technician stock: material_id={material_id}, qty={qty}")
            elif source_type == 'warehouse':
                # Warehouse materiallari uchun ham texnikda kamaytirish kerak
                # (agar texnikda bu material bo'lsa)
                current_qty = await conn.fetchval(
                    """
                    SELECT COALESCE(quantity, 0) 
                    FROM material_and_technician 
                    WHERE user_id = $1 AND material_id = $2
                    """,
                    user_id, material_id
                )
                
                if current_qty and current_qty > 0:
                    # Texnikda bu material bor, uni kamaytirish
                    await conn.execute(
                        """
                        UPDATE material_and_technician 
                        SET quantity = quantity - $1
                        WHERE user_id = $2 AND material_id = $3
                        """,
                        qty, user_id, material_id
                    )
                    logger.info(f"Decreased technician stock for warehouse material: material_id={material_id}, qty={qty}")
                else:
                    logger.info(f"Warehouse material not in technician stock: material_id={material_id}")

    except asyncpg.UniqueViolationError:
        raise ValueError("Material allaqachon tanlangan. Miqdorni o'zgartirish uchun qayta tanlang.")
    except ValueError as ve:
        # Re-raise validation errors as-is
        raise ve
    except Exception as e:
        # Log error and re-raise with more context
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Material selection upsert failed: {str(e)}")
        raise Exception(f"Material selection upsert failed: {str(e)}")
    finally:
        await conn.close()


async def create_material_issued_from_review(
    user_id: int,
    application_number: str,
    request_type: str
) -> None:
    """
    Yakuniy ko'rinishda (tech_review) barcha tanlangan materiallarni
    material_issued ga yozish
    """
    conn = await _conn()
    try:
        # Fetch all selected materials from material_requests
        selected = await conn.fetch(
            """
            SELECT mr.material_id, mr.quantity, mr.price, mr.source_type,
                   m.name as material_name
            FROM material_requests mr
            JOIN materials m ON m.id = mr.material_id
            WHERE mr.user_id = $1 AND mr.application_number = $2
            """,
            user_id, application_number
        )
        
        # Insert into material_issued for each material
        for mat in selected:
            await _insert_material_issued(
                conn, mat['material_id'], mat['quantity'],
                mat['price'], mat['quantity'] * mat['price'],
                user_id, application_number, request_type,
                mat['material_name']
            )
    finally:
        await conn.close()


async def restore_technician_materials_on_cancel(user_id: int, application_number: str) -> None:
    """
    Ariza bekor qilinganda material tanlovlarini o'chirish.
    - Barcha material tanlovlarini o'chiradi (warehouse va technician_stock)
    - Texnikda mavjud materiallarni qaytaradi
    """
    conn = await _conn()
    try:
        async with conn.transaction():
            # Avval tanlangan materiallarni olish
            selected_materials = await conn.fetch(
                """
                SELECT material_id, quantity, source_type
                FROM material_requests 
                WHERE user_id = $1 AND application_number = $2
                """,
                user_id, application_number
            )
            
            # Texnikda mavjud materiallarni qaytarish
            for material in selected_materials:
                if material['source_type'] == 'technician_stock':
                    await conn.execute(
                        """
                        UPDATE material_and_technician 
                        SET quantity = quantity + $1
                        WHERE user_id = $2 AND material_id = $3
                        """,
                        material['quantity'], user_id, material['material_id']
                    )
            
            # Barcha material tanlovlarini o'chirish
            await conn.execute(
                """
                DELETE FROM material_requests 
                WHERE user_id = $1 AND application_number = $2
                """,
                user_id, application_number
            )
    finally:
        await conn.close()


# Orqa-ward compat: eski nomli funksiya ham shu mantiqqa yo'naltiriladi
async def recover_technician_materials_after_crash() -> None:
    """
    Server qayta ishga tushganda ishlatilmaydi - DISABLED!
    Material_requests qo'yilganda darhol material_and_technician kamayadi.
    Recovery kerak emas!
    """
    # DISABLED - Recovery kerak emas, chunki material_requests yozilganda
    # darhol material_and_technician kamayadi
    pass


async def recover_warehouse_materials_after_crash() -> None:
    """
    Server qayta ishga tushganda ishlatilmaydi - DISABLED!
    Warehouse materials uchun recovery kerak emas.
    """
    # DISABLED - Recovery kerak emas
    pass


async def upsert_material_request_and_decrease_stock(
    user_id: int,
    applications_id: int,
    material_id: int,
    add_qty: int,
    request_type: str = "connection"
) -> None:
    await upsert_material_selection(user_id, applications_id, material_id, add_qty, request_type)


async def fetch_selected_materials_for_request(
    user_id: int,
    application_number: str
) -> list[dict]:
    """
    Tanlangan materiallar ro'yxati.
    UNIQUE constraint tufayli GROUP BY kerak emas.
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT
                mr.material_id,
                m.name,
                COALESCE(m.price, 0) AS price,
                mr.quantity AS qty,
                mr.source_type
            FROM material_requests mr
            JOIN materials m ON m.id = mr.material_id
            WHERE mr.user_id = $1
              AND mr.application_number = $2
            ORDER BY m.name
            """,
            user_id, application_number
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def return_materials_to_technician_stock(
    user_id: int,
    application_number: str
) -> None:
    """
    Ariza bekor qilinganda materiallarni texnik stock'ga qaytarish.
    Faqat technician_stock source_type uchun qaytariladi.
    """
    conn = await _conn()
    try:
        async with conn.transaction():
            # Technician stock materiallarini topish
            technician_materials = await conn.fetch(
                """
                SELECT material_id, quantity
                FROM material_requests 
                WHERE user_id = $1 AND application_number = $2 AND source_type = 'technician_stock'
                """,
                user_id, application_number
            )
            
            # Har bir materialni qaytarish
            for material in technician_materials:
                await conn.execute(
                    """
                    UPDATE material_and_technician 
                    SET quantity = quantity + $1
                    WHERE user_id = $2 AND material_id = $3
                    """,
                    material['quantity'], user_id, material['material_id']
                )
            
            # Warehouse materiallarni ham qaytarish (agar texnikda mavjud bo'lsa)
            warehouse_materials = await conn.fetch(
                """
                SELECT material_id, quantity
                FROM material_requests 
                WHERE user_id = $1 AND application_number = $2 AND source_type = 'warehouse'
                """,
                user_id, application_number
            )
            
            for material in warehouse_materials:
                # Texnikda bu material bor-yo'qligini tekshirish
                current_qty = await conn.fetchval(
                    """
                    SELECT COALESCE(quantity, 0) 
                    FROM material_and_technician 
                    WHERE user_id = $1 AND material_id = $2
                    """,
                    user_id, material['material_id']
                )
                
                if current_qty is not None:
                    # Texnikda bu material bor, qaytarish
                    await conn.execute(
                        """
                        UPDATE material_and_technician 
                        SET quantity = quantity + $1
                        WHERE user_id = $2 AND material_id = $3
                        """,
                        material['quantity'], user_id, material['material_id']
                    )
            
            logger.info(f"Returned materials to technician stock for user_id={user_id}, application_number={application_number}")
            
    finally:
        await conn.close()


# --- Omborga jo'natish: material_requests'ga QAYTA yozmaydi! ---
async def pick_warehouse_user_rr(seed: int) -> int | None:
    """
    Omborchilar orasidan bitta foydalanuvchini round-robin usulida tanlaydi.
    seed odatda applications_id bo'ladi.
    """
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """
            SELECT id
            FROM users
            WHERE role = 'warehouse'
            ORDER BY id
            """
        )
        print(f"DEBUG: Found {len(rows)} warehouse users")
        if not rows:
            print("DEBUG: No warehouse users found!")
            return None
        ids = [r["id"] for r in rows]
        print(f"DEBUG: Warehouse user IDs: {ids}")
        
        # Round-robin logic
        selected_id = ids[seed % len(ids)]
        print(f"DEBUG: Selected warehouse user ID: {selected_id}")
        return selected_id
    finally:
        await conn.close()


async def send_selection_to_warehouse(
    applications_id: int,
    technician_user_id: Optional[int] = None, *,
    technician_id: Optional[int] = None,
    request_type: str = "connection",  # 'connection' | 'technician' | 'staff'
) -> bool:
    """
    Tanlangan materiallarni omborga jo'natish.
    YANGI: Status O'ZGARMAYDI! Faqat connections ga tarix yoziladi.
    Texnik ishni davom ettiradi, omborchi faqat material yetkazib beradi.
    """
    uid = technician_user_id if technician_user_id is not None else technician_id
    if uid is None:
        raise TypeError("send_selection_to_warehouse(): technician_user_id yoki technician_id bering")

    conn = await _conn()
    try:
        async with conn.transaction():
            # STATUS O'ZGARMAYDI! Texnik davom ettiradi.
            # Faqat connections ga tarix yozamiz - omborchi material_requests dan ko'radi
            
            print(f"DEBUG: Picking warehouse user for applications_id={applications_id}")
            warehouse_id = await pick_warehouse_user_rr(applications_id)
            print(f"DEBUG: Selected warehouse_id: {warehouse_id}")
            
            if warehouse_id is not None:
                conn_id  = applications_id if request_type == "connection"  else None
                tech_oid = applications_id if request_type == "technician" else None
                staff_oid = applications_id if request_type == "staff"       else None

                # Get application_number based on request_type
                if request_type == "connection":
                    app_info = await conn.fetchrow("SELECT application_number FROM connection_orders WHERE id = $1", applications_id)
                elif request_type == "technician":
                    app_info = await conn.fetchrow("SELECT application_number FROM technician_orders WHERE id = $1", applications_id)
                elif request_type == "staff":
                    app_info = await conn.fetchrow("SELECT application_number FROM staff_orders WHERE id = $1", applications_id)
                else:
                    app_info = None
                
                app_number = app_info['application_number'] if app_info else None

                await conn.execute(
                    """
                    INSERT INTO connections(
                        application_number,
                        sender_id, recipient_id,
                        connection_id, technician_id, staff_id,
                        sender_status, recipient_status,
                        created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6,
                            'in_technician_work', 'pending_warehouse',
                            NOW(), NOW())
                    """,
                    app_number, uid, warehouse_id, conn_id, tech_oid, staff_oid
                )

            return True
    finally:
        await conn.close()


# ======================= MATERIAL CHECKING AND WAREHOUSE INTEGRATION =======================

async def check_technician_material_availability(user_id: int, material_id: int, required_quantity: int) -> Dict[str, Any]:
    """
    Texnikning materialiga ega ekanligini tekshirish
    Agar yetarli bo'lmasa, ombordan qo'shimcha olish imkoniyatini ko'rsatish
    """
    conn = await _conn()
    try:
        # Texnikning joriy material miqdorini olish
        current_qty = await fetch_assigned_qty(user_id, material_id)
        
        # Ombor material miqdorini olish
        warehouse_qty = await conn.fetchval(
            """
            SELECT COALESCE(quantity, 0) 
            FROM materials 
            WHERE id = $1
            """,
            material_id
        )
        
        # Material ma'lumotlarini olish
        material_info = await fetch_material_by_id(material_id)
        
        result = {
            'material_id': material_id,
            'material_name': material_info['name'] if material_info else 'Unknown',
            'required_quantity': required_quantity,
            'current_quantity': current_qty,
            'warehouse_quantity': warehouse_qty,
            'has_enough': current_qty >= required_quantity,
            'can_get_from_warehouse': warehouse_qty >= (required_quantity - current_qty) if current_qty < required_quantity else True,
            'shortage': max(0, required_quantity - current_qty)
        }
        
        return result
    finally:
        await conn.close()

async def transfer_material_from_warehouse_to_technician(user_id: int, material_id: int, quantity: int) -> bool:
    """
    Ombordan texnikka material o'tkazish
    """
    conn = await _conn()
    try:
        # Transaction boshlash
        async with conn.transaction():
            # Ombordagi material miqdorini tekshirish
            warehouse_qty = await conn.fetchval(
                """
                SELECT COALESCE(quantity, 0) 
                FROM materials 
                WHERE id = $1
                """,
                material_id
            )
            
            if warehouse_qty < quantity:
                print(f"Insufficient warehouse quantity for material {material_id}. Available: {warehouse_qty}, Required: {quantity}")
                return False
            
            # Ombordagi material miqdorini kamaytirish
            await conn.execute(
                """
                UPDATE materials 
                SET quantity = quantity - $2, updated_at = now()
                WHERE id = $1
                """,
                material_id, quantity
            )
            
            # Texnikka material qo'shish (UPSERT)
            await conn.execute(
                """
                INSERT INTO material_and_technician (user_id, material_id, quantity)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, material_id) 
                DO UPDATE SET quantity = material_and_technician.quantity + $3
                """,
                user_id, material_id, quantity
            )
            
            return True
    except Exception as e:
        print(f"Error transferring material from warehouse to technician: {e}")
        return False
    finally:
        await conn.close()

async def get_technician_material_shortage_list(user_id: int, order_materials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Texnikning biror ariza uchun yetishmayotgan materiallar ro'yxatini olish
    """
    shortage_list = []
    
    for material in order_materials:
        material_id = material['material_id']
        required_qty = material['quantity']
        
        availability = await check_technician_material_availability(user_id, material_id, required_qty)
        
        if not availability['has_enough']:
            shortage_list.append(availability)
    
    return shortage_list

# Eski nom bilan chaqirilsa ham yangi mantiqqa yo'naltirish
async def create_material_request_and_mark_in_warehouse(
    applications_id: int,
    technician_user_id: Optional[int] = None, *,
    technician_id: Optional[int] = None,
    material_id: int = 0,
    qty: int = 0,
    request_type: str = "connection",
) -> bool:
    # material_requests ga QAYTA yozmaymiz; tanlov bosqichida upsert_material_selection ishlatiladi.
    uid = technician_user_id if technician_user_id is not None else technician_id
    return await send_selection_to_warehouse(applications_id, technician_user_id=uid, request_type=request_type)
