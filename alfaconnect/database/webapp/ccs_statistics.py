"""
CCS (Call Center System) Statistics Queries
Real-time statistics for CCO and clients
"""
import asyncpg
from typing import Dict, Any, List, Optional
from config import settings
from datetime import datetime, timedelta


async def get_ccs_comprehensive_statistics() -> Dict[str, Any]:
    """
    CCS uchun to'liq statistika:
    - Operatorlar ro'yxati (online status, last seen, answered chats)
    - Clientlar ro'yxati (online status, last seen)
    - Umumiy statistika
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Operatorlar statistikasi
        operators = await conn.fetch(
            """
            SELECT 
                u.id,
                u.telegram_id,
                u.full_name,
                u.username,
                u.phone,
                u.role,
                u.is_online,
                u.last_seen_at,
                u.created_at,
                -- Faol chatlar soni (hozir operator_id = u.id va status = 'active')
                COALESCE(active_chats.cnt, 0) as active_chats_count,
                -- Jami javob berilgan chatlar (operator_id = u.id bo'lgan barcha chatlar)
                COALESCE(total_chats.cnt, 0) as total_answered_chats,
                -- Bugun javob berilgan chatlar
                COALESCE(today_chats.cnt, 0) as today_answered_chats,
                -- Oxirgi hafta javob berilgan chatlar
                COALESCE(week_chats.cnt, 0) as week_answered_chats,
                -- Jami yuborilgan xabarlar soni
                COALESCE(messages.cnt, 0) as total_messages_sent
            FROM users u
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as cnt 
                FROM chats 
                WHERE operator_id = u.id AND status = 'active'
            ) active_chats ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(DISTINCT id) as cnt 
                FROM chats 
                WHERE operator_id = u.id
            ) total_chats ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(DISTINCT id) as cnt 
                FROM chats 
                WHERE operator_id = u.id 
                  AND DATE(created_at) = CURRENT_DATE
            ) today_chats ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(DISTINCT id) as cnt 
                FROM chats 
                WHERE operator_id = u.id 
                  AND created_at >= NOW() - INTERVAL '7 days'
            ) week_chats ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as cnt 
                FROM messages 
                WHERE sender_id = u.id AND sender_type = 'operator'
            ) messages ON TRUE
            WHERE u.role IN ('callcenter_operator', 'callcenter_supervisor')
              AND COALESCE(u.is_blocked, FALSE) = FALSE
            ORDER BY u.is_online DESC NULLS LAST, u.last_seen_at DESC NULLS LAST, u.full_name
            """
        )
        
        # Clientlar statistikasi (oxirgi faol 100 ta)
        clients = await conn.fetch(
            """
            SELECT 
                u.id,
                u.telegram_id,
                u.full_name,
                u.username,
                u.phone,
                u.role,
                u.is_online,
                u.last_seen_at,
                u.created_at,
                u.region,
                u.abonent_id,
                -- Faol chatlar soni
                COALESCE(active_chats.cnt, 0) as active_chats_count,
                -- Jami chatlar soni
                COALESCE(total_chats.cnt, 0) as total_chats_count,
                -- Oxirgi chat vaqti
                last_chat.last_chat_at
            FROM users u
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as cnt 
                FROM chats 
                WHERE client_id = u.id AND status = 'active'
            ) active_chats ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as cnt 
                FROM chats 
                WHERE client_id = u.id
            ) total_chats ON TRUE
            LEFT JOIN LATERAL (
                SELECT MAX(created_at) as last_chat_at
                FROM chats 
                WHERE client_id = u.id
            ) last_chat ON TRUE
            WHERE u.role = 'client'
              AND COALESCE(u.is_blocked, FALSE) = FALSE
            ORDER BY u.is_online DESC NULLS LAST, u.last_seen_at DESC NULLS LAST
            LIMIT 100
            """
        )
        
        # Umumiy statistika
        overview = await conn.fetchrow(
            """
            SELECT
                -- Operatorlar
                (SELECT COUNT(*) FROM users WHERE role = 'callcenter_operator' AND COALESCE(is_blocked, FALSE) = FALSE) as total_operators,
                (SELECT COUNT(*) FROM users WHERE role = 'callcenter_operator' AND is_online = TRUE AND COALESCE(is_blocked, FALSE) = FALSE) as online_operators,
                -- Supervisorlar
                (SELECT COUNT(*) FROM users WHERE role = 'callcenter_supervisor' AND COALESCE(is_blocked, FALSE) = FALSE) as total_supervisors,
                (SELECT COUNT(*) FROM users WHERE role = 'callcenter_supervisor' AND is_online = TRUE AND COALESCE(is_blocked, FALSE) = FALSE) as online_supervisors,
                -- Clientlar
                (SELECT COUNT(*) FROM users WHERE role = 'client') as total_clients,
                (SELECT COUNT(*) FROM users WHERE role = 'client' AND is_online = TRUE) as online_clients,
                -- Chatlar
                (SELECT COUNT(*) FROM chats WHERE status = 'active') as active_chats,
                (SELECT COUNT(*) FROM chats WHERE status = 'active' AND operator_id IS NULL) as inbox_chats,
                (SELECT COUNT(*) FROM chats WHERE status = 'active' AND operator_id IS NOT NULL) as assigned_chats,
                -- Bugungi chatlar
                (SELECT COUNT(*) FROM chats WHERE DATE(created_at) = CURRENT_DATE) as today_chats,
                -- Haftalik chatlar
                (SELECT COUNT(*) FROM chats WHERE created_at >= NOW() - INTERVAL '7 days') as week_chats,
                -- Oylik chatlar
                (SELECT COUNT(*) FROM chats WHERE created_at >= NOW() - INTERVAL '30 days') as month_chats,
                -- Xabarlar
                (SELECT COUNT(*) FROM messages WHERE DATE(created_at) = CURRENT_DATE) as today_messages,
                (SELECT COUNT(*) FROM messages WHERE created_at >= NOW() - INTERVAL '7 days') as week_messages
            """
        )
        
        # Kunlik trend (oxirgi 7 kun)
        daily_trends = await conn.fetch(
            """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as total_chats,
                COUNT(CASE WHEN operator_id IS NOT NULL THEN 1 END) as answered_chats,
                COUNT(CASE WHEN status = 'inactive' THEN 1 END) as closed_chats
            FROM chats
            WHERE created_at >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            """
        )
        
        return {
            'operators': [dict(r) for r in operators],
            'clients': [dict(r) for r in clients],
            'overview': dict(overview) if overview else {},
            'daily_trends': [dict(r) for r in daily_trends]
        }
    finally:
        await conn.close()


async def get_operator_statistics(operator_id: int) -> Dict[str, Any]:
    """
    Bitta operator uchun batafsil statistika
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Operator ma'lumotlari
        operator = await conn.fetchrow(
            """
            SELECT 
                u.id,
                u.telegram_id,
                u.full_name,
                u.username,
                u.phone,
                u.role,
                u.is_online,
                u.last_seen_at,
                u.created_at
            FROM users u
            WHERE u.id = $1
            """,
            operator_id
        )
        
        if not operator:
            return None
        
        # Statistikalar
        stats = await conn.fetchrow(
            """
            SELECT
                -- Faol chatlar
                (SELECT COUNT(*) FROM chats WHERE operator_id = $1 AND status = 'active') as active_chats,
                -- Jami javob berilgan chatlar
                (SELECT COUNT(DISTINCT id) FROM chats WHERE operator_id = $1) as total_answered_chats,
                -- Bugun
                (SELECT COUNT(*) FROM chats WHERE operator_id = $1 AND DATE(created_at) = CURRENT_DATE) as today_chats,
                -- Hafta
                (SELECT COUNT(*) FROM chats WHERE operator_id = $1 AND created_at >= NOW() - INTERVAL '7 days') as week_chats,
                -- Oy
                (SELECT COUNT(*) FROM chats WHERE operator_id = $1 AND created_at >= NOW() - INTERVAL '30 days') as month_chats,
                -- Jami xabarlar
                (SELECT COUNT(*) FROM messages WHERE sender_id = $1 AND sender_type = 'operator') as total_messages,
                -- Bugungi xabarlar
                (SELECT COUNT(*) FROM messages WHERE sender_id = $1 AND sender_type = 'operator' AND DATE(created_at) = CURRENT_DATE) as today_messages
            """,
            operator_id
        )
        
        # Kunlik trend (oxirgi 7 kun)
        daily = await conn.fetch(
            """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as chats_handled
            FROM chats
            WHERE operator_id = $1 AND created_at >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            """,
            operator_id
        )
        
        return {
            'operator': dict(operator),
            'statistics': dict(stats) if stats else {},
            'daily_activity': [dict(r) for r in daily]
        }
    finally:
        await conn.close()


async def get_online_users_summary() -> Dict[str, Any]:
    """
    Online userlar haqida qisqacha ma'lumot (WebSocket uchun)
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        result = await conn.fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM users WHERE role = 'callcenter_operator' AND is_online = TRUE AND COALESCE(is_blocked, FALSE) = FALSE) as online_operators,
                (SELECT COUNT(*) FROM users WHERE role = 'callcenter_supervisor' AND is_online = TRUE AND COALESCE(is_blocked, FALSE) = FALSE) as online_supervisors,
                (SELECT COUNT(*) FROM users WHERE role = 'client' AND is_online = TRUE) as online_clients,
                (SELECT COUNT(*) FROM chats WHERE status = 'active' AND operator_id IS NULL) as inbox_count,
                (SELECT COUNT(*) FROM chats WHERE status = 'active' AND operator_id IS NOT NULL) as assigned_count
            """
        )
        
        # Online userlar ro'yxati
        online_users = await conn.fetch(
            """
            SELECT id, role
            FROM users
            WHERE is_online = TRUE
            """
        )
        
        return {
            'summary': dict(result) if result else {},
            'online_user_ids': [r['id'] for r in online_users]
        }
    finally:
        await conn.close()


async def get_recent_clients(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Oxirgi faol clientlar (chat yaratgan yoki xabar yuborgan)
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                u.id,
                u.telegram_id,
                u.full_name,
                u.username,
                u.phone,
                u.is_online,
                u.last_seen_at,
                u.region,
                u.abonent_id,
                COALESCE(stats.active_chats, 0) as active_chats_count,
                COALESCE(stats.total_chats, 0) as total_chats_count,
                stats.last_activity_at
            FROM users u
            LEFT JOIN LATERAL (
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'active') as active_chats,
                    COUNT(*) as total_chats,
                    MAX(last_activity_at) as last_activity_at
                FROM chats 
                WHERE client_id = u.id
            ) stats ON TRUE
            WHERE u.role = 'client'
              AND stats.total_chats > 0
            ORDER BY stats.last_activity_at DESC NULLS LAST
            LIMIT $1
            """,
            limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

