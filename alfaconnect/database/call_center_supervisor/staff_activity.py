import asyncpg
from typing import List, Dict, Any
from config import settings

async def fetch_callcenter_staff_activity_with_time_filter(time_filter: str = "total") -> List[Dict[str, Any]]:
    """
    Call center supervisor uchun xodimlar faoliyati - vaqt filtri bilan.
    Faqat call center operator va supervisorlarni ko'rsatadi.
    time_filter: 'today', '7days', 'month', 'total'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Vaqt filtri uchun WHERE sharti
        if time_filter == "total":
            staff_time_condition = "TRUE"
            conn_time_condition = "TRUE"
            tech_time_condition = "TRUE"
        else:
            if time_filter == "today":
                time_condition = "created_at >= CURRENT_DATE"
            elif time_filter == "7days":
                time_condition = "created_at >= CURRENT_DATE - INTERVAL '7 days'"
            elif time_filter == "month":
                time_condition = "created_at >= CURRENT_DATE - INTERVAL '30 days'"
            else:
                time_condition = "TRUE"
            staff_time_condition = f"so.{time_condition}"
            conn_time_condition = f"co.{time_condition}"
            tech_time_condition = f"tech_orders.{time_condition}"
        
        # SQL query'ni alohida qilib yozamiz
        if time_filter == "total":
            query = """
            WITH callcenter_connection_stats AS (
                SELECT
                    u.id,
                    u.full_name,
                    u.phone,
                    u.role,
                    u.created_at,
                    -- Orders they created (as user_id) - Connection orders
                    COUNT(CASE WHEN co.user_id = u.id THEN co.id END) as created_conn_orders,
                    COUNT(CASE WHEN co.user_id = u.id AND co.status NOT IN ('cancelled', 'completed') THEN co.id END) as created_conn_active,
                    -- Orders assigned to them through workflow (as recipient) - Connection orders
                    COUNT(CASE WHEN c.recipient_id = u.id AND c.recipient_status IN ('in_call_center_operator', 'in_call_center_supervisor') THEN co.id END) as assigned_conn_orders,
                    COUNT(CASE WHEN c.recipient_id = u.id AND c.recipient_status IN ('in_call_center_operator', 'in_call_center_supervisor') AND co.status NOT IN ('cancelled', 'completed') THEN co.id END) as assigned_conn_active
                FROM users u
                LEFT JOIN connection_orders co ON COALESCE(co.is_active, TRUE) = TRUE
                LEFT JOIN connections c ON c.application_number = co.application_number
                WHERE u.role IN ('callcenter_operator', 'callcenter_supervisor')
                GROUP BY u.id, u.full_name, u.phone, u.role, u.created_at
            ),
            callcenter_technician_stats AS (
                SELECT
                    u.id,
                    -- Orders they created (as user_id) - Technician orders
                    COUNT(CASE WHEN tech_orders.user_id = u.id THEN tech_orders.id END) as created_tech_orders,
                    COUNT(CASE WHEN tech_orders.user_id = u.id AND tech_orders.status NOT IN ('cancelled', 'completed') THEN tech_orders.id END) as created_tech_active,
                    -- Orders assigned to them through workflow (as recipient) - Technician orders
                    COUNT(CASE WHEN c.recipient_id = u.id AND c.recipient_status IN ('in_call_center_operator', 'in_call_center_supervisor') THEN tech_orders.id END) as assigned_tech_orders,
                    COUNT(CASE WHEN c.recipient_id = u.id AND c.recipient_status IN ('in_call_center_operator', 'in_call_center_supervisor') AND tech_orders.status NOT IN ('cancelled', 'completed') THEN tech_orders.id END) as assigned_tech_active
                FROM users u
                LEFT JOIN technician_orders tech_orders ON COALESCE(tech_orders.is_active, TRUE) = TRUE
                LEFT JOIN connections c ON c.application_number = tech_orders.application_number
                WHERE u.role IN ('callcenter_operator', 'callcenter_supervisor')
                GROUP BY u.id
            ),
            callcenter_staff_orders_stats AS (
                SELECT
                    u.id,
                    -- Orders they created (as user_id) - Staff orders
                    COUNT(CASE WHEN so.user_id = u.id THEN so.id END) as created_staff_orders,
                    COUNT(CASE WHEN so.user_id = u.id AND so.status NOT IN ('cancelled', 'completed') THEN so.id END) as created_staff_active,
                    -- Orders assigned to them through workflow (as recipient) - Staff orders
                    COUNT(CASE WHEN c.recipient_id = u.id AND c.recipient_status IN ('in_call_center_operator', 'in_call_center_supervisor') THEN so.id END) as assigned_staff_orders,
                    COUNT(CASE WHEN c.recipient_id = u.id AND c.recipient_status IN ('in_call_center_operator', 'in_call_center_supervisor') AND so.status NOT IN ('cancelled', 'completed') THEN so.id END) as assigned_staff_active
                FROM users u
                LEFT JOIN staff_orders so ON COALESCE(so.is_active, TRUE) = TRUE
                LEFT JOIN connections c ON c.application_number = so.application_number
                WHERE u.role IN ('callcenter_operator', 'callcenter_supervisor')
                GROUP BY u.id
            ),
            callcenter_sent_orders_stats AS (
                SELECT
                    u.id,
                    -- Orders they sent (as sender_id) - Through connections table
                    COUNT(CASE WHEN c.sender_id = u.id AND co.id IS NOT NULL THEN c.id END) as sent_conn_orders,
                    COUNT(CASE WHEN c.sender_id = u.id AND co.id IS NOT NULL AND co.status NOT IN ('cancelled', 'completed') THEN c.id END) as sent_conn_active,
                    COUNT(CASE WHEN c.sender_id = u.id AND tech_orders.id IS NOT NULL THEN c.id END) as sent_tech_orders,
                    COUNT(CASE WHEN c.sender_id = u.id AND tech_orders.id IS NOT NULL AND tech_orders.status NOT IN ('cancelled', 'completed') THEN c.id END) as sent_tech_active,
                    COUNT(CASE WHEN c.sender_id = u.id AND so.id IS NOT NULL THEN c.id END) as sent_staff_orders,
                    COUNT(CASE WHEN c.sender_id = u.id AND so.id IS NOT NULL AND so.status NOT IN ('cancelled', 'completed') THEN c.id END) as sent_staff_active
                FROM users u
                LEFT JOIN connections c ON c.sender_id = u.id
                LEFT JOIN connection_orders co ON co.application_number = c.application_number
                LEFT JOIN technician_orders tech_orders ON tech_orders.application_number = c.application_number
                LEFT JOIN staff_orders so ON so.application_number = c.application_number
                WHERE u.role IN ('callcenter_operator', 'callcenter_supervisor')
                GROUP BY u.id
            )
            SELECT
                ccs.id,
                ccs.full_name,
                ccs.phone,
                ccs.role,
                ccs.created_at,
                (COALESCE(ccs.created_conn_orders, 0) + COALESCE(ccs.assigned_conn_orders, 0) + 
                 COALESCE(cts.created_tech_orders, 0) + COALESCE(cts.assigned_tech_orders, 0) +
                 COALESCE(csos.created_staff_orders, 0) + COALESCE(csos.assigned_staff_orders, 0) +
                 COALESCE(csent.sent_conn_orders, 0) + COALESCE(csent.sent_tech_orders, 0) + COALESCE(csent.sent_staff_orders, 0)) as total_orders,
                (COALESCE(ccs.created_conn_orders, 0) + COALESCE(ccs.assigned_conn_orders, 0) + 
                 COALESCE(csent.sent_conn_orders, 0)) as conn_count,
                (COALESCE(cts.created_tech_orders, 0) + COALESCE(cts.assigned_tech_orders, 0) + 
                 COALESCE(csent.sent_tech_orders, 0)) as tech_count,
                (COALESCE(ccs.created_conn_active, 0) + COALESCE(ccs.assigned_conn_active, 0) + 
                 COALESCE(cts.created_tech_active, 0) + COALESCE(cts.assigned_tech_active, 0) +
                 COALESCE(csos.created_staff_active, 0) + COALESCE(csos.assigned_staff_active, 0) +
                 COALESCE(csent.sent_conn_active, 0) + COALESCE(csent.sent_tech_active, 0) + COALESCE(csent.sent_staff_active, 0)) as active_count,
                -- New detailed counts
                COALESCE(ccs.assigned_conn_orders, 0) as assigned_conn_count,
                COALESCE(ccs.created_conn_orders, 0) as created_conn_count,
                COALESCE(cts.created_tech_orders, 0) as created_tech_count,
                COALESCE(cts.assigned_tech_orders, 0) as assigned_tech_count,
                -- Staff orders they created and assigned
                COALESCE(csos.created_staff_orders, 0) as created_staff_count,
                COALESCE(csos.assigned_staff_orders, 0) as assigned_staff_count,
                -- Orders they sent
                COALESCE(csent.sent_conn_orders, 0) as sent_conn_count,
                COALESCE(csent.sent_tech_orders, 0) as sent_tech_count,
                COALESCE(csent.sent_staff_orders, 0) as sent_staff_count
            FROM callcenter_connection_stats ccs
            LEFT JOIN callcenter_technician_stats cts ON cts.id = ccs.id
            LEFT JOIN callcenter_staff_orders_stats csos ON csos.id = ccs.id
            LEFT JOIN callcenter_sent_orders_stats csent ON csent.id = ccs.id
            ORDER BY total_orders DESC, ccs.full_name
            """
        else:
            # Vaqt filtri bilan query
            query = f"""
            WITH callcenter_connection_stats AS (
                SELECT
                    u.id,
                    u.full_name,
                    u.phone,
                    u.role,
                    u.created_at,
                    -- Orders they created (as user_id) - Connection orders
                    COUNT(CASE WHEN co.user_id = u.id THEN co.id END) as created_conn_orders,
                    COUNT(CASE WHEN co.user_id = u.id AND co.status NOT IN ('cancelled', 'completed') THEN co.id END) as created_conn_active,
                    -- Orders assigned to them through workflow (as recipient) - Connection orders
                    COUNT(CASE WHEN c.recipient_id = u.id AND c.recipient_status IN ('in_call_center_operator', 'in_call_center_supervisor') THEN co.id END) as assigned_conn_orders,
                    COUNT(CASE WHEN c.recipient_id = u.id AND c.recipient_status IN ('in_call_center_operator', 'in_call_center_supervisor') AND co.status NOT IN ('cancelled', 'completed') THEN co.id END) as assigned_conn_active
                FROM users u
                LEFT JOIN connection_orders co ON COALESCE(co.is_active, TRUE) = TRUE
                    AND {conn_time_condition}
                LEFT JOIN connections c ON c.application_number = co.application_number
                WHERE u.role IN ('callcenter_operator', 'callcenter_supervisor')
                GROUP BY u.id, u.full_name, u.phone, u.role, u.created_at
            ),
            callcenter_technician_stats AS (
                SELECT
                    u.id,
                    -- Orders they created (as user_id) - Technician orders
                    COUNT(CASE WHEN tech_orders.user_id = u.id THEN tech_orders.id END) as created_tech_orders,
                    COUNT(CASE WHEN tech_orders.user_id = u.id AND tech_orders.status NOT IN ('cancelled', 'completed') THEN tech_orders.id END) as created_tech_active,
                    -- Orders assigned to them through workflow (as recipient) - Technician orders
                    COUNT(CASE WHEN c.recipient_id = u.id AND c.recipient_status IN ('in_call_center_operator', 'in_call_center_supervisor') THEN tech_orders.id END) as assigned_tech_orders,
                    COUNT(CASE WHEN c.recipient_id = u.id AND c.recipient_status IN ('in_call_center_operator', 'in_call_center_supervisor') AND tech_orders.status NOT IN ('cancelled', 'completed') THEN tech_orders.id END) as assigned_tech_active
                FROM users u
                LEFT JOIN technician_orders tech_orders ON COALESCE(tech_orders.is_active, TRUE) = TRUE
                    AND {tech_time_condition}
                LEFT JOIN connections c ON c.application_number = tech_orders.application_number
                WHERE u.role IN ('callcenter_operator', 'callcenter_supervisor')
                GROUP BY u.id
            ),
            callcenter_staff_orders_stats AS (
                SELECT
                    u.id,
                    -- Orders they created (as user_id) - Staff orders
                    COUNT(CASE WHEN so.user_id = u.id THEN so.id END) as created_staff_orders,
                    COUNT(CASE WHEN so.user_id = u.id AND so.status NOT IN ('cancelled', 'completed') THEN so.id END) as created_staff_active,
                    -- Orders assigned to them through workflow (as recipient) - Staff orders
                    COUNT(CASE WHEN c.recipient_id = u.id AND c.recipient_status IN ('in_call_center_operator', 'in_call_center_supervisor') THEN so.id END) as assigned_staff_orders,
                    COUNT(CASE WHEN c.recipient_id = u.id AND c.recipient_status IN ('in_call_center_operator', 'in_call_center_supervisor') AND so.status NOT IN ('cancelled', 'completed') THEN so.id END) as assigned_staff_active
                FROM users u
                LEFT JOIN staff_orders so ON COALESCE(so.is_active, TRUE) = TRUE
                    AND {staff_time_condition}
                LEFT JOIN connections c ON c.application_number = so.application_number
                WHERE u.role IN ('callcenter_operator', 'callcenter_supervisor')
                GROUP BY u.id
            ),
            callcenter_sent_orders_stats AS (
                SELECT
                    u.id,
                    -- Orders they sent (as sender_id) - Through connections table
                    COUNT(CASE WHEN c.sender_id = u.id AND co.id IS NOT NULL THEN c.id END) as sent_conn_orders,
                    COUNT(CASE WHEN c.sender_id = u.id AND co.id IS NOT NULL AND co.status NOT IN ('cancelled', 'completed') THEN c.id END) as sent_conn_active,
                    COUNT(CASE WHEN c.sender_id = u.id AND tech_orders.id IS NOT NULL THEN c.id END) as sent_tech_orders,
                    COUNT(CASE WHEN c.sender_id = u.id AND tech_orders.id IS NOT NULL AND tech_orders.status NOT IN ('cancelled', 'completed') THEN c.id END) as sent_tech_active,
                    COUNT(CASE WHEN c.sender_id = u.id AND so.id IS NOT NULL THEN c.id END) as sent_staff_orders,
                    COUNT(CASE WHEN c.sender_id = u.id AND so.id IS NOT NULL AND so.status NOT IN ('cancelled', 'completed') THEN c.id END) as sent_staff_active
                FROM users u
                LEFT JOIN connections c ON c.sender_id = u.id
                    AND {staff_time_condition.replace('so.', 'c.')}
                LEFT JOIN connection_orders co ON co.application_number = c.application_number
                LEFT JOIN technician_orders tech_orders ON tech_orders.application_number = c.application_number
                LEFT JOIN staff_orders so ON so.application_number = c.application_number
                WHERE u.role IN ('callcenter_operator', 'callcenter_supervisor')
                GROUP BY u.id
            )
            SELECT
                ccs.id,
                ccs.full_name,
                ccs.phone,
                ccs.role,
                ccs.created_at,
                (COALESCE(ccs.created_conn_orders, 0) + COALESCE(ccs.assigned_conn_orders, 0) + 
                 COALESCE(cts.created_tech_orders, 0) + COALESCE(cts.assigned_tech_orders, 0) +
                 COALESCE(csos.created_staff_orders, 0) + COALESCE(csos.assigned_staff_orders, 0) +
                 COALESCE(csent.sent_conn_orders, 0) + COALESCE(csent.sent_tech_orders, 0) + COALESCE(csent.sent_staff_orders, 0)) as total_orders,
                (COALESCE(ccs.created_conn_orders, 0) + COALESCE(ccs.assigned_conn_orders, 0) + 
                 COALESCE(csent.sent_conn_orders, 0)) as conn_count,
                (COALESCE(cts.created_tech_orders, 0) + COALESCE(cts.assigned_tech_orders, 0) + 
                 COALESCE(csent.sent_tech_orders, 0)) as tech_count,
                (COALESCE(ccs.created_conn_active, 0) + COALESCE(ccs.assigned_conn_active, 0) + 
                 COALESCE(cts.created_tech_active, 0) + COALESCE(cts.assigned_tech_active, 0) +
                 COALESCE(csos.created_staff_active, 0) + COALESCE(csos.assigned_staff_active, 0) +
                 COALESCE(csent.sent_conn_active, 0) + COALESCE(csent.sent_tech_active, 0) + COALESCE(csent.sent_staff_active, 0)) as active_count,
                -- New detailed counts
                COALESCE(ccs.assigned_conn_orders, 0) as assigned_conn_count,
                COALESCE(ccs.created_conn_orders, 0) as created_conn_count,
                COALESCE(cts.created_tech_orders, 0) as created_tech_count,
                COALESCE(cts.assigned_tech_orders, 0) as assigned_tech_count,
                -- Staff orders they created and assigned
                COALESCE(csos.created_staff_orders, 0) as created_staff_count,
                COALESCE(csos.assigned_staff_orders, 0) as assigned_staff_count,
                -- Orders they sent
                COALESCE(csent.sent_conn_orders, 0) as sent_conn_count,
                COALESCE(csent.sent_tech_orders, 0) as sent_tech_count,
                COALESCE(csent.sent_staff_orders, 0) as sent_staff_count
            FROM callcenter_connection_stats ccs
            LEFT JOIN callcenter_technician_stats cts ON cts.id = ccs.id
            LEFT JOIN callcenter_staff_orders_stats csos ON csos.id = ccs.id
            LEFT JOIN callcenter_sent_orders_stats csent ON csent.id = ccs.id
            ORDER BY total_orders DESC, ccs.full_name
            """
        
        rows = await conn.fetch(query)
        return [dict(r) for r in rows]
    finally:
        await conn.close()
