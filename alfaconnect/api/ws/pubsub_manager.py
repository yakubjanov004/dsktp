"""
Redis PubSub Manager for distributed WebSocket messaging
Based on fastapi-chat patterns
"""
import redis.asyncio as aioredis
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RedisPubSubManager:
    """
    Manages Redis PubSub connections for distributed WebSocket messaging.
    Allows multiple server instances to broadcast messages to WebSocket clients.
    """
    
    def __init__(self, redis_pool: Optional[aioredis.ConnectionPool] = None):
        """
        Initialize Redis PubSub Manager.
        
        Args:
            redis_pool: Optional Redis connection pool. If None, will create new connection.
        """
        self.redis_pool = redis_pool
        self.redis_connection: Optional[aioredis.Redis] = None
        self.pubsub: Optional[aioredis.client.PubSub] = None
        self._connected = False

    async def _get_redis_connection(self) -> aioredis.Redis:
        """Get or create Redis connection."""
        if self.redis_pool:
            return aioredis.Redis(connection_pool=self.redis_pool)
        # Fallback: create direct connection (not recommended for production)
        return aioredis.Redis(host='localhost', port=6379, decode_responses=False)

    async def connect(self):
        """Connect to Redis and create PubSub instance."""
        if self._connected:
            logger.warning("Redis PubSub already connected")
            return
            
        try:
            self.redis_connection = await self._get_redis_connection()
            self.pubsub = self.redis_connection.pubsub()
            self._connected = True
            logger.info("Redis PubSub connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis PubSub: {e}")
            raise

    async def subscribe(self, channel: str) -> aioredis.client.PubSub:
        """
        Subscribe to a Redis channel.
        
        Args:
            channel: Channel name (e.g., chat_id or chat_guid)
            
        Returns:
            PubSub instance for reading messages
        """
        if not self._connected:
            await self.connect()
        
        await self.pubsub.subscribe(channel)
        logger.debug(f"Subscribed to Redis channel: {channel}")
        return self.pubsub

    async def unsubscribe(self, channel: str):
        """Unsubscribe from a Redis channel."""
        if not self._connected or not self.pubsub:
            return
            
        try:
            await self.pubsub.unsubscribe(channel)
            logger.debug(f"Unsubscribed from Redis channel: {channel}")
        except Exception as e:
            logger.error(f"Error unsubscribing from channel {channel}: {e}")

    async def publish(self, channel: str, message: str | dict):
        """
        Publish a message to a Redis channel.
        
        Args:
            channel: Channel name
            message: Message to publish (str or dict, will be JSON-encoded if dict)
        """
        if not self._connected:
            await self.connect()
        
        import json
        if isinstance(message, dict):
            message = json.dumps(message, ensure_ascii=False)
        
        try:
            await self.redis_connection.publish(channel, message)
            logger.debug(f"Published message to Redis channel: {channel}")
        except Exception as e:
            logger.error(f"Error publishing to channel {channel}: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        if not self._connected:
            return
            
        try:
            if self.pubsub:
                await self.pubsub.close()
            if self.redis_connection:
                await self.redis_connection.close()
            self._connected = False
            logger.info("Redis PubSub disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting from Redis: {e}")

