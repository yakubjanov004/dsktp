"""
Monitoring and observability utilities for chat system
"""
import logging
import time
from functools import wraps
from typing import Callable, Any, Dict
from datetime import datetime
import asyncpg
from config import settings

logger = logging.getLogger(__name__)

# Metrics storage (in production, use Prometheus, StatsD, etc.)
metrics = {
    "api_requests": {},
    "ws_connections": {"active": 0, "total_connects": 0, "total_disconnects": 0, "reconnects": 0},
    "cron_jobs": {},
    "db_conflicts": {"ux_chats_client_active": 0, "ux_chat_assignment_log_chat_open": 0}
}


def log_api_latency(endpoint: str):
    """Decorator to log API endpoint latency (p95 tracking)"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                
                # Track latency
                if endpoint not in metrics["api_requests"]:
                    metrics["api_requests"][endpoint] = {
                        "count": 0,
                        "total_latency": 0,
                        "latencies": []
                    }
                
                metrics["api_requests"][endpoint]["count"] += 1
                metrics["api_requests"][endpoint]["total_latency"] += latency_ms
                metrics["api_requests"][endpoint]["latencies"].append(latency_ms)
                
                # Keep only last 100 latencies for p95 calculation
                if len(metrics["api_requests"][endpoint]["latencies"]) > 100:
                    metrics["api_requests"][endpoint]["latencies"] = \
                        metrics["api_requests"][endpoint]["latencies"][-100:]
                
                logger.info(f"API {endpoint} latency: {latency_ms:.2f}ms")
                return result
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                logger.error(f"API {endpoint} error after {latency_ms:.2f}ms: {e}")
                raise
        return wrapper
    return decorator


def get_p95_latency(endpoint: str) -> float:
    """Calculate p95 latency for an endpoint"""
    if endpoint not in metrics["api_requests"]:
        return 0.0
    
    latencies = metrics["api_requests"][endpoint]["latencies"]
    if not latencies:
        return 0.0
    
    sorted_latencies = sorted(latencies)
    p95_index = int(len(sorted_latencies) * 0.95)
    return sorted_latencies[p95_index] if p95_index < len(sorted_latencies) else sorted_latencies[-1]


async def log_cron_result(job_name: str, result: Any, execution_time: float = None):
    """Log cron job execution result"""
    if execution_time:
        logger.info(f"Cron {job_name} completed in {execution_time:.2f}s: {result}")
    else:
        logger.info(f"Cron {job_name} completed: {result}")
    
    metrics["cron_jobs"][job_name] = {
        "last_run": datetime.now().isoformat(),
        "result": str(result),
        "execution_time": execution_time
    }


def track_ws_connection(action: str):
    """Track WebSocket connection events"""
    if action == "connect":
        metrics["ws_connections"]["active"] += 1
        metrics["ws_connections"]["total_connects"] += 1
        logger.info(f"WS connect. Active: {metrics['ws_connections']['active']}")
    elif action == "disconnect":
        metrics["ws_connections"]["active"] = max(0, metrics["ws_connections"]["active"] - 1)
        metrics["ws_connections"]["total_disconnects"] += 1
        logger.info(f"WS disconnect. Active: {metrics['ws_connections']['active']}")
    elif action == "reconnect":
        metrics["ws_connections"]["reconnects"] += 1
        logger.info(f"WS reconnect attempt. Total: {metrics['ws_connections']['reconnects']}")


async def track_db_conflict(constraint_name: str):
    """Track database constraint violations (race conditions)"""
    if constraint_name in metrics["db_conflicts"]:
        metrics["db_conflicts"][constraint_name] += 1
        logger.warning(f"DB conflict detected: {constraint_name} (total: {metrics['db_conflicts'][constraint_name]})")
    else:
        metrics["db_conflicts"][constraint_name] = 1
        logger.warning(f"DB conflict detected: {constraint_name} (new)")


async def get_metrics_summary() -> Dict[str, Any]:
    """Get summary of all metrics"""
    summary = {
        "api": {},
        "ws": metrics["ws_connections"].copy(),
        "cron": metrics["cron_jobs"].copy(),
        "db_conflicts": metrics["db_conflicts"].copy()
    }
    
    # Calculate p95 for each endpoint
    for endpoint in metrics["api_requests"]:
        data = metrics["api_requests"][endpoint]
        p95 = get_p95_latency(endpoint)
        summary["api"][endpoint] = {
            "count": data["count"],
            "avg_latency_ms": data["total_latency"] / data["count"] if data["count"] > 0 else 0,
            "p95_latency_ms": p95
        }
    
    return summary


async def log_mark_inactive_result(count: int, execution_time: float):
    """Log mark_inactive_chats_auto() result"""
    await log_cron_result("mark_inactive_chats_auto", f"inactive updated: {count}", execution_time)


# Example usage in API endpoints:
# @log_api_latency("/chat/inbox")
# async def get_inbox(...):
#     ...

