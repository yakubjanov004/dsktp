# database/admin/orders.py

import asyncpg
from typing import List, Dict, Any
from config import settings

async def get_connection_orders(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Connection orders ro'yxati"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                co.id,
                co.application_number,
                co.address,
                co.region,
                co.status,
                co.is_active,
                co.created_at,
                co.updated_at,
                co.latitude,
                co.longitude,
                co.jm_notes,
                u.full_name as client_name,
                u.phone as client_phone,
                u.username,
                t.name as tariff_name,
                mf.file_path as media
            FROM connection_orders co
            LEFT JOIN users u ON u.id = co.user_id
            LEFT JOIN tarif t ON t.id = co.tarif_id
            LEFT JOIN media_files mf ON mf.related_table = 'connection_orders' AND mf.related_id = co.id AND mf.is_active = true
            ORDER BY co.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_technician_orders(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Technician orders ro'yxati"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
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
                tech_orders.abonent_id,
                tech_orders.media,
                tech_orders.latitude,
                tech_orders.longitude,
                u.full_name as client_name,
                u.phone as client_phone,
                u.username,
                CASE 
                    WHEN tech_orders.media IS NOT NULL THEN 'video'
                    ELSE NULL
                END as media_type
            FROM technician_orders tech_orders
            LEFT JOIN users u ON u.id = tech_orders.user_id
            ORDER BY tech_orders.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_staff_orders(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Staff orders ro'yxati"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                so.id,
                so.application_number,
                so.address,
                so.region,
                so.status,
                so.is_active,
                so.description,
                so.phone,
                so.abonent_id,
                so.type_of_zayavka,
                so.problem_description,
                so.created_at,
                so.updated_at,
                u.full_name as client_name,
                u.phone as client_phone,
                u.username,
                t.name as tariff_name
            FROM staff_orders so
            LEFT JOIN users u ON u.id = so.user_id
            LEFT JOIN tarif t ON t.id = so.tarif_id
            ORDER BY so.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()
