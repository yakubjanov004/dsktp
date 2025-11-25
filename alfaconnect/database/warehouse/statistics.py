# database/warehouse/statistics.py
import asyncpg
from typing import Dict, Any, List
from datetime import date, datetime
from config import settings

# ---------- STATISTIKA BOSHLANG'ICH KO'RSATKICHLAR ----------

async def get_warehouse_head_counters() -> Dict[str, Any]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        total_materials = await conn.fetchval("SELECT COUNT(*) FROM materials")
        total_quantity = await conn.fetchval("SELECT COALESCE(SUM(quantity),0) FROM materials")
        total_value = await conn.fetchval("SELECT COALESCE(SUM(quantity * COALESCE(price,0)),0) FROM materials")
        low_stock_count = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE quantity <= 10")
        out_of_stock_count = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE quantity = 0")
        # aylanish (mock, joriy oy qo'shilganlarga qarab foiz)
        weekly_added = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE created_at >= date_trunc('week', CURRENT_DATE)")
        turnover_rate = min(100, (weekly_added or 0) * 5)  # ko'rsatkich uchun oddiy formula
        turnover_rate_week = turnover_rate

        top_stock_material = await conn.fetchrow("SELECT name, quantity FROM materials ORDER BY quantity DESC LIMIT 1")
        most_expensive = await conn.fetchrow("SELECT name, price FROM materials WHERE price IS NOT NULL ORDER BY price DESC LIMIT 1")

        return {
            "total_materials": int(total_materials or 0),
            "total_quantity": int(total_quantity or 0),
            "total_value": float(total_value or 0),
            "low_stock_count": int(low_stock_count or 0),
            "out_of_stock_count": int(out_of_stock_count or 0),
            "turnover_rate": int(turnover_rate),
            "turnover_rate_week": int(turnover_rate_week),
            "top_stock_material": dict(top_stock_material) if top_stock_material else None,
            "most_expensive": dict(most_expensive) if most_expensive else None,
        }
    finally:
        await conn.close()

async def get_warehouse_daily_statistics(date_str: str | None = None) -> Dict[str, Any]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if date_str:
            daily_added = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE DATE(created_at) = $1", date_str)
            daily_updated = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE DATE(updated_at) = $1", date_str)
        else:
            daily_added = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE DATE(created_at) = CURRENT_DATE")
            daily_updated = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE DATE(updated_at) = CURRENT_DATE")
        return {"daily_added": int(daily_added or 0), "daily_updated": int(daily_updated or 0)}
    finally:
        await conn.close()

async def get_warehouse_weekly_statistics() -> Dict[str, Any]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        weekly_added = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE created_at >= date_trunc('week', CURRENT_DATE)")
        weekly_updated = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE updated_at >= date_trunc('week', CURRENT_DATE)")
        weekly_value = await conn.fetchval("SELECT COALESCE(SUM(quantity * COALESCE(price,0)),0) FROM materials WHERE created_at >= date_trunc('week', CURRENT_DATE)")
        return {
            "weekly_added": int(weekly_added or 0), 
            "weekly_updated": int(weekly_updated or 0),
            "weekly_value": float(weekly_value or 0)
        }
    finally:
        await conn.close()

async def get_warehouse_monthly_statistics() -> Dict[str, Any]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        monthly_added = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE created_at >= date_trunc('month', CURRENT_DATE)")
        monthly_updated = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE updated_at >= date_trunc('month', CURRENT_DATE)")
        monthly_value = await conn.fetchval("SELECT COALESCE(SUM(quantity * COALESCE(price,0)),0) FROM materials WHERE created_at >= date_trunc('month', CURRENT_DATE)")
        return {
            "monthly_added": int(monthly_added or 0), 
            "monthly_updated": int(monthly_updated or 0),
            "monthly_value": float(monthly_value or 0)
        }
    finally:
        await conn.close()

async def get_warehouse_yearly_statistics() -> Dict[str, Any]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        yearly_added = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE created_at >= date_trunc('year', CURRENT_DATE)")
        yearly_updated = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE updated_at >= date_trunc('year', CURRENT_DATE)")
        yearly_value = await conn.fetchval("SELECT COALESCE(SUM(quantity * COALESCE(price,0)),0) FROM materials WHERE created_at >= date_trunc('year', CURRENT_DATE)")
        return {
            "yearly_added": int(yearly_added or 0), 
            "yearly_updated": int(yearly_updated or 0),
            "yearly_value": float(yearly_value or 0)
        }
    finally:
        await conn.close()

async def get_warehouse_range_statistics(date_from: str, date_to: str) -> Dict[str, Any]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        range_added = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE DATE(created_at) BETWEEN $1 AND $2", date_from, date_to)
        range_updated = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE DATE(updated_at) BETWEEN $1 AND $2", date_from, date_to)
        return {"range_added": int(range_added or 0), "range_updated": int(range_updated or 0)}
    finally:
        await conn.close()

async def get_warehouse_financial_report() -> Dict[str, Any]:
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        total_value = await conn.fetchval("SELECT COALESCE(SUM(quantity * COALESCE(price,0)),0) FROM materials")
        avg_price = await conn.fetchval("SELECT COALESCE(AVG(price),0) FROM materials WHERE price IS NOT NULL")
        most_expensive = await conn.fetchrow("SELECT name, price FROM materials WHERE price IS NOT NULL ORDER BY price DESC LIMIT 1")
        cheapest = await conn.fetchrow("SELECT name, price FROM materials WHERE price IS NOT NULL ORDER BY price ASC LIMIT 1")
        
        return {
            "total_value": float(total_value or 0),
            "avg_price": float(avg_price or 0),
            "most_expensive": dict(most_expensive) if most_expensive else None,
            "cheapest": dict(cheapest) if cheapest else None,
        }
    finally:
        await conn.close()

async def get_warehouse_statistics() -> Dict[str, Any]:
    """Umumiy ombor statistikasi"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        # Asosiy ko'rsatkichlar
        total_materials = await conn.fetchval("SELECT COUNT(*) FROM materials")
        total_quantity = await conn.fetchval("SELECT COALESCE(SUM(quantity),0) FROM materials")
        total_value = await conn.fetchval("SELECT COALESCE(SUM(quantity * COALESCE(price,0)),0) FROM materials")
        
        # Kam qolgan materiallar
        low_stock_count = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE quantity <= 10")
        out_of_stock_count = await conn.fetchval("SELECT COUNT(*) FROM materials WHERE quantity = 0")
        
        # Eng ko'p va eng kam materiallar
        top_stock_material = await conn.fetchrow("SELECT name, quantity FROM materials ORDER BY quantity DESC LIMIT 1")
        most_expensive = await conn.fetchrow("SELECT name, price FROM materials WHERE price IS NOT NULL ORDER BY price DESC LIMIT 1")
        
        return {
            "total_materials": int(total_materials or 0),
            "total_quantity": int(total_quantity or 0),
            "total_value": float(total_value or 0),
            "low_stock_count": int(low_stock_count or 0),
            "out_of_stock_count": int(out_of_stock_count or 0),
            "top_stock_material": dict(top_stock_material) if top_stock_material else None,
            "most_expensive": dict(most_expensive) if most_expensive else None,
        }
    finally:
        await conn.close()

async def get_warehouse_statistics_for_export() -> List[Dict[str, Any]]:
    """Export uchun ombor statistikasi"""
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT 
                COUNT(*) as total_materials,
                COALESCE(SUM(quantity),0) as total_quantity,
                COALESCE(SUM(quantity * COALESCE(price,0)),0) as total_value,
                COUNT(CASE WHEN quantity <= 10 THEN 1 END) as low_stock_count,
                COUNT(CASE WHEN quantity = 0 THEN 1 END) as out_of_stock_count
            FROM materials
            """
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()
