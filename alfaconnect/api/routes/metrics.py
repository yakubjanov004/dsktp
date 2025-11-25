"""
Metrics endpoint for monitoring
"""
from fastapi import APIRouter
from utils.monitoring import get_metrics_summary

router = APIRouter()


@router.get("/metrics")
async def get_metrics():
    """
    Get monitoring metrics summary.
    Returns API latency (p95), WebSocket connections, cron jobs, and DB conflicts.
    """
    try:
        metrics = await get_metrics_summary()
        return metrics
    except Exception as e:
        return {"error": str(e)}

