# database/akt_queries.py
"""
AKT hujjatlari bilan ishlash uchun database query funksiyalari
"""

import asyncpg
from typing import Dict, Any, List, Optional
from config import settings
from datetime import datetime

async def get_akt_data_by_request_id(request_id: int, request_type: str) -> Optional[Dict[str, Any]]:
    """
    AKT yaratish uchun kerakli ma'lumotlarni olish.
    Barcha ariza turlari uchun umumiy funksiya.
    
    Args:
        request_id: Ariza IDsi
        request_type: Ariza turi ('connection', 'technician', 'staff')
        
    Returns:
        Dict: AKT uchun kerakli ma'lumotlar yoki None
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if request_type == 'connection':
            return await _get_connection_akt_data(conn, request_id)
        elif request_type == 'technician':
            return await _get_technician_akt_data(conn, request_id)
        elif request_type == 'staff':
            return await _get_staff_akt_data(conn, request_id)
        else:
            return None
    finally:
        await conn.close()

async def _get_connection_akt_data(conn, request_id: int) -> Optional[Dict[str, Any]]:
    """Connection order uchun AKT ma'lumotlari"""
    row = await conn.fetchrow(
        """
        SELECT 
            co.id,
            co.application_number,
            co.address,
            co.region,
            co.created_at,
            co.updated_at,
            
            -- Client ma'lumotlari
            u.full_name AS client_name,
            u.phone AS client_phone,
            u.telegram_id AS client_telegram_id,
            u.language AS client_lang,
            
            -- Tarif ma'lumotlari
            t.name AS tariff_name,
            
            -- Texnik ma'lumotlari (agar mavjud bo'lsa)
            tech.full_name AS technician_name
            
        FROM connection_orders co
        LEFT JOIN users u ON u.id = co.user_id
        LEFT JOIN tarif t ON t.id = co.tarif_id
        LEFT JOIN users tech ON tech.id = (
            SELECT c.recipient_id 
            FROM connections c 
            WHERE c.application_number = co.application_number 
            AND c.recipient_id IN (
                SELECT id FROM users WHERE role = 'technician'
            )
            LIMIT 1
        )
        WHERE co.id = $1 AND co.is_active = TRUE
        """,
        request_id
    )
    return dict(row) if row else None

async def _get_technician_akt_data(conn, request_id: int) -> Optional[Dict[str, Any]]:
    """Technician order uchun AKT ma'lumotlari"""
    row = await conn.fetchrow(
        """
        SELECT 
            t.id,
            t.application_number,
            t.address,
            t.region,
            t.description,
            t.description_ish AS diagnostics,
            t.created_at,
            t.updated_at,
            
            -- Client ma'lumotlari
            u.full_name AS client_name,
            u.phone AS client_phone,
            u.telegram_id AS client_telegram_id,
            u.language AS client_lang,
            
            -- Texnik ma'lumotlari
            tech.full_name AS technician_name
            
        FROM technician_orders t
        LEFT JOIN users u ON u.id = t.user_id
        LEFT JOIN users tech ON tech.id = (
            SELECT c.recipient_id 
            FROM connections c 
            WHERE c.application_number = t.application_number 
            AND c.recipient_id IN (
                SELECT id FROM users WHERE role = 'technician'
            )
            LIMIT 1
        )
        WHERE t.id = $1 AND t.is_active = TRUE
        """,
        request_id
    )
    return dict(row) if row else None

async def _get_staff_akt_data(conn, request_id: int) -> Optional[Dict[str, Any]]:
    """Staff order uchun AKT ma'lumotlari"""
    row = await conn.fetchrow(
        """
        SELECT 
            so.id,
            so.application_number,
            so.address,
            so.region,
            so.description,
            so.created_at,
            so.updated_at,
            
            -- Client ma'lumotlari
            u.full_name AS client_name,
            u.phone AS client_phone,
            u.telegram_id AS client_telegram_id,
            u.language AS client_lang,
            
            -- Tarif ma'lumotlari (agar connection turi bo'lsa)
            t.name AS tariff_name,
            
            -- Texnik ma'lumotlari
            tech.full_name AS technician_name
            
        FROM staff_orders so
        LEFT JOIN users u ON u.id = so.user_id
        LEFT JOIN tarif t ON t.id = so.tarif_id
        LEFT JOIN users tech ON tech.id = (
            SELECT c.recipient_id 
            FROM connections c 
            WHERE c.application_number = so.application_number 
            AND c.recipient_id IN (
                SELECT id FROM users WHERE role = 'technician'
            )
            LIMIT 1
        )
        WHERE so.id = $1 AND so.is_active = TRUE
        """,
        request_id
    )
    return dict(row) if row else None

async def get_materials_for_akt(request_id: int, request_type: str) -> List[Dict[str, Any]]:
    """
    AKT uchun ishlatilgan materiallarni olish.
    material_issued jadvalidan olinadi (yakuniy ishlatilgan materiallar).
    
    Args:
        request_id: Ariza IDsi
        request_type: Ariza turi
        
    Returns:
        List: Materiallar ro'yxati
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Avval application_number ni olish
        app_number_query = """
            SELECT application_number FROM technician_orders WHERE id = $1
            UNION ALL
            SELECT application_number FROM connection_orders WHERE id = $1
            UNION ALL
            SELECT application_number FROM staff_orders WHERE id = $1
            LIMIT 1
        """
        
        app_number_result = await conn.fetchrow(app_number_query, request_id)
        if not app_number_result:
            return []
        
        application_number = app_number_result['application_number']
        
        # material_issued jadvalidan olish (yakuniy ishlatilgan materiallar)
        materials = await conn.fetch(
            """
            SELECT 
                material_name,
                quantity,
                price,
                total_price,
                material_unit AS unit
            FROM material_issued
            WHERE request_type = $1 
              AND application_number = $2
            ORDER BY created_at
            """,
            request_type, application_number
        )
            
        return [dict(m) for m in materials]
    finally:
        await conn.close()

async def get_rating_for_akt(request_id: int, request_type: str) -> Optional[Dict[str, Any]]:
    """
    AKT uchun client rating va komentini olish.
    
    Args:
        request_id: Ariza IDsi
        request_type: Ariza turi
        
    Returns:
        Dict: Rating ma'lumotlari yoki None
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Get application_number from the order tables
        app_number_query = """
            SELECT application_number FROM technician_orders WHERE id = $1
            UNION ALL
            SELECT application_number FROM connection_orders WHERE id = $1
            UNION ALL
            SELECT application_number FROM staff_orders WHERE id = $1
            LIMIT 1
        """
        app_number_result = await conn.fetchrow(app_number_query, request_id)
        if not app_number_result:
            return None
        
        application_number = app_number_result['application_number']
        
        rating = await conn.fetchrow(
            """
            SELECT rating, comment, created_at
            FROM akt_ratings
            WHERE application_number = $1
            """,
            application_number
        )
        return dict(rating) if rating else None
    finally:
        await conn.close()

async def create_akt_document(request_id: int, request_type: str, akt_number: str, file_path: str, file_hash: str) -> bool:
    """
    AKT hujjatini database'ga saqlash.
    
    Args:
        request_id: Ariza IDsi
        request_type: Ariza turi
        akt_number: AKT raqami
        file_path: Fayl yo'li
        file_hash: Fayl hash
        
    Returns:
        bool: Muvaffaqiyatli saqlangan bo'lsa True
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Get application_number from the order tables
        app_number_query = """
            SELECT application_number FROM technician_orders WHERE id = $1
            UNION ALL
            SELECT application_number FROM connection_orders WHERE id = $1
            UNION ALL
            SELECT application_number FROM staff_orders WHERE id = $1
            LIMIT 1
        """
        app_number_result = await conn.fetchrow(app_number_query, request_id)
        if not app_number_result:
            print(f"Error: No application_number found for request_id {request_id}")
            return False
        
        application_number = app_number_result['application_number']
        
        # First check if document already exists
        existing = await conn.fetchrow(
            """
            SELECT id FROM akt_documents 
            WHERE application_number = $1
            """,
            application_number
        )
        
        if existing:
            # Update existing document
            await conn.execute(
                """
                UPDATE akt_documents 
                SET akt_number = $1, file_path = $2, file_hash = $3, updated_at = NOW()
                WHERE id = $4
                """,
                akt_number, file_path, file_hash, existing['id']
            )
        else:
            # Insert new document
            await conn.execute(
                """
                INSERT INTO akt_documents (application_number, akt_number, file_path, file_hash, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                """,
                application_number, akt_number, file_path, file_hash
            )
        return True
    except Exception as e:
        print(f"Error creating AKT document: {e}")
        return False
    finally:
        await conn.close()

async def mark_akt_sent(request_id: int, request_type: str, sent_at: datetime) -> bool:
    """
    AKT yuborilganini belgilash.
    
    Args:
        request_id: Ariza IDsi
        request_type: Ariza turi
        sent_at: Yuborilgan vaqt
        
    Returns:
        bool: Muvaffaqiyatli yangilangan bo'lsa True
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Get application_number from the order tables
        app_number_query = """
            SELECT application_number FROM technician_orders WHERE id = $1
            UNION ALL
            SELECT application_number FROM connection_orders WHERE id = $1
            UNION ALL
            SELECT application_number FROM staff_orders WHERE id = $1
            LIMIT 1
        """
        app_number_result = await conn.fetchrow(app_number_query, request_id)
        if not app_number_result:
            print(f"Error: No application_number found for request_id {request_id}")
            return False
        
        application_number = app_number_result['application_number']
        
        await conn.execute(
            """
            UPDATE akt_documents 
            SET sent_to_client_at = $2, updated_at = NOW()
            WHERE application_number = $1
            """,
            application_number, sent_at
        )
        return True
    except Exception as e:
        print(f"Error marking AKT as sent: {e}")
        return False
    finally:
        await conn.close()

async def check_akt_exists(request_id: int, request_type: str) -> bool:
    """
    AKT mavjudligini tekshirish.
    
    Args:
        request_id: Ariza IDsi
        request_type: Ariza turi
        
    Returns:
        bool: AKT mavjud bo'lsa True
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Get application_number from the order tables
        app_number_query = """
            SELECT application_number FROM technician_orders WHERE id = $1
            UNION ALL
            SELECT application_number FROM connection_orders WHERE id = $1
            UNION ALL
            SELECT application_number FROM staff_orders WHERE id = $1
            LIMIT 1
        """
        app_number_result = await conn.fetchrow(app_number_query, request_id)
        if not app_number_result:
            return False
        
        application_number = app_number_result['application_number']
        
        result = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM akt_documents 
                WHERE application_number = $1
            )
            """,
            application_number
        )
        return bool(result)
    finally:
        await conn.close()
