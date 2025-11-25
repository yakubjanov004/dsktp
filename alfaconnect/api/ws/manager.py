# app/ws/manager.py

from typing import Dict, Set, Optional
from fastapi import WebSocket
from collections import defaultdict
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class ChatWSManager:
    """
    Enhanced WebSocket Manager with decorator pattern for handlers
    Based on fastapi-chat patterns
    """
    
    def __init__(self, use_redis_pubsub: bool = False, redis_pubsub_manager=None):
        """
        Initialize WebSocket Manager.
        
        Args:
            use_redis_pubsub: If True, use Redis PubSub for distributed messaging
            redis_pubsub_manager: Optional RedisPubSubManager instance
        """
        self.rooms: Dict[int, Set[WebSocket]] = defaultdict(set)
        self.user_connections: Dict[int, Set[WebSocket]] = defaultdict(set)  # user_id -> {ws1, ws2}
        self._lock = asyncio.Lock()
        self.handlers: Dict[str, callable] = {}  # message_type -> handler function
        self.use_redis_pubsub = use_redis_pubsub
        self.pubsub_manager = redis_pubsub_manager
        self._pubsub_tasks: Dict[int, asyncio.Task] = {}  # chat_id -> pubsub reader task

    def handler(self, message_type: str):
        """
        Decorator to register a message handler.
        
        Usage:
            @manager.handler("message")
            async def handle_message(websocket, incoming_message, **kwargs):
                ...
        """
        def decorator(func):
            self.handlers[message_type] = func
            logger.info(f"Registered WebSocket handler for type: {message_type}")
            return func
        return decorator

    async def connect(self, chat_id: int, ws: WebSocket, accept_already_called: bool = False):
        """
        Connect a WebSocket to a chat room
        
        Args:
            chat_id: Chat room ID
            ws: WebSocket instance
            accept_already_called: If True, skip ws.accept() (for cases where accept was already called)
        """
        if not accept_already_called:
            await ws.accept()
        
        async with self._lock:
            self.rooms[chat_id].add(ws)
            logger.info(f"WebSocket connected to chat {chat_id}. Total connections: {len(self.rooms[chat_id])}")
            
            # If using Redis PubSub and this is the first connection to this chat, subscribe
            if self.use_redis_pubsub and self.pubsub_manager and chat_id not in self._pubsub_tasks:
                await self._setup_redis_pubsub(chat_id)

    async def _setup_redis_pubsub(self, chat_id: int):
        """Setup Redis PubSub subscription for a chat."""
        if not self.pubsub_manager:
            return
            
        try:
            await self.pubsub_manager.connect()
            pubsub_subscriber = await self.pubsub_manager.subscribe(str(chat_id))
            # Start background task to read from PubSub
            task = asyncio.create_task(self._pubsub_data_reader(chat_id, pubsub_subscriber))
            self._pubsub_tasks[chat_id] = task
            logger.info(f"Redis PubSub setup for chat {chat_id}")
        except Exception as e:
            logger.error(f"Failed to setup Redis PubSub for chat {chat_id}: {e}")

    async def _pubsub_data_reader(self, chat_id: int, pubsub_subscriber):
        """
        Background task to read messages from Redis PubSub and broadcast to WebSocket clients.
        """
        try:
            while True:
                message = await pubsub_subscriber.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is not None:
                    channel = message["channel"].decode("utf-8") if isinstance(message["channel"], bytes) else message["channel"]
                    if channel == str(chat_id):
                        data = message["data"].decode("utf-8") if isinstance(message["data"], bytes) else message["data"]
                        # Broadcast to all WebSocket connections in this chat
                        await self._broadcast_to_room(chat_id, data)
        except asyncio.CancelledError:
            logger.info(f"PubSub reader task cancelled for chat {chat_id}")
        except Exception as e:
            logger.exception(f"Error in PubSub reader for chat {chat_id}: {e}")

    async def _broadcast_to_room(self, chat_id: int, message: str):
        """Broadcast message to all WebSocket connections in a room."""
        disconnected = []
        async with self._lock:
            room = self.rooms.get(chat_id, set())
            for ws in list(room):
                try:
                    if hasattr(ws, 'client_state') and ws.client_state.name != 'CONNECTED':
                        disconnected.append(ws)
                        continue
                    await ws.send_text(message)
                except Exception as e:
                    logger.warning(f"Error broadcasting to WebSocket in chat {chat_id}: {e}")
                    disconnected.append(ws)
        
        # Clean up disconnected WebSockets
        if disconnected:
            async with self._lock:
                room = self.rooms.get(chat_id)
                if room:
                    for ws in disconnected:
                        room.discard(ws)
                    if not room:
                        self.rooms.pop(chat_id, None)
                        # Cancel PubSub task if no connections
                        if chat_id in self._pubsub_tasks:
                            self._pubsub_tasks[chat_id].cancel()
                            del self._pubsub_tasks[chat_id]
                            if self.pubsub_manager:
                                await self.pubsub_manager.unsubscribe(str(chat_id))

    async def disconnect(self, chat_id: int, ws: WebSocket):
        """Disconnect a WebSocket from a chat room"""
        async with self._lock:
            room = self.rooms.get(chat_id)
            if room and ws in room:
                room.remove(ws)
                logger.info(f"WebSocket disconnected from chat {chat_id}. Remaining connections: {len(room)}")
            
            # If no connections left, cleanup
            if room and not room:
                self.rooms.pop(chat_id, None)
                logger.info(f"Chat room {chat_id} removed (no connections)")
                
                # Cancel PubSub task
                if chat_id in self._pubsub_tasks:
                    self._pubsub_tasks[chat_id].cancel()
                    del self._pubsub_tasks[chat_id]
                    if self.pubsub_manager:
                        await self.pubsub_manager.unsubscribe(str(chat_id))

    async def emit(self, chat_id: int, event: str, payload: dict):
        """
        Emit an event to all WebSocket connections in a chat room.
        If Redis PubSub is enabled, also publishes to Redis for distributed messaging.
        
        Args:
            chat_id: Chat room ID
            event: Event name (e.g., "message.new")
            payload: Event payload data
        """
        msg = json.dumps({"event": event, "payload": payload}, ensure_ascii=False)
        
        # If using Redis PubSub, publish to Redis (other instances will pick it up)
        if self.use_redis_pubsub and self.pubsub_manager:
            try:
                await self.pubsub_manager.publish(str(chat_id), msg)
            except Exception as e:
                logger.error(f"Error publishing to Redis for chat {chat_id}: {e}")
        
        # Also broadcast directly to local connections
        await self._broadcast_to_room(chat_id, msg)

    async def send_error(self, message: str, websocket: WebSocket):
        """Send an error message to a WebSocket client."""
        try:
            error_msg = json.dumps({"status": "error", "message": message}, ensure_ascii=False)
            await websocket.send_text(error_msg)
        except Exception as e:
            logger.error(f"Error sending error message: {e}")

    async def add_user_connection(self, user_id: int, websocket: WebSocket):
        """Add a user's WebSocket connection (for tracking user connections across chats)."""
        async with self._lock:
            self.user_connections[user_id].add(websocket)

    async def remove_user_connection(self, user_id: int, websocket: WebSocket):
        """Remove a user's WebSocket connection."""
        async with self._lock:
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(websocket)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]


# Global manager instance (default, without Redis PubSub)
manager = ChatWSManager()

