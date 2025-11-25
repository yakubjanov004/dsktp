# utils/completion_notification.py
"""
Ariza yakunlanganda clientga notification yuborish va rating so'rash.
Barcha ariza turlari uchun ishlatiladi.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from database.basic.user import get_user_by_telegram_id
from keyboards.client_buttons import get_rating_keyboard

logger = logging.getLogger(__name__)

async def send_completion_notification_to_client(bot, request_id: int, request_type: str):
    """
    Texnik ishni yakunlagandan so'ng clientga ariza haqida to'liq ma'lumot yuborish va rating so'rash.
    AKT yuborilmaydi - faqat ma'lumot va rating tizimi.
    
    Args:
        bot: Aiogram Bot instance
        request_id: Ariza IDsi
        request_type: Ariza turi ('connection', 'technician', 'staff')
    """
    try:
        # Client ma'lumotlarini olish
        client_data = await get_client_data_for_notification(request_id, request_type)
        if not client_data or not client_data.get('client_telegram_id'):
            logger.warning(f"No client data found for {request_type} request {request_id}")
            return

        client_telegram_id = client_data['client_telegram_id']
        client_lang = client_data.get('client_lang', 'uz')
        
        # Ariza turini til bo'yicha formatlash
        if client_lang == "ru":
            if request_type == "connection":
                order_type_text = "подключения"
            elif request_type == "technician":
                order_type_text = "технической"
            else:
                order_type_text = "сотрудника"
        else:
            if request_type == "connection":
                order_type_text = "ulanish"
            elif request_type == "technician":
                order_type_text = "texnik xizmat"
            else:
                order_type_text = "xodim"

        # Ishlatilgan materiallarni olish
        materials_info = await get_used_materials_info(request_id, request_type, client_lang)
        
        # Diagnostika ma'lumotini olish (texnik xizmat uchun)
        diagnosis_info = await get_diagnosis_info(request_id, request_type, client_lang)

        # Application number ni olish
        app_number = await get_application_number_for_notification(request_id, request_type)
        
        # To'liq ma'lumot bilan notification matnini tayyorlash
        if client_lang == "ru":
            message = (
                "✅ <b>Работа завершена!</b>\n\n"
                f"📋 <b>Заявка {order_type_text}:</b> #{app_number}\n"
                f"📅 <b>Дата завершения:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"👤 <b>Клиент:</b> {client_data.get('client_name', 'N/A')}\n"
                f"📞 <b>Телефон:</b> {client_data.get('client_phone', 'N/A')}\n"
                f"📍 <b>Адрес:</b> {client_data.get('address', 'N/A')}\n\n"
            )
            
            if diagnosis_info:
                message += f"🔧 <b>Выполненные работы:</b>\n{diagnosis_info}\n\n"
            
            if materials_info:
                message += f"📦 <b>Использованные материалы:</b>\n{materials_info}\n\n"
            else:
                message += "📦 <b>Использованные материалы:</b>\n• Материалы не использовались\n\n"
            
            message += (
                "💰 <b>Общая стоимость материалов:</b> " + 
                (await get_total_materials_cost(request_id, request_type, client_lang)) + "\n\n"
                "<i>Пожалуйста, оцените качество нашей работы:</i>"
            )
        else:
            message = (
                "✅ <b>Ish yakunlandi!</b>\n\n"
                f"📋 <b>{order_type_text} arizasi:</b> #{app_number}\n"
                f"📅 <b>Yakunlangan sana:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"👤 <b>Mijoz:</b> {client_data.get('client_name', 'N/A')}\n"
                f"📞 <b>Telefon:</b> {client_data.get('client_phone', 'N/A')}\n"
                f"📍 <b>Manzil:</b> {client_data.get('address', 'N/A')}\n\n"
            )
            
            if diagnosis_info:
                message += f"🔧 <b>Bajarilgan ishlar:</b>\n{diagnosis_info}\n\n"
            
            if materials_info:
                message += f"📦 <b>Ishlatilgan materiallar:</b>\n{materials_info}\n\n"
            else:
                message += "📦 <b>Ishlatilgan materiallar:</b>\n• Materiallar ishlatilmagan\n\n"
            
            message += (
                "💰 <b>Materiallar jami narxi:</b> " + 
                (await get_total_materials_cost(request_id, request_type, client_lang)) + "\n\n"
                "<i>Iltimos, xizmatimizni baholang:</i>"
            )

        # Rating keyboard yaratish
        rating_keyboard = get_rating_keyboard(request_id, request_type)
        
        # Xabarni yuborish
        await bot.send_message(
            chat_id=client_telegram_id,
            text=message,
            parse_mode='HTML',
            reply_markup=rating_keyboard
        )
        
        logger.info(f"Completion notification sent to client {client_telegram_id} for {request_type} request {request_id}")
        
    except Exception as e:
        logger.error(f"Error sending completion notification to client: {e}")
        raise

async def get_client_data_for_notification(request_id: int, request_type: str):
    """
    Client ma'lumotlarini olish notification uchun.
    """
    from database.connections import get_connection_url
    import asyncpg
    
    try:
        conn = await asyncpg.connect(get_connection_url())
        try:
            if request_type == "connection":
                query = """
                    SELECT 
                        u.telegram_id AS client_telegram_id,
                        u.language as client_lang,
                        u.full_name AS client_name,
                        u.phone AS client_phone,
                        co.address
                    FROM connection_orders co
                    LEFT JOIN users u ON u.id = co.user_id
                    WHERE co.id = $1
                """
            elif request_type == "technician":
                query = """
                    SELECT 
                        u.telegram_id AS client_telegram_id,
                        u.language as client_lang,
                        u.full_name AS client_name,
                        u.phone AS client_phone,
                        t.address
                    FROM technician_orders t
                    LEFT JOIN users u ON u.id = t.user_id
                    WHERE t.id = $1
                """
            elif request_type == "staff":
                query = """
                    SELECT 
                        u.telegram_id AS client_telegram_id,
                        u.language as client_lang,
                        u.full_name AS client_name,
                        u.phone AS client_phone,
                        s.address
                    FROM staff_orders s
                    LEFT JOIN users u ON u.id = s.user_id
                    WHERE s.id = $1
                """
            else:
                return None
                
            result = await conn.fetchrow(query, request_id)
            return dict(result) if result else None
            
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Error getting client data: {e}")
        return None

async def get_used_materials_info(request_id: int, request_type: str, client_lang: str = "uz"):
    """
    Ishlatilgan materiallar haqida ma'lumot olish.
    """
    try:
        from database.connections import get_connection_url
        import asyncpg
        
        conn = await asyncpg.connect(get_connection_url())
        try:
            # Application number ni olish
            if request_type == "connection":
                app_number = await conn.fetchval(
                    "SELECT application_number FROM connection_orders WHERE id = $1",
                    request_id
                )
            elif request_type == "technician":
                app_number = await conn.fetchval(
                    "SELECT application_number FROM technician_orders WHERE id = $1",
                    request_id
                )
            elif request_type == "staff":
                app_number = await conn.fetchval(
                    "SELECT application_number FROM staff_orders WHERE id = $1",
                    request_id
                )
            else:
                return ""
            
            if not app_number:
                return "• Hech qanday material ishlatilmagan" if client_lang == "uz" else "• Материалы не использовались"
            
            # Material ma'lumotlarini olish
            query = """
                SELECT 
                    m.name as material_name,
                    mr.quantity,
                    mr.price,
                    mr.source_type,
                    mr.warehouse_approved
                FROM material_requests mr
                JOIN materials m ON m.id = mr.material_id
                WHERE mr.application_number = $1
                ORDER BY mr.created_at
            """
                
            materials = await conn.fetch(query, app_number)
            
            if not materials:
                return "• Hech qanday material ishlatilmagan" if client_lang == "uz" else "• Материалы не использовались"
            
            materials_text = []
            for mat in materials:
                name = mat['material_name'] or "Noma'lum"
                qty = mat['quantity'] or 0
                price = mat['price'] or 0
                total_price = qty * price
                source_type = mat.get('source_type', 'warehouse')
                warehouse_approved = mat.get('warehouse_approved', False)
                
                # Source indicator
                if source_type == 'technician_stock':
                    source_indicator = "🧑‍🔧" if client_lang == "uz" else "🧑‍🔧"
                elif source_type == 'warehouse':
                    if warehouse_approved:
                        source_indicator = "✅" if client_lang == "uz" else "✅"
                    else:
                        source_indicator = "🏢" if client_lang == "uz" else "🏢"
                else:
                    source_indicator = "❓"
                
                if client_lang == "ru":
                    materials_text.append(f"• {name} — {qty} шт. (💰 {_fmt_price_uzs(total_price)} сум) {source_indicator}")
                else:
                    materials_text.append(f"• {name} — {qty} dona (💰 {_fmt_price_uzs(total_price)} so'm) {source_indicator}")
            
            return "\n".join(materials_text)
            
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Error getting materials info: {e}")
        return ""

async def get_diagnosis_info(request_id: int, request_type: str, client_lang: str = "uz"):
    """
    Diagnostika ma'lumotini olish (faqat texnik xizmat uchun).
    """
    try:
        if request_type != "technician":
            return ""
            
        from database.connections import get_connection_url
        import asyncpg
        
        conn = await asyncpg.connect(get_connection_url())
        try:
            query = """
                SELECT description_ish
                FROM technician_orders
                WHERE id = $1 AND description_ish IS NOT NULL AND description_ish != ''
            """
            
            result = await conn.fetchval(query, request_id)
            
            if not result:
                return ""
            
            diagnosis = result.strip()
            if len(diagnosis) > 200:
                diagnosis = diagnosis[:200] + "..."
            
            return diagnosis
            
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Error getting diagnosis info: {e}")
        return ""

async def get_total_materials_cost(request_id: int, request_type: str, client_lang: str = "uz") -> str:
    """
    Materiallar jami narxini olish.
    """
    try:
        from database.connections import get_connection_url
        import asyncpg
        
        conn = await asyncpg.connect(get_connection_url())
        try:
            # Application number ni olish
            if request_type == "connection":
                app_number = await conn.fetchval(
                    "SELECT application_number FROM connection_orders WHERE id = $1",
                    request_id
                )
            elif request_type == "technician":
                app_number = await conn.fetchval(
                    "SELECT application_number FROM technician_orders WHERE id = $1",
                    request_id
                )
            elif request_type == "staff":
                app_number = await conn.fetchval(
                    "SELECT application_number FROM staff_orders WHERE id = $1",
                    request_id
                )
            else:
                return "N/A"
            
            if not app_number:
                return "0 so'm" if client_lang == "uz" else "0 сум"
            
            query = """
                SELECT SUM(total_price) as total_cost
                FROM material_requests
                WHERE application_number = $1
            """
            
            total_cost = await conn.fetchval(query, app_number)
            
            if not total_cost or total_cost == 0:
                return "0 so'm" if client_lang == "uz" else "0 сум"
            
            # Format the cost
            if client_lang == "ru":
                return f"{total_cost:,.0f} сум"
            else:
                return f"{total_cost:,.0f} so'm"
                
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Error getting total materials cost: {e}")
        return "N/A"

async def get_application_number_for_notification(request_id: int, request_type: str) -> str:
    """Get application_number from database for notification"""
    try:
        import asyncpg
        from config import settings
        
        conn = await asyncpg.connect(settings.DB_URL)
        try:
            if request_type == "technician":
                query = """
                    SELECT application_number FROM technician_orders 
                    WHERE id = $1
                """
            elif request_type == "staff":
                query = """
                    SELECT application_number FROM staff_orders 
                    WHERE id = $1
                """
            else:  # connection mode
                query = """
                    SELECT application_number FROM connection_orders 
                    WHERE id = $1
                """
            result = await conn.fetchval(query, request_id)
            return result or str(request_id)
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Error getting application_number for notification: {e}")
        return str(request_id)

def _fmt_price_uzs(val) -> str:
    try:
        s = f"{int(val):,}"
        return s.replace(",", " ")
    except Exception:
        return str(val)

async def ensure_akt_for_all_order_types():
    """
    Barcha ariza turlari uchun AKT yuborishni ta'minlash.
    Bu funksiya barcha joylarda ariza yakunlanganda chaqiriladi.
    """
    # Bu funksiya barcha ariza turlari uchun umumiy AKT yuborishni ta'minlaydi
    # Hozirgi holatda faqat technician va CC operator uchun ishlatiladi
    pass
