"""
WebSocket endpoints for real-time chat
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from starlette.websockets import WebSocketState
from database.webapp.user_queries import get_user_by_id
from database.webapp.staff_chat_queries import get_staff_chat_by_id, get_staff_messages, get_staff_message_by_id, create_staff_message
from api.ws.manager import manager as chat_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Store global WebSocket connections for stats updates
# Format: {user_id: WebSocket} - for supervisors and operators
global_connections: Dict[int, WebSocket] = {}

# Store staff chat WebSocket connections
# Format: {chat_id: {user_id: WebSocket}}
staff_chat_connections: Dict[int, Dict[int, WebSocket]] = {}

# Store online status for operators and supervisors
# Format: {user_id: bool}
online_users: Dict[int, bool] = {}

# Store online status timestamps (last_seen)
# Format: {user_id: datetime}
online_status_timestamp: Dict[int, datetime] = {}



# Helper function to broadcast user online/offline status
async def broadcast_user_status(user_id: int, is_online: bool, role: str = None, exclude_user_id: int = None):
    """
    Broadcast user online/offline status to all relevant users.
    Sends user.online or user.offline event to all global connections.
    """
    event = {
        "type": "user.online" if is_online else "user.offline",
        "user_id": user_id,
        "role": role
    }
    
    # Send to all global connections (operators and supervisors)
    disconnected = []
    for uid, ws in list(global_connections.items()):
        # Skip the user who just connected/disconnected
        if exclude_user_id and uid == exclude_user_id:
            continue
        
        try:
            # Check WebSocket state before sending
            if hasattr(ws, 'client_state') and ws.client_state.name != 'CONNECTED':
                disconnected.append(uid)
                continue
            
            await ws.send_json(event)
        except Exception as e:
            logger.error(f"Error sending user status to user {uid}: {e}")
            disconnected.append(uid)
    
    # Clean up disconnected users - only remove from connections, don't mark as offline
    # The offline status should only be set when the user actually disconnects, not when we can't send to them
    for uid in disconnected:
        global_connections.pop(uid, None)
        # ❗ Don't modify online_users here - we're broadcasting ABOUT someone else's status,
        # not marking recipients as offline


async def _send_event_to_global_user(user_id: int, event: dict):
    """
    Send a JSON event to a single stats WebSocket (if connected).
    Removes stale connections automatically.
    """
    websocket = global_connections.get(user_id)
    if not websocket:
        return

    try:
        await websocket.send_json(event)
    except Exception as e:
        logger.error(f"Error sending event to user {user_id}: {e}")
        global_connections.pop(user_id, None)


async def _broadcast_global_event(event: dict, exclude_user_id: int = None):
    """
    Broadcast a JSON event to all stats WebSockets, optionally skipping one user.
    """
    disconnected = []
    for uid, websocket in list(global_connections.items()):
        if exclude_user_id and uid == exclude_user_id:
            continue
        try:
            await websocket.send_json(event)
        except Exception as e:
            logger.error(f"Error sending event to user {uid}: {e}")
            disconnected.append(uid)

    for uid in disconnected:
        global_connections.pop(uid, None)


def _serialize_datetime(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _serialize_chat(chat: Optional[dict]) -> Optional[dict]:
    if not chat:
        return None
    return {
        "id": chat.get("id"),
        "client_id": chat.get("client_id"),
        "operator_id": chat.get("operator_id"),
        "status": chat.get("status"),
        "created_at": _serialize_datetime(chat.get("created_at")),
        "updated_at": _serialize_datetime(chat.get("updated_at")),
        "last_activity_at": _serialize_datetime(chat.get("last_activity_at")),
        "client_name": chat.get("client_name"),
        "client_telegram_id": chat.get("client_telegram_id"),
        "operator_name": chat.get("operator_name"),
    }


async def send_chat_new_event(chat: dict):
    """
    Broadcast chat.new event with serialized chat payload.
    """
    chat_payload = _serialize_chat(chat)
    if not chat_payload:
        logger.warning("[chat.new] Attempted to broadcast without chat payload")
        return

    event = {
        "type": "chat.new",
        "chat_id": chat_payload["id"],
        "chat": chat_payload,
    }
    await _broadcast_global_event(event)


@router.websocket("/stats")
async def stats_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for global stats updates (supervisors and operators)
    Expects: ?user_id=123 in query params
    Tracks online/offline status for operators and supervisors
    """
    # Get user_id from query params
    user_id_param = websocket.query_params.get("user_id")
    if not user_id_param:
        await websocket.close(code=1008, reason="user_id parameter required")
        return
    
    try:
        user_id = int(user_id_param)
    except ValueError:
        await websocket.close(code=1008, reason="Invalid user_id parameter")
        return
    
    # Get user to check role
    user = await get_user_by_id(user_id)
    if not user:
        await websocket.close(code=1008, reason="User not found")
        return
    
    user_role = user.get('role')
    
    # Only allow operators and supervisors
    if user_role not in ('callcenter_operator', 'callcenter_supervisor'):
        await websocket.close(code=1008, reason="Only operators and supervisors can connect")
        return
    
    # Connect to global connections
    await websocket.accept()
    global_connections[user_id] = websocket
    
    # Mark user as online
    online_users[user_id] = True
    online_status_timestamp[user_id] = datetime.now()
    
    logger.info(f"[STATS-WS] User {user_id} ({user_role}) connected - marked as online")
    logger.info(f"[STATS-WS] Total online users: {len([u for u, status in online_users.items() if status])}")
    
    try:
        # Send initial stats
        from database.webapp.chat_queries import get_active_chat_counts
        stats = await get_active_chat_counts()
        
        # Send initial online users list (before adding current user to broadcast)
        online_user_ids = [uid for uid, is_online in online_users.items() if is_online and uid != user_id]
        
        try:
            await websocket.send_json({
                "type": "stats.initial",
                "inbox_count": stats["inbox_count"],
                "operator_counts": stats["operator_counts"],
                "online_users": online_user_ids
            })
        except Exception as e:
            logger.error(f"Error sending initial stats to user {user_id}: {e}", exc_info=True)
            # Don't raise - continue even if stats fail
        
        # Broadcast online status to other users (after initial message sent)
        await broadcast_user_status(user_id, True, user_role, exclude_user_id=user_id)
        
        # Listen for messages (ping/pong, etc.)
        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                raise
            except RuntimeError as e:
                if "close message has been sent" in str(e):
                    break
                raise
            except Exception as e:
                logger.warning(f"[STATS-WS] Error receiving message from user {user_id}: {e}")
                break
            
            if data.get("type") == "ping":
                now_ts = datetime.now()
                online_status_timestamp[user_id] = now_ts
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        logger.info(f"[STATS-WS] User {user_id} disconnected from stats WebSocket")
    except Exception as e:
        logger.exception(f"[STATS-WS] Error in stats WebSocket connection: {e}")
    finally:
        # Always cleanup on exit (disconnect, timeout, or error)
        if user_id in global_connections:
            del global_connections[user_id]
        online_users[user_id] = False
        online_status_timestamp[user_id] = datetime.now()
        logger.info(f"[STATS-WS] User {user_id} ({user_role}) disconnected - marked as offline")
        logger.info(f"[STATS-WS] Total online users: {len([u for u, status in online_users.items() if status])}")
        # Broadcast offline status
        await broadcast_user_status(user_id, False, user_role)
        try:
            await websocket.close()
        except:
            pass

# Helper functions to send events from other parts of the application
async def send_chat_assigned_event(chat_id: int, operator_id: int, chat: Optional[dict] = None):
    """
    Send chat.assigned event when chat is assigned to operator.
    Event: { type: "chat.assigned", chat_id: int, operator_id: int }
    """
    event = {
        "type": "chat.assigned",
        "chat_id": chat_id,
        "operator_id": operator_id
    }
    chat_payload = _serialize_chat(chat)
    if chat_payload:
        event["chat"] = chat_payload

    ws_payload = {
        "chat_id": chat_id,
        "operator_id": operator_id,
        "chat": chat_payload,
    }

    try:
        await chat_ws_manager.emit(chat_id, "chat.assigned", ws_payload)
        logger.info(f"[chat.assigned] Broadcast to chat {chat_id} succeeded")
    except Exception as e:
        logger.warning(f"[chat.assigned] Failed to emit via chat manager for chat {chat_id}: {e}")

    await _send_event_to_global_user(operator_id, event)
    await _broadcast_global_event(event, exclude_user_id=operator_id)


async def send_chat_inactive_event(chat_id: int, chat: Optional[dict] = None):
    """
    Send chat.inactive event when chat becomes inactive.
    Event: { type: "chat.inactive", chat_id: int }
    """
    event = {
        "type": "chat.inactive",
        "chat_id": chat_id
    }
    chat_payload = _serialize_chat(chat)
    if chat_payload:
        event["chat"] = chat_payload
    
    ws_payload = {
        "chat_id": chat_id,
        "chat": chat_payload,
    }

    try:
        await chat_ws_manager.emit(chat_id, "chat.inactive", ws_payload)
        logger.info(f"[chat.inactive] Broadcast to chat {chat_id} succeeded")
    except Exception as e:
        logger.warning(f"[chat.inactive] Failed to emit via chat manager for chat {chat_id}: {e}")

    await _broadcast_global_event(event)


async def send_message_read_event(chat_id: int, message_id: int, user_id: int):
    """
    Send message read event via WebSocket.
    Broadcasts to all chat participants.
    Event: { type: "message.read", chat_id: int, message_id: int, user_id: int }
    """
    try:
        await chat_ws_manager.emit(
            chat_id,
            "message.read",
            {"message_id": message_id, "user_id": user_id}
        )
    except Exception as e:
        logger.warning(f"send_message_read_event: Error broadcasting via chat manager: {e}")


async def send_chat_message_event(chat_id: int, message: Dict[str, Any], event_type: str = "message.new"):
    """
    Send chat message event (new or edited).
    Broadcasts to both old WebSocket endpoint (/ws/chat/{chat_id}) and new endpoint (/ws/chat?chat_id=...)
    Event: { type: "message.new" | "message.edited", chat_id: int, message: {...} }
    """
    # Convert datetime objects to ISO format strings for JSON serialization
    serialized_message = {}
    for key, value in message.items():
        if hasattr(value, 'isoformat'):  # datetime object
            serialized_message[key] = value.isoformat()
        elif isinstance(value, dict):
            # Recursively handle nested dicts
            serialized_message[key] = {
                k: v.isoformat() if hasattr(v, 'isoformat') else v
                for k, v in value.items()
            }
        else:
            serialized_message[key] = value

    global_event = {
        "type": "chat.message",
        "chat_id": chat_id,
        "message": serialized_message
    }
    
    logger.info(f"send_chat_message_event: Broadcasting message for chat {chat_id}, message_id={serialized_message.get('id')}, sender_type={serialized_message.get('sender_type')}")
    
    try:
        await chat_ws_manager.emit(
            chat_id,
            event_type,
            serialized_message
        )
        logger.info(f"send_chat_message_event: Broadcasted via chat manager for chat {chat_id}")
    except Exception as e:
        logger.warning(f"send_chat_message_event: Error broadcasting via chat manager: {e}")
    
    await _broadcast_global_event(global_event)
    logger.info(f"send_chat_message_event: Sent to {len(global_connections)} global connections")


async def send_message_reaction_event(chat_id: int, message_id: int, user_id: int, emoji: str, action: str):
    """
    Send message.reaction event when a reaction is added or removed.
    Event: { type: "message.reaction", chat_id: int, message_id: int, user_id: int, emoji: str, action: "added"|"removed" }
    """
    event = {
        "type": "message.reaction",
        "chat_id": chat_id,
        "message_id": message_id,
        "user_id": user_id,
        "emoji": emoji,
        "action": action
    }
    
    logger.info(f"send_message_reaction_event: Broadcasting reaction for chat {chat_id}, message {message_id}, user {user_id}, emoji {emoji}, action {action}")
    
    try:
        await chat_ws_manager.emit(
            chat_id,
            "message.reaction",
            event
        )
        logger.info(f"send_message_reaction_event: Broadcasted via chat manager for chat {chat_id}")
    except Exception as e:
        logger.warning(f"send_message_reaction_event: Error broadcasting via chat manager: {e}")
    
    await _broadcast_global_event(event)
    logger.info(f"send_message_reaction_event: Sent to {len(global_connections)} global connections")


async def send_stats_changed_event(inbox_count: int, operator_counts: List[Dict[str, Any]]):
    """Send stats.changed event when stats update"""
    event = {
        "type": "stats.changed",
        "inbox_count": inbox_count,
        "operator_counts": operator_counts
    }
    
    # Send to all global connections (supervisors and operators)
    disconnected = []
    for user_id, ws in global_connections.items():
        try:
            await ws.send_json(event)
        except Exception as e:
            logger.error(f"Error sending stats to user {user_id}: {e}")
            disconnected.append(user_id)
    
    # Clean up disconnected users
    for user_id in disconnected:
        if user_id in global_connections:
            del global_connections[user_id]


# ============================================
# STAFF CHAT WEBSOCKET
# ============================================

@router.websocket("/staff-chat/{chat_id}")
async def staff_chat_websocket_endpoint(websocket: WebSocket, chat_id: int):
    """
    WebSocket endpoint for real-time staff chat
    Expects: ?user_id=123 in query params
    """
    logger.info(f"[WebSocket] Connection attempt for chat_id={chat_id}, user_id_param='{websocket.query_params.get('user_id')}'")
    user_id_param = websocket.query_params.get("user_id")
    if not user_id_param:
        await websocket.close(code=1008, reason="user_id parameter required")
        return
    
    try:
        user_id = int(user_id_param)
    except ValueError:
        await websocket.close(code=1008, reason="Invalid user_id parameter")
        return
    
    # Verify chat exists and user is participant
    chat = await get_staff_chat_by_id(chat_id, user_id)
    if not chat:
        await websocket.close(code=1008, reason="Staff chat not found or unauthorized")
        return
    
    # Get user to check role
    user = await get_user_by_id(user_id)
    if not user:
        await websocket.close(code=1008, reason="User not found")
        return
    
    user_role = user.get('role')
    
    # Only allow operators and supervisors
    if user_role not in ('callcenter_operator', 'callcenter_supervisor'):
        await websocket.close(code=1008, reason="Only operators and supervisors can connect to staff chats")
        return
    
    # Connect to staff chat connections
    await websocket.accept()
    
    if chat_id not in staff_chat_connections:
        staff_chat_connections[chat_id] = {}
    
    # If user already has a connection, close the old one first
    if user_id in staff_chat_connections[chat_id]:
        try:
            await staff_chat_connections[chat_id][user_id].close()
            logger.info(f"[STAFF-WS] Closed old connection for user {user_id} in staff chat {chat_id}")
        except Exception as e:
            logger.warning(f"[STAFF-WS] Error closing old connection: {e}")
    
    staff_chat_connections[chat_id][user_id] = websocket
    connected_users = list(staff_chat_connections[chat_id].keys())
    logger.info(f"[STAFF-WS] User {user_id} ({user_role}) connected to staff chat {chat_id}. Total connections: {len(staff_chat_connections[chat_id])}, users: {connected_users}")
    
    try:
        # Send recent messages on connect
        messages = await get_staff_messages(chat_id, limit=50, offset=0)
        await websocket.send_json({
            "type": "initial_messages",
            "chat_id": chat_id,
            "messages": [
                {
                    "id": m.get('id'),
                    "chat_id": m.get('chat_id'),
                    "sender_id": m.get('sender_id'),
                    "message_text": m.get('message_text'),
                    "attachments": m.get('attachments'),
                    "read_by": m.get('read_by'),
                    "created_at": m.get('created_at').isoformat() if m.get('created_at') else None,
                    "sender_name": m.get('sender_name'),
                    "sender_telegram_id": m.get('sender_telegram_id'),
                    "sender_role": m.get('sender_role'),
                }
                for m in messages
            ]
        })
        
        # Listen for messages
        while True:
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "message":
                # Save message to database
                message_text = data.get("message_text", "")
                attachments = data.get("attachments")
                
                if not message_text or not message_text.strip():
                    await websocket.send_json({
                        "type": "error",
                        "message": "Message text cannot be empty"
                    })
                    continue
                
                message_id = await create_staff_message(
                    chat_id=chat_id,
                    sender_id=user_id,
                    message_text=message_text.strip(),
                    attachments=attachments
                )
                
                if not message_id:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Failed to create message"
                    })
                    continue
                
                # Get the created message from database by ID (more reliable than limit/offset)
                created_message = await get_staff_message_by_id(message_id)
                if not created_message:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Failed to retrieve created message"
                    })
                    continue
                
                # Prepare full message data
                full_message_data = {
                    "id": created_message.get('id'),
                    "chat_id": created_message.get('chat_id'),
                    "sender_id": created_message.get('sender_id'),
                    "message_text": created_message.get('message_text'),
                    "attachments": created_message.get('attachments'),
                    "read_by": created_message.get('read_by'),
                    "created_at": created_message.get('created_at').isoformat() if created_message.get('created_at') else None,
                    "sender_name": created_message.get('sender_name'),
                    "sender_telegram_id": created_message.get('sender_telegram_id'),
                    "sender_role": created_message.get('sender_role'),
                }
                
                # Broadcast to all participants except sender
                message_event = {
                    "type": "staff.message",
                    "chat_id": chat_id,
                    "message": full_message_data
                }
                
                await broadcast_staff_message(message_event, chat_id, exclude_user_id=user_id)
                
                # Send confirmation to sender
                await websocket.send_json({
                    "type": "message_sent",
                    "message_id": message_id,
                    "message": full_message_data
                })
            
            elif message_type == "typing":
                # Broadcast typing indicator
                typing_data = {
                    "type": "staff.typing",
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "is_typing": data.get("is_typing", True)
                }
                await broadcast_staff_message(typing_data, chat_id, exclude_user_id=user_id)
            
            elif message_type == "ping":
                # Respond to ping
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        remaining_users = []
        if chat_id in staff_chat_connections:
            if user_id in staff_chat_connections[chat_id]:
                del staff_chat_connections[chat_id][user_id]
            remaining_users = list(staff_chat_connections[chat_id].keys()) if chat_id in staff_chat_connections else []
            if chat_id in staff_chat_connections and not staff_chat_connections[chat_id]:
                del staff_chat_connections[chat_id]
                logger.info(f"[STAFF-WS] Staff chat {chat_id} removed (no connections left)")
        logger.info(f"[STAFF-WS] User {user_id} disconnected from staff chat {chat_id}. Remaining users: {remaining_users}")
    except Exception as e:
        logger.exception(f"[STAFF-WS] Error in staff chat WebSocket connection: {e}")
        if chat_id in staff_chat_connections:
            if user_id in staff_chat_connections[chat_id]:
                del staff_chat_connections[chat_id][user_id]
            if not staff_chat_connections[chat_id]:
                del staff_chat_connections[chat_id]
        try:
            await websocket.close()
        except:
            pass


async def broadcast_staff_message(message: dict, chat_id: int, exclude_user_id: int = None):
    """Broadcast message to all users in a staff chat"""
    logger.info(f"[STAFF-BROADCAST] chat_id={chat_id}, exclude_user_id={exclude_user_id}, message_type={message.get('type')}")
    
    if chat_id in staff_chat_connections:
        connected_users = list(staff_chat_connections[chat_id].keys())
        logger.info(f"[STAFF-BROADCAST] Found {len(staff_chat_connections[chat_id])} connections for staff chat {chat_id}: {connected_users}")
        
        disconnected = []
        sent_count = 0
        for user_id, websocket in list(staff_chat_connections[chat_id].items()):
            if user_id == exclude_user_id:
                logger.info(f"[STAFF-BROADCAST] Skipping user {user_id} (excluded)")
                continue
            try:
                if websocket.client_state.name != 'CONNECTED':
                    logger.warning(f"[STAFF-BROADCAST] WebSocket for user {user_id} is not connected, removing")
                    disconnected.append(user_id)
                    continue
                await websocket.send_json(message)
                sent_count += 1
                logger.info(f"[STAFF-BROADCAST] Sent to user {user_id} in staff chat {chat_id}")
            except Exception as e:
                logger.error(f"[STAFF-BROADCAST] Error sending to user {user_id} in staff chat {chat_id}: {e}")
                disconnected.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected:
            if chat_id in staff_chat_connections:
                if user_id in staff_chat_connections[chat_id]:
                    del staff_chat_connections[chat_id][user_id]
                if not staff_chat_connections[chat_id]:
                    del staff_chat_connections[chat_id]
        
        logger.info(f"[STAFF-BROADCAST] Summary: Sent to {sent_count}/{len(connected_users)} users in staff chat {chat_id}")
    else:
        logger.warning(f"[STAFF-BROADCAST] No active connections for staff chat {chat_id}")


async def send_staff_message_event(chat_id: int, message: Dict[str, Any]):
    """
    Send staff.message event when a new staff message is created.
    Event: { type: "staff.message", chat_id: int, message: {...} }
    """
    # Convert datetime objects to ISO format strings for JSON serialization
    serialized_message = {}
    for key, value in message.items():
        if hasattr(value, 'isoformat'):  # datetime object
            serialized_message[key] = value.isoformat()
        elif isinstance(value, dict):
            # Recursively handle nested dicts
            serialized_message[key] = {
                k: v.isoformat() if hasattr(v, 'isoformat') else v
                for k, v in value.items()
            }
        else:
            serialized_message[key] = value
    
    event = {
        "type": "staff.message",
        "chat_id": chat_id,
        "message": serialized_message
    }
    
    logger.info(f"send_staff_message_event: Sending event for staff chat {chat_id}, message_id={serialized_message.get('id')}")
    
    # Get chat to find participants
    chat = await get_staff_chat_by_id(chat_id, serialized_message.get('sender_id'))
    if not chat:
        logger.error(f"send_staff_message_event: Staff chat {chat_id} not found")
        return
    
    sender_id = chat.get('sender_id')
    receiver_id = chat.get('receiver_id')
    
    # Broadcast to all chat participants
    await broadcast_staff_message(event, chat_id, exclude_user_id=None)

