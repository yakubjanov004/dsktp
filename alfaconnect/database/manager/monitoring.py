# database/manager/monitoring.py
# Manager roli uchun realtime monitoring queries

from typing import List, Dict, Any, Optional
import asyncpg
from asyncpg.exceptions import UndefinedColumnError
from config import settings
from datetime import datetime, timezone, timedelta

# =========================================================
#  OVERVIEW COUNTS (faqat connection_orders)
# =========================================================

async def get_realtime_counts() -> Dict[str, int]:
    """
    Faol va shoshilinch (24 soatdan oshgan) connection_orders sonlari.
    """
    sql = """
    SELECT
      COUNT(*) FILTER (
        WHERE status <> 'completed'::connection_order_status
          AND is_active = TRUE
      ) AS active_total,
      COUNT(*) FILTER (
         WHERE status <> 'completed'::connection_order_status
           AND is_active = TRUE
           AND now() - created_at > INTERVAL '1 day'
      ) AS urgent_total
    FROM connection_orders;
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(sql)
        active = int(row["active_total"] or 0)
        urgent = int(row["urgent_total"] or 0)
        return {
            "active_total": active,
            "urgent_total": urgent,
            "normal_total": max(active - urgent, 0),
        }
    finally:
        await conn.close()

# =========================================================
#  LISTS for cards (faqat connection_orders)
# =========================================================

def _select_block() -> str:
    # user_id -> users.full_name AS creator_name
    # (UI'da "Yaratgan" sifatida ko'rsatiladi)
    return """
    SELECT
        co.id,
        co.application_number,
        co.created_at,
        co.status::text AS status_text,
        co.address,
        u.full_name AS creator_name
    FROM connection_orders co
    LEFT JOIN users u ON u.id = co.user_id
    WHERE co.is_active = TRUE
      AND co.status <> 'completed'::connection_order_status
    """

async def _list_detailed(limit: int, urgent_only: bool) -> List[Dict[str, Any]]:
    base = _select_block()
    # Shoshilinchlar: eng eski (ko'proq kutgan) oldinda bo'lishi uchun ASC
    order_dir = "ASC" if urgent_only else "DESC"
    where_urgent = " AND (now() - co.created_at > INTERVAL '1 day')" if urgent_only else ""
    sql = f"""
    {base}
    {where_urgent}
    ORDER BY co.created_at {order_dir}, co.id {order_dir}
    LIMIT $1;
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(sql, limit)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def list_active_detailed(limit: int = 50) -> List[Dict[str, Any]]:
    """Faol (completed emas, is_active=TRUE) arizalar."""
    return await _list_detailed(limit=limit, urgent_only=False)

async def list_urgent_detailed(limit: int = 50) -> List[Dict[str, Any]]:
    """Shoshilinch (24 soatdan oshgan) arizalar."""
    return await _list_detailed(limit=limit, urgent_only=True)

# =========================================================
#  WORKFLOW HISTORY (connections jadvalidan)
# =========================================================

def _fmt_duration(delta) -> str:
    """
    Tilga bog'liq bo'lmagan, neytral yozuv (1d 2h 3m).
    Handler umumiy vaqtni o'zi UZ/RU ga moslab formatlaydi.
    """
    if not delta:
        return "—"
    secs = int(delta.total_seconds())
    d, r = divmod(secs, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if not parts: parts.append(f"{s}s")
    return " ".join(parts)

async def get_workflow_history(application_number: str) -> Dict[str, Any]:
    """
    connections jadvalidan berilgan application_number bo'yicha barcha o'tishlar.
    - sender_id/recipient_id -> users.full_name
    - Qadam davomiyligi: keyingi yozuv.created_at - joriy.created_at
    - Tugallanmagan bosqichda end_at = NULL, duration_str = "—" (handler UZ/RU matnini o'zi qo'yadi).
    Barcha order turlarini qo'llab-quvvatlaydi: connection_orders, technician_orders, staff_orders, smart_service_orders
    
    Manager uchun:
    - STAFF-CONN-* → controller logikasi (client_created → in_controller)
    - CONN-* → manager logikasi (client_created → in_manager)
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if not application_number:
            return {"steps": [], "user_times": []}
        
        # Application type aniqlash
        is_staff_conn = application_number.upper().startswith("STAFF-CONN-")
        is_conn = application_number.upper().startswith("CONN-")
        
        # Barcha order turlarini tekshirib, mos connection recordlarni olamiz
        # application_number bo'yicha to'g'ri qidirish - NULL va bo'sh string holatlarini ham tekshiramiz
        sql_all_connections = """
        SELECT c.id,
               c.sender_id, su.full_name AS sender_name, su.role AS sender_role,
               c.recipient_id, ru.full_name AS recipient_name, ru.role AS recipient_role,
               c.sender_status::text AS sender_status,
               c.recipient_status::text AS recipient_status,
               c.created_at,
               'connection' AS order_type
          FROM connections c
          LEFT JOIN users su ON su.id = c.sender_id
          LEFT JOIN users ru ON ru.id = c.recipient_id
         WHERE c.application_number IS NOT NULL 
           AND c.application_number = $1
         ORDER BY c.created_at ASC, c.id ASC;
        """

        rows = await conn.fetch(sql_all_connections, application_number)

        steps: List[Dict[str, Any]] = []
        processed_statuses = set()
        
        # Hash to store time spent by each user
        user_times: Dict[str, Any] = {}  # key: user_id, value: {name, total_seconds, start_time}
        
        for i, r in enumerate(rows):
            start_at = r["created_at"]
            end_at = rows[i + 1]["created_at"] if i + 1 < len(rows) else None
            duration_str = _fmt_duration(end_at - start_at) if end_at else "—"

            # Track time spent by recipient (the person who received the order)
            # Faqat xodimlar uchun (client emas) vaqt hisoblaymiz
            recipient_id = r["recipient_id"]
            recipient_name = r["recipient_name"] or "—"
            recipient_role = r["recipient_role"]
            recipient_status = r["recipient_status"]
            
            # Client uchun vaqt hisoblamaymiz - faqat xodimlar uchun
            # recipient_role "client" bo'lsa yoki recipient_status "client_created" bo'lsa, uni qo'shmaymiz
            is_staff_member = (
                recipient_id and  # recipient_id bo'lishi kerak
                recipient_role and  # role mavjud bo'lishi kerak
                recipient_role.lower() != "client" and  # role client bo'lmasligi kerak
                recipient_role != "—" and  # role "—" bo'lmasligi kerak
                recipient_status and  # status mavjud bo'lishi kerak
                recipient_status != "client_created"  # status client_created bo'lmasligi kerak
            )
            
            if is_staff_member:
                if end_at:
                    time_spent = (end_at - start_at).total_seconds()
                else:
                    # If no end time, calculate from now
                    now = datetime.now(timezone.utc)
                    time_spent = (now - start_at).total_seconds()
                
                if recipient_id:
                    key = str(recipient_id)
                    if key not in user_times:
                        user_times[key] = {
                            "user_id": recipient_id,
                            "name": recipient_name,
                            "total_seconds": 0,
                            "roles": set()
                        }
                    user_times[key]["total_seconds"] += time_spent
                    user_times[key]["roles"].add(recipient_role or "—")

            # CONN arizalar uchun boshidagi bosqichni to'g'rilash
            # Agar CONN bo'lsa va client_created → in_controller bo'lsa, 
            # uni client_created → in_manager sifatida ko'rsatamiz
            actual_sender_status = r["sender_status"]
            actual_recipient_status = r["recipient_status"]
            
            if is_conn and actual_sender_status == "client_created" and actual_recipient_status == "in_controller":
                # CONN arizalar uchun boshida manager ga kelishi kerak
                actual_recipient_status = "in_manager"
            
            status_key = f"{actual_sender_status}_{actual_recipient_status}"
            if status_key in processed_statuses:
                continue
            processed_statuses.add(status_key)

            if actual_sender_status == "client_created":
                from_name = "Mijoz"  # Client
            else:
                from_name = r["sender_name"] or (actual_sender_status or "—")
            
            # Manager uchun to'g'ri nomlar - application_number ga qarab
            if actual_recipient_status == "in_manager":
                to_name = "Manager"
            elif actual_recipient_status == "in_junior_manager":
                to_name = "Junior Manager"
            elif actual_recipient_status == "in_controller":
                # Agar STAFF-CONN bo'lsa → Controller (to'g'ri)
                if is_staff_conn:
                    to_name = "Controller"  # STAFF-CONN uchun controller to'g'ri
                else:
                    # CONN uchun ham in_controller bo'lishi mumkin (keyinroq controller ga o'tganda)
                    to_name = r["recipient_name"] or "Controller"
            elif actual_recipient_status == "in_technician":
                to_name = "Technician"
            elif actual_recipient_status == "in_warehouse":
                to_name = "Warehouse"
            else:
                to_name = r["recipient_name"] or (actual_recipient_status or "—")

            # Application type bo'yicha to'g'ri tavsif
            step_description = _get_step_description_for_manager(
                actual_sender_status, 
                actual_recipient_status, 
                r["order_type"],
                is_staff_conn,
                is_conn
            )

            steps.append({
                "idx": len(steps) + 1,
                "from_name": from_name,
                "to_name": to_name,
                "from_status": actual_sender_status,
                "to_status": actual_recipient_status,
                "start_at": start_at,
                "end_at": end_at,
                "duration_str": duration_str,
                "order_type": r["order_type"],
                "description": step_description
            })

        # Convert user_times to list for display
        user_times_list = []
        for user_id, data in user_times.items():
            # Create a timedelta object for formatting
            time_delta = timedelta(seconds=data["total_seconds"])
            duration_str = _fmt_duration(time_delta)
            
            user_times_list.append({
                "user_id": data["user_id"],
                "name": data["name"],
                "total_seconds": data["total_seconds"],
                "duration_str": duration_str,
                "roles": list(data["roles"])
            })
        
        # Sort by time spent (descending)
        user_times_list.sort(key=lambda x: x["total_seconds"], reverse=True)

        return {"steps": steps, "user_times": user_times_list}
    finally:
        await conn.close()

def _get_step_description_for_manager(
    sender_status: str, 
    recipient_status: str, 
    order_type: str,
    is_staff_conn: bool,
    is_conn: bool
) -> Dict[str, str]:
    """
    Manager uchun workflow qadami tavsifi.
    - STAFF-CONN-* uchun controller logikasi
    - CONN-* uchun manager logikasi
    """
    # Agar STAFF-CONN bo'lsa, controller logikasi
    if is_staff_conn:
        if (sender_status, recipient_status) == ("client_created", "in_controller"):
            return {
                "uz": "Ariza client_created dan in_controller ga o'tkazildi",
                "ru": "Заявка передана с client_created на in_controller"
            }
    
    # Agar CONN bo'lsa, manager logikasi
    if is_conn:
        if (sender_status, recipient_status) == ("client_created", "in_manager"):
            return {
                "uz": "Ariza client_created dan in_manager ga o'tkazildi",
                "ru": "Заявка передана с client_created на in_manager"
            }
    
    # Umumiy tavsiflar
    descriptions = {
        ("client_created", "in_manager"): {
            "uz": "Ariza client_created dan in_manager ga o'tkazildi",
            "ru": "Заявка передана с client_created на in_manager"
        },
        ("client_created", "in_controller"): {
            "uz": "Ariza client_created dan in_controller ga o'tkazildi",
            "ru": "Заявка передана с client_created на in_controller"
        },
        ("in_manager", "in_junior_manager"): {
            "uz": "Ariza in_manager dan in_junior_manager ga o'tkazildi",
            "ru": "Заявка передана с in_manager на in_junior_manager"
        },
        ("in_junior_manager", "in_controller"): {
            "uz": "Ariza in_junior_manager dan in_controller ga o'tkazildi",
            "ru": "Заявка передана с in_junior_manager на in_controller"
        },
        ("in_controller", "in_technician"): {
            "uz": "Kontroller arizani texnik xizmatga topshirdi",
            "ru": "Контроллер передал заявку техническому обслуживанию"
        },
        ("in_technician", "in_warehouse"): {
            "uz": "Texnik xizmat materiallar uchun omborga murojaat qildi",
            "ru": "Техническое обслуживание обратилось на склад за материалами"
        },
        ("in_warehouse", "in_technician"): {
            "uz": "Ombor materiallarni texnik xizmatga yetkazdi",
            "ru": "Склад доставил материалы техническому обслуживанию"
        },
        ("in_technician", "in_controller"): {
            "uz": "Texnik xizmat ishni tugatib kontrollerga qaytardi",
            "ru": "Техническое обслуживание завершило работу и вернуло контроллеру"
        },
        # Controller to Manager
        ("in_controller", "in_manager"): {
            "uz": "Kontroller ishni tugatib menejerga qaytardi",
            "ru": "Контроллер завершил работу и вернул менеджеру"
        },
        # Manager to Client
        ("in_manager", "completed"): {
            "uz": "Menejer ishni tugatdi va mijozga xabar berdi",
            "ru": "Менеджер завершил работу и уведомил клиента"
        },
        # Self-assignment cases
        ("in_manager", "in_manager"): {
            "uz": "Menejer arizani o'ziga qayta tayinladi",
            "ru": "Менеджер переназначил заявку себе"
        },
        ("in_controller", "in_controller"): {
            "uz": "Kontroller arizani o'ziga qayta tayinladi",
            "ru": "Контроллер переназначил заявку себе"
        },
        ("in_technician", "in_technician"): {
            "uz": "Texnik xizmat arizani o'ziga qayta tayinladi",
            "ru": "Техническое обслуживание переназначило заявку себе"
        }
    }
    
    key = (sender_status, recipient_status)
    return descriptions.get(key, {
        "uz": f"Ariza {sender_status} dan {recipient_status} ga o'tkazildi",
        "ru": f"Заявка передана с {sender_status} на {recipient_status}"
    })

# =========================================================
#  Smart Service Orders Monitoring
# =========================================================

async def get_smart_service_realtime_counts() -> Dict[str, int]:
    """
    Smart service orders uchun realtime counts.
    """
    sql = """
    SELECT
      COUNT(*) FILTER (
        WHERE is_active = TRUE
      ) AS active_total,
      COUNT(*) FILTER (
         WHERE is_active = TRUE
           AND now() - created_at > INTERVAL '1 day'
      ) AS urgent_total
    FROM smart_service_orders;
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(sql)
        active = int(row["active_total"] or 0)
        urgent = int(row["urgent_total"] or 0)
        return {
            "active_total": active,
            "urgent_total": urgent,
            "normal_total": max(active - urgent, 0),
        }
    finally:
        await conn.close()

async def list_smart_service_active_detailed(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Faol smart service arizalari.
    """
    sql = """
    SELECT
        sso.id,
        sso.created_at,
        sso.category,
        sso.service_type,
        sso.address,
        sso.latitude,
        sso.longitude,
        u.full_name AS creator_name,
        u.phone AS creator_phone
    FROM smart_service_orders sso
    LEFT JOIN users u ON u.id = sso.user_id
    WHERE sso.is_active = TRUE
    ORDER BY sso.created_at DESC
    LIMIT $1;
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(sql, limit)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# =========================================================
#  Staff Orders Monitoring
# =========================================================

async def get_staff_orders_realtime_counts() -> Dict[str, int]:
    """
    Staff orders uchun realtime counts.
    """
    sql = """
    SELECT
      COUNT(*) FILTER (
        WHERE is_active = TRUE
      ) AS active_total,
      COUNT(*) FILTER (
         WHERE is_active = TRUE
           AND now() - created_at > INTERVAL '1 day'
      ) AS urgent_total
    FROM staff_orders;
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(sql)
        active = int(row["active_total"] or 0)
        urgent = int(row["urgent_total"] or 0)
        return {
            "active_total": active,
            "urgent_total": urgent,
            "normal_total": max(active - urgent, 0),
        }
    finally:
        await conn.close()

async def list_staff_orders_active_detailed(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Faol staff orders arizalari.
    """
    sql = """
    SELECT
        so.id,
        so.created_at,
        so.status::text AS status_text,
        so.type_of_zayavka,
        so.address,
        so.description,
        u.full_name AS creator_name,
        u.phone AS creator_phone,
        client.full_name AS client_name,
        client.phone AS client_phone
    FROM staff_orders so
    LEFT JOIN users u ON u.id = so.user_id
    LEFT JOIN users client ON client.id::text = so.abonent_id
    WHERE so.is_active = TRUE
    ORDER BY so.created_at DESC
    LIMIT $1;
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(sql, limit)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# =========================================================
#  Technician Orders Monitoring
# =========================================================

async def get_technician_orders_realtime_counts() -> Dict[str, int]:
    """
    Technician orders uchun realtime counts.
    """
    sql = """
    SELECT
      COUNT(*) FILTER (
        WHERE is_active = TRUE
      ) AS active_total,
      COUNT(*) FILTER (
         WHERE is_active = TRUE
           AND now() - created_at > INTERVAL '1 day'
      ) AS urgent_total
    FROM technician_orders;
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        row = await conn.fetchrow(sql)
        active = int(row["active_total"] or 0)
        urgent = int(row["urgent_total"] or 0)
        return {
            "active_total": active,
            "urgent_total": urgent,
            "normal_total": max(active - urgent, 0),
        }
    finally:
        await conn.close()

async def list_technician_orders_active_detailed(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Faol technician orders arizalari.
    """
    sql = """
    SELECT
        tech_orders.id,
        tech_orders.created_at,
        tech_orders.status::text AS status_text,
        tech_orders.address,
        tech_orders.description,
        tech_orders.media,
        u.full_name AS creator_name,
        u.phone AS creator_phone,
        client.full_name AS client_name,
        client.phone AS client_phone
    FROM technician_orders tech_orders
    LEFT JOIN users u ON u.id = tech_orders.user_id
    LEFT JOIN users client ON client.id::text = tech_orders.abonent_id
    WHERE tech_orders.is_active = TRUE
    ORDER BY tech_orders.created_at DESC
    LIMIT $1;
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(sql, limit)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# =========================================================
#  Overall Dashboard Statistics
# =========================================================

async def get_overall_dashboard_stats() -> Dict[str, Any]:
    """
    Umumiy dashboard statistikasi - barcha order turlari uchun.
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Connection orders
        connection_stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_active = TRUE AND status <> 'completed') as active,
                COUNT(*) FILTER (WHERE is_active = TRUE AND now() - created_at > INTERVAL '1 day') as urgent
            FROM connection_orders
        """)
        
        # Staff orders
        staff_stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_active = TRUE) as active,
                COUNT(*) FILTER (WHERE is_active = TRUE AND now() - created_at > INTERVAL '1 day') as urgent
            FROM staff_orders
        """)
        
        # Smart service orders
        smart_stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_active = TRUE) as active,
                COUNT(*) FILTER (WHERE is_active = TRUE AND now() - created_at > INTERVAL '1 day') as urgent
            FROM smart_service_orders
        """)
        
        # Technician orders
        technician_stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_active = TRUE) as active,
                COUNT(*) FILTER (WHERE is_active = TRUE AND now() - created_at > INTERVAL '1 day') as urgent
            FROM technician_orders
        """)
        
        return {
            "connection_orders": {
                "total": connection_stats["total"] or 0,
                "active": connection_stats["active"] or 0,
                "urgent": connection_stats["urgent"] or 0,
            },
            "staff_orders": {
                "total": staff_stats["total"] or 0,
                "active": staff_stats["active"] or 0,
                "urgent": staff_stats["urgent"] or 0,
            },
            "smart_service_orders": {
                "total": smart_stats["total"] or 0,
                "active": smart_stats["active"] or 0,
                "urgent": smart_stats["urgent"] or 0,
            },
            "technician_orders": {
                "total": technician_stats["total"] or 0,
                "active": technician_stats["active"] or 0,
                "urgent": technician_stats["urgent"] or 0,
            },
            "overall": {
                "total": (connection_stats["total"] or 0) + (staff_stats["total"] or 0) + 
                        (smart_stats["total"] or 0) + (technician_stats["total"] or 0),
                "active": (connection_stats["active"] or 0) + (staff_stats["active"] or 0) + 
                         (smart_stats["active"] or 0) + (technician_stats["active"] or 0),
                "urgent": (connection_stats["urgent"] or 0) + (staff_stats["urgent"] or 0) + 
                         (smart_stats["urgent"] or 0) + (technician_stats["urgent"] or 0),
            }
        }
    finally:
        await conn.close()
