"""
WebSocket Rate Limiting
Based on fastapi-chat patterns
"""
import logging
from typing import Dict
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class WebSocketRateLimiter:
    """
    Simple in-memory rate limiter for WebSocket connections.
    For production, consider using Redis-based rate limiting.
    """
    
    def __init__(self, times: int = 50, seconds: int = 10):
        """
        Initialize rate limiter.
        
        Args:
            times: Maximum number of requests allowed
            seconds: Time window in seconds
        """
        self.times = times
        self.seconds = seconds
        self.requests: Dict[str, list] = defaultdict(list)  # websocket_id -> [timestamps]
        self._cleanup_interval = timedelta(seconds=60)  # Cleanup old entries every minute
        self._last_cleanup = datetime.now()
    
    def _cleanup_old_entries(self):
        """Remove old request timestamps to prevent memory leaks."""
        now = datetime.now()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        cutoff = now - timedelta(seconds=self.seconds * 2)  # Keep 2x window for safety
        for ws_id in list(self.requests.keys()):
            self.requests[ws_id] = [
                ts for ts in self.requests[ws_id] if ts > cutoff
            ]
            if not self.requests[ws_id]:
                del self.requests[ws_id]
        
        self._last_cleanup = now
    
    def _get_websocket_id(self, websocket) -> str:
        """Get a unique identifier for a WebSocket connection."""
        # Use client info if available, otherwise use object id
        if hasattr(websocket, 'client'):
            return f"{websocket.client.host}:{id(websocket)}"
        return str(id(websocket))
    
    async def check_rate_limit(self, websocket) -> bool:
        """
        Check if WebSocket request is within rate limit.
        
        Args:
            websocket: WebSocket instance
            
        Returns:
            True if within limit, False if rate limited
        """
        self._cleanup_old_entries()
        
        ws_id = self._get_websocket_id(websocket)
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.seconds)
        
        # Filter out old requests
        self.requests[ws_id] = [
            ts for ts in self.requests[ws_id] if ts > cutoff
        ]
        
        # Check if limit exceeded
        if len(self.requests[ws_id]) >= self.times:
            logger.warning(f"Rate limit exceeded for WebSocket {ws_id}: {len(self.requests[ws_id])} requests in {self.seconds}s")
            return False
        
        # Add current request
        self.requests[ws_id].append(now)
        return True


class WebsocketTooManyRequests(Exception):
    """Exception raised when WebSocket rate limit is exceeded."""
    pass

