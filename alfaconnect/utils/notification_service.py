# utils/notification_service.py

from aiogram import Bot
from typing import Optional, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def _normalize_lang(lang: Optional[str]) -> str:
    v = (lang or "uz").lower()
    return "ru" if v.startswith("ru") else "uz"

def format_order_type_text(order_type: str, lang: Optional[str]) -> str:
    lang = _normalize_lang(lang)
    if lang == "ru":
        if order_type == "connection":
            return "подключения"
        if order_type == "technician":
            return "технической"
        return "сотрудника"
    # uz
    if order_type == "connection":
        return "ulanish"
    if order_type == "technician":
        return "texnik xizmat"
    return "xodim"

def build_transfer_notification(order_type_text: str, application_number: Optional[str], current_load: int, lang: Optional[str]) -> str:
    lang = _normalize_lang(lang)
    app = application_number if (application_number and str(application_number).strip()) else "—"
    if lang == "ru":
        return (
            f"📬 <b>Новая заявка {order_type_text}</b>\n\n"
            f"🆔 {app}\n\n"
            f"📊 Всего: <b>{current_load}</b>\n"
            f"#️⃣ Это <b>{current_load}</b>-я в списке"
        )
    return (
        f"📬 <b>Yangi {order_type_text} arizasi</b>\n\n"
        f"🆔 {app}\n\n"
        f"📊 Jami: <b>{current_load} ta</b>\n"
        f"#️⃣ Bu <b>{current_load}</b>-ariza"
    )

def should_send_notification(
    sender_role: str,
    recipient_role: str,
    sender_id: Optional[int],
    recipient_id: Optional[int],
    creator_id: Optional[int],
) -> bool:
    # Client → Manager/Controller: skip
    if (sender_role or "").lower() == "client" and (recipient_role or "").lower() in {"manager", "controller"}:
        return False
    # Same role rotation: skip
    if (sender_role or "").lower() == (recipient_role or "").lower():
        return False
    # Same person or self-created to self: skip
    if sender_id is not None and recipient_id is not None and sender_id == recipient_id:
        return False
    if creator_id is not None and recipient_id is not None and creator_id == recipient_id:
        return False
    return True

async def send_cross_role_notification(
    bot: Bot,
    *,
    sender_role: str,
    recipient_role: str,
    sender_id: Optional[int],
    recipient_id: Optional[int],
    creator_id: Optional[int],
    recipient_telegram_id: Optional[int],
    application_number: Optional[str],
    order_type: str,  # 'connection' | 'technician' | 'staff'
    current_load: int,
    lang: Optional[str] = "uz",
) -> bool:
    try:
        if not recipient_telegram_id:
            return False
        if not should_send_notification(sender_role, recipient_role, sender_id, recipient_id, creator_id):
            return False

        lang = _normalize_lang(lang)
        order_type_text = format_order_type_text(order_type, lang)
        message = build_transfer_notification(order_type_text, application_number, int(current_load or 0), lang)

        await bot.send_message(
            chat_id=recipient_telegram_id,
            text=message,
            parse_mode="HTML",
        )
        logger.info(
            f"Role-change notification sent to {recipient_telegram_id} | type={order_type} | app={application_number} | load={current_load}"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send cross-role notification: {e}")
        return False

async def send_role_notification(
    bot: Bot,
    recipient_telegram_id: int,
    order_id: str,
    order_type: str,  # 'connection' | 'technician' | 'staff'
    current_load: int,
    lang: str = "uz"
) -> bool:
    """
    Rol o'zgarishida recipient'ga notification yuborish.
    State'ga ta'sir qilmaydi - faqat oddiy xabar yuboradi.
    
    Args:
        bot: Aiogram Bot instance
        recipient_telegram_id: Qabul qiluvchining telegram ID'si
        order_id: Ariza ID'si (masalan: CONN-B2B-0029)
        order_type: Ariza turi
        current_load: Hozirgi yuklama (qancha ariza bor)
        lang: Til (uz/ru)
    
    Returns:
        True - yuborildi, False - xatolik
    """
    try:
        # Ariza turini til bo'yicha formatlash
        if lang == "ru":
            if order_type == "connection":
                order_type_text = "подключения"
            elif order_type == "technician":
                order_type_text = "технической"
            else:
                order_type_text = "сотрудника"
        else:
            if order_type == "connection":
                order_type_text = "ulanish"
            elif order_type == "technician":
                order_type_text = "texnik xizmat"
            else:
                order_type_text = "xodim"
        
        # Notification matnini tayyorlash
        if lang == "ru":
            message = f"📬 <b>Новая заявка {order_type_text}</b>\n\n🆔 {order_id}\n\n📊 У вас теперь <b>{current_load}</b> активных заявок"
        else:
            message = f"📬 <b>Yangi {order_type_text} arizasi</b>\n\n🆔 {order_id}\n\n📊 Sizda yana <b>{current_load}ta</b> ariza bor"
        
        # Xabarni yuborish (state'ga ta'sir qilmaydi)
        await bot.send_message(
            chat_id=recipient_telegram_id,
            text=message,
            parse_mode="HTML"
        )
        
        logger.info(f"Notification sent to {recipient_telegram_id} for order {order_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send notification to {recipient_telegram_id}: {e}")
        return False


async def send_group_notification_for_staff_order(
    bot: Bot,
    order_id: str,
    order_type: str,  # 'connection' | 'technician' | 'staff'
    client_name: str,
    client_phone: str,
    creator_name: str,
    creator_role: str,  # 'junior_manager' | 'manager' | 'controller' | 'call_center' | 'call_center_supervisor'
    region: str,
    address: str,
    tariff_name: str = None,
    description: str = None,  # Texnik xizmat uchun muammo tavsifi
    business_type: str = "B2C"
) -> bool:
    """
    Xodimlar tomonidan yaratilgan arizalar uchun guruhga xabar yuborish.
    Faqat o'zbek tilida yuboriladi.
    
    Args:
        bot: Aiogram Bot instance
        order_id: Ariza ID'si (masalan: STAFF-CONN-B2B-0034)
        order_type: Ariza turi
        client_name: Mijoz ismi
        client_phone: Mijoz telefoni
        creator_name: Ariza yaratgan xodim ismi
        creator_role: Ariza yaratgan xodim roli
        region: Viloyat
        address: Manzil
        tariff_name: Tarif nomi (ixtiyoriy)
        description: Muammo tavsifi (texnik xizmat uchun)
        business_type: Biznes turi (B2C/B2B)
    
    Returns:
        True - yuborildi, False - xatolik
    """
    try:
        from config import settings
        
        logger.info(f"Attempting to send group notification for {order_type} order {order_id}")
        
        if not settings.ZAYAVKA_GROUP_ID:
            logger.warning("ZAYAVKA_GROUP_ID not configured")
            return False
        
        # Ariza turini formatlash
        if order_type == "connection":
            order_type_text = "ulanish"
        elif order_type == "technician":
            order_type_text = "texnik xizmat"
        else:
            order_type_text = "xodim"
        
        # Yaratgan xodim roli
        role_texts = {
            'junior_manager': 'Junior Manager',
            'manager': 'Manager',
            'controller': 'Controller',
            'call_center': 'Call Center',
            'call_center_supervisor': 'Call Center Supervisor'
        }
        
        creator_role_text = role_texts.get(creator_role, creator_role)
        
        # Tarif qismini tayyorlash
        tariff_section = ""
        if tariff_name:
            tariff_section = f"💳 <b>Tarif:</b> {tariff_name}\n"
        
        # Xabar matnini tayyorlash (faqat o'zbek tilida)
        if order_type == "connection":
            message = (
                f"🔌 <b>YANGI ULANISH ARIZASI</b>\n"
                f"👨‍💼 <b>Xodim yaratgan ariza</b>\n"
                f"{'='*30}\n"
                f"🆔 <b>ID:</b> <code>{order_id}</code>\n"
                f"👤 <b>Mijoz:</b> {client_name}\n"
                f"📞 <b>Tel:</b> {client_phone}\n"
                f"👨‍💼 <b>Yaratdi:</b> {creator_name} ({creator_role_text})\n"
                f"🏢 <b>Region:</b> {region}\n"
                f"{tariff_section}"
                f"📍 <b>Manzil:</b> {address}\n"
                f"🕐 <b>Vaqt:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"{'='*30}"
            )
        elif order_type == "technician":
            # Muammo qismini tayyorlash
            problem_section = ""
            if description:
                problem_section = f"🔧 <b>Muammo:</b> {description}\n"
            
            message = (
                f"🔧 <b>YANGI TEKNIK XIZMAT ARIZASI</b>\n"
                f"👨‍💼 <b>Xodim yaratgan ariza</b>\n"
                f"{'='*30}\n"
                f"🆔 <b>ID:</b> <code>{order_id}</code>\n"
                f"👤 <b>Mijoz:</b> {client_name}\n"
                f"📞 <b>Tel:</b> {client_phone}\n"
                f"👨‍💼 <b>Yaratdi:</b> {creator_name} ({creator_role_text})\n"
                f"🏢 <b>Region:</b> {region}\n"
                f"{problem_section}"
                f"📍 <b>Manzil:</b> {address}\n"
                f"🕐 <b>Vaqt:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"{'='*30}"
            )
        else:
            message = (
                f"👥 <b>YANGI XODIM ARIZASI</b>\n"
                f"👨‍💼 <b>Xodim yaratgan ariza</b>\n"
                f"{'='*30}\n"
                f"🆔 <b>ID:</b> <code>{order_id}</code>\n"
                f"👤 <b>Mijoz:</b> {client_name}\n"
                f"📞 <b>Tel:</b> {client_phone}\n"
                f"👨‍💼 <b>Yaratdi:</b> {creator_name} ({creator_role_text})\n"
                f"🏢 <b>Region:</b> {region}\n"
                f"📍 <b>Manzil:</b> {address}\n"
                f"🕐 <b>Vaqt:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"{'='*30}"
            )
        
        # Xabarni guruhga yuborish
        logger.info(f"Sending message to group {settings.ZAYAVKA_GROUP_ID}")
        await bot.send_message(
            chat_id=settings.ZAYAVKA_GROUP_ID,
            text=message,
            parse_mode="HTML"
        )
        
        logger.info(f"Group notification sent for staff order {order_id} created by {creator_role}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send group notification for staff order {order_id}: {e}")
        return False


async def get_recipient_load(
    recipient_id: int,
    role: str,
    order_type: str = "connection"
) -> int:
    """
    Recipient'ning hozirgi yuklamasini olish.
    
    Args:
        recipient_id: User database ID
        role: User roli (junior_manager, controller, technician)
        order_type: Ariza turi
    
    Returns:
        Aktiv arizalar soni
    """
    from database.connections import get_connection_url
    import asyncpg
    
    try:
        conn = await asyncpg.connect(get_connection_url())
        try:
            if role == "junior_manager":
                # Junior manager uchun connection_orders hisoblaymiz
                count = await conn.fetchval(
                    """
                    WITH last_assign AS (
                        SELECT DISTINCT ON (c.application_number)
                               c.application_number,
                               c.recipient_id,
                               c.recipient_status
                        FROM connections c
                        WHERE c.application_number IS NOT NULL
                        ORDER BY c.application_number, c.created_at DESC
                    )
                    SELECT COUNT(*)
                    FROM last_assign la
                    JOIN connection_orders co ON co.application_number = la.application_number
                    WHERE la.recipient_id = $1
                      AND co.is_active = TRUE
                      AND co.status = 'in_junior_manager'
                      AND la.recipient_status = 'in_junior_manager'
                    """,
                    recipient_id
                )
            elif role == "controller":
                # Controller uchun staff_orders hisoblaymiz
                count = await conn.fetchval(
                    """
                    WITH last_assign AS (
                        SELECT DISTINCT ON (c.application_number)
                               c.application_number,
                               c.recipient_id,
                               c.recipient_status
                        FROM connections c
                        WHERE c.application_number IS NOT NULL
                        ORDER BY c.application_number, c.created_at DESC
                    )
                    SELECT COUNT(*)
                    FROM last_assign la
                    JOIN staff_orders so ON so.application_number = la.application_number
                    WHERE la.recipient_id = $1
                      AND COALESCE(so.is_active, TRUE) = TRUE
                      AND so.status = 'in_controller'
                      AND la.recipient_status = 'in_controller'
                    """,
                    recipient_id
                )
            elif role == "technician":
                # Technician uchun barcha turdagi arizalarni hisoblaymiz
                count = await conn.fetchval(
                    """
                    WITH connection_loads AS (
                        SELECT COUNT(*) AS cnt
                        FROM connection_orders co
                        WHERE co.status IN ('between_controller_technician', 'in_technician')
                          AND co.is_active = TRUE
                          AND EXISTS (
                              SELECT 1 FROM connections c
                              WHERE c.application_number = co.application_number
                                AND c.recipient_id = $1
                                AND c.recipient_status IN ('between_controller_technician', 'in_technician')
                          )
                    ),
                    technician_loads AS (
                        SELECT COUNT(*) AS cnt
                        FROM technician_orders to_orders
                        WHERE to_orders.status IN ('between_controller_technician', 'in_technician')
                          AND COALESCE(to_orders.is_active, TRUE) = TRUE
                          AND EXISTS (
                              SELECT 1 FROM connections c
                              WHERE c.application_number = to_orders.application_number
                                AND c.recipient_id = $1
                                AND c.recipient_status IN ('between_controller_technician', 'in_technician')
                          )
                    ),
                    staff_loads AS (
                        SELECT COUNT(*) AS cnt
                        FROM staff_orders so
                        WHERE so.status IN ('between_controller_technician', 'in_technician')
                          AND COALESCE(so.is_active, TRUE) = TRUE
                          AND EXISTS (
                              SELECT 1 FROM connections c
                              WHERE c.application_number = so.application_number
                                AND c.recipient_id = $1
                                AND c.recipient_status IN ('between_controller_technician', 'in_technician')
                          )
                    )
                    SELECT 
                        COALESCE((SELECT cnt FROM connection_loads), 0) +
                        COALESCE((SELECT cnt FROM technician_loads), 0) +
                        COALESCE((SELECT cnt FROM staff_loads), 0) AS total_load
                    """,
                    recipient_id
                )
            else:
                return 0
            
            return count or 0
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to get recipient load: {e}")
        return 0

