# database/basic/rating.py

import asyncpg
from typing import Optional, Dict, Any
from config import settings

async def save_rating(request_id: int, request_type: str, rating: int, comment: Optional[str] = None) -> bool:
    """
    Reyting va izohni saqlash.
    
    Args:
        request_id: Ariza IDsi
        request_type: Ariza turi ('connection', 'technician', 'staff')
        rating: Reyting (1-5)
        comment: Izoh (ixtiyoriy)
        
    Returns:
        bool: Muvaffaqiyatli saqlangan bo'lsa True
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Ensure rating is integer and validate parameters
        rating = int(rating)
        
        # Debug: Print parameters
        print(f"DEBUG: Saving rating - request_id: {request_id}, request_type: {request_type}, rating: {rating}, comment: {comment}")
        
        # Validate parameters
        if not isinstance(request_id, int):
            raise ValueError(f"request_id must be int, got {type(request_id)}")
        if not isinstance(request_type, str):
            raise ValueError(f"request_type must be str, got {type(request_type)}")
        if not isinstance(rating, int):
            raise ValueError(f"rating must be int, got {type(rating)}")
        if comment is not None and not isinstance(comment, str):
            raise ValueError(f"comment must be str or None, got {type(comment)}")
        
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
            print(f"DEBUG: No application_number found for request_id {request_id}")
            return False
        
        application_number = app_number_result['application_number']
        
        # Check if rating already exists
        existing = await conn.fetchrow(
            """
            SELECT id FROM akt_ratings 
            WHERE application_number = $1
            """,
            application_number
        )
        
        if existing:
            # Update existing rating
            print(f"DEBUG: Updating existing rating with id: {existing['id']}")
            await conn.execute(
                """
                UPDATE akt_ratings 
                SET rating = $1, comment = $2, updated_at = NOW()
                WHERE id = $3
                """,
                rating, comment, existing['id']
            )
        else:
            # Insert new rating
            print(f"DEBUG: Inserting new rating")
            await conn.execute(
                """
                INSERT INTO akt_ratings (application_number, rating, comment)
                VALUES ($1, $2, $3)
                """,
                application_number, rating, comment
            )
        print(f"DEBUG: Rating saved successfully")
        return True
    except Exception as e:
        print(f"Error saving rating: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

async def get_rating_stats() -> Dict[str, Any]:
    """
    Reyting statistikalarini olish.
    
    Returns:
        Dict: Reyting statistikasi
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        stats = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_ratings,
                AVG(rating) as avg_rating,
                COUNT(CASE WHEN rating = 5 THEN 1 END) as "5_stars",
                COUNT(CASE WHEN rating = 4 THEN 1 END) as "4_stars",
                COUNT(CASE WHEN rating = 3 THEN 1 END) as "3_stars",
                COUNT(CASE WHEN rating = 2 THEN 1 END) as "2_stars",
                COUNT(CASE WHEN rating = 1 THEN 1 END) as "1_stars"
            FROM akt_ratings
            """
        )
        return dict(stats) if stats else {}
    except Exception as e:
        print(f"Error getting rating stats: {e}")
        return {}
    finally:
        await conn.close()

async def get_rating(request_id: int, request_type: str) -> Optional[Dict[str, Any]]:
    """
    Belgilangan ariza uchun reytingni olish.
    
    Args:
        request_id: Ariza IDsi
        request_type: Ariza turi
        
    Returns:
        Dict: Reyting ma'lumotlari yoki None
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
    except Exception as e:
        print(f"Error getting rating: {e}")
        return None
    finally:
        await conn.close()
