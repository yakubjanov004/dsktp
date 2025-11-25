# database/admin/export.py

import asyncpg
from typing import List, Dict, Any
from config import settings

def _get_time_condition(time_period: str, column: str) -> str:
    """
    Get SQL WHERE condition for time period filtering.
    time_period: 'today', 'week', 'month', 'total'
    column: column name to filter on (e.g., 'created_at')
    
    For 'week': calculates from Monday to today
    """
    if time_period == "today":
        return f"{column} >= CURRENT_DATE"
    elif time_period == "week":
        from datetime import datetime, timedelta
        today = datetime.now()
        days_since_monday = today.weekday() 
        monday = today - timedelta(days=days_since_monday)
        monday_date = monday.strftime("%Y-%m-%d")
        return f"{column} >= '{monday_date}'"
    elif time_period == "month":
        return f"{column} >= CURRENT_DATE - INTERVAL '30 days'"
    else:  # total
        return "TRUE"

async def get_admin_users_for_export(user_type: str = "all") -> List[Dict[str, Any]]:
    """Admin uchun foydalanuvchilar ro'yxatini export qilish"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Build query based on user type
        if user_type == "clients":
            where_clause = "WHERE role = 'client'"
        elif user_type == "staff":
            where_clause = "WHERE role IN ('admin', 'manager', 'controller', 'technician', 'callcenter_supervisor', 'callcenter_operator', 'junior_manager', 'warehouse')"
        else:
            where_clause = ""
        
        rows = await conn.fetch(
            f"""
            SELECT 
                id,
                telegram_id,
                username,
                full_name,
                phone,
                role,
                language,
                is_blocked,
                created_at,
                updated_at
            FROM users
            {where_clause}
            ORDER BY created_at DESC
            """
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_admin_connection_orders_for_export(time_period: str = "total") -> List[Dict[str, Any]]:
    """Admin uchun connection orders ro'yxatini export qilish
    time_period: 'today', 'week', 'month', 'total'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        time_condition = _get_time_condition(time_period, "co.created_at")
        rows = await conn.fetch(
            f"""
            SELECT 
                co.id,
                co.application_number,
                co.address,
                co.region,
                co.status,
                co.is_active,
                co.created_at,
                co.updated_at,
                u.full_name as client_name,
                u.phone as client_phone,
                t.name as tariff_name
            FROM connection_orders co
            LEFT JOIN users u ON u.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            WHERE {time_condition}
            ORDER BY co.created_at DESC
            """
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_admin_technician_orders_for_export(time_period: str = "total") -> List[Dict[str, Any]]:
    """Admin uchun technician orders ro'yxatini export qilish
    time_period: 'today', 'week', 'month', 'total'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        time_condition = _get_time_condition(time_period, "tech_orders.created_at")
        rows = await conn.fetch(
            f"""
            SELECT 
                tech_orders.id,
                tech_orders.application_number,
                tech_orders.address,
                tech_orders.region,
                tech_orders.status,
                tech_orders.is_active,
                tech_orders.description,
                tech_orders.created_at,
                tech_orders.updated_at,
                u.full_name as client_name,
                u.phone as client_phone
            FROM technician_orders tech_orders
            LEFT JOIN users u ON u.id = tech_orders.user_id
            WHERE {time_condition}
            ORDER BY tech_orders.created_at DESC
            """
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_admin_staff_orders_for_export(time_period: str = "total") -> List[Dict[str, Any]]:
    """Admin uchun staff orders ro'yxatini export qilish
    time_period: 'today', 'week', 'month', 'total'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        time_condition = _get_time_condition(time_period, "so.created_at")
        rows = await conn.fetch(
            f"""
            SELECT 
                so.id,
                so.application_number,
                so.address,
                so.region,
                so.status,
                so.is_active,
                so.description,
                so.phone,
                so.created_at,
                so.updated_at,
                u.full_name as client_name,
                u.phone as client_phone
            FROM staff_orders so
            LEFT JOIN users u ON u.id = so.user_id
            WHERE {time_condition}
            ORDER BY so.created_at DESC
            """
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_admin_statistics_for_export(time_period: str = "total") -> Dict[str, Any]:
    """Admin uchun statistikalar
    time_period: 'today', 'week', 'month', 'total'
    """
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Note: total_users and total_materials are not time-filtered
        time_condition_co = _get_time_condition(time_period, "created_at")
        time_condition_to = _get_time_condition(time_period, "created_at")
        time_condition_so = _get_time_condition(time_period, "created_at")
        
        stats = await conn.fetchrow(
            f"""
            SELECT 
                (SELECT COUNT(*) FROM users) as total_users,
                (SELECT COUNT(*) FROM connection_orders WHERE is_active = TRUE AND {time_condition_co}) as active_connections,
                (SELECT COUNT(*) FROM technician_orders WHERE is_active = TRUE AND {time_condition_to}) as active_technician,
                (SELECT COUNT(*) FROM staff_orders WHERE is_active = TRUE AND {time_condition_so}) as active_staff,
                (SELECT COUNT(*) FROM materials) as total_materials
            """
        )
        return dict(stats) if stats else {}
    finally:
        await conn.close()
