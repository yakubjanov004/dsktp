# app/ws/chat.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from json.decoder import JSONDecodeError
import logging

from api.ws.manager import manager
from api.ws.rate_limiter import WebSocketRateLimiter, WebsocketTooManyRequests
from api.exceptions import AuthenticationError, AuthorizationError, NotFoundError
from database.webapp.user_queries import get_user_by_telegram_id
from database.webapp.chat_queries import get_chat_by_id
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@manager.handler("typing")
async def handle_typing(
    websocket: WebSocket,
    incoming_message: dict,
    chat_id: int,
    user_id: int,
    user_role: str,
    chat: dict,
    **kwargs
):
    """
    Handle typing indicator events.
    Expected message format: {"type": "typing", "is_typing": bool}
    """
    try:
        is_typing = incoming_message.get("is_typing", True)
        
        # Update typing status
        await manager.set_typing_status(chat_id, user_id, is_typing)
        
        # Broadcast typing event to all participants (sender will ignore their own typing)
        await manager.broadcast_typing_event(chat_id, user_id, is_typing)
        
    except Exception as e:
        logger.error(f"Error handling typing event: {e}", exc_info=True)


def can_user_access_chat(user_id: int, chat_id: int, chat: dict) -> bool:
    """
    Check if user can access a chat.
    
    Args:
        user_id: User ID to check
        chat_id: Chat ID
        chat: Chat dictionary from database
        
    Returns:
        True if user can access, False otherwise
    """
    client_id = chat.get('client_id')
    operator_id = chat.get('operator_id')
    
    # Get user to check role
    # Note: We'll need to pass user info or fetch it
    # For now, allow client, operator, or supervisor
    allowed_users = [client_id]
    if operator_id:
        allowed_users.append(operator_id)
    
    # Supervisors can access any chat (read-only)
    # We'll check this in the endpoint
    
    return user_id in allowed_users


@router.websocket("/ws/chat")
async def chat_ws(
    websocket: WebSocket,
    chat_id: int = Query(..., description="Chat ID"),
    telegram_id: int = Query(..., description="Telegram user ID for authentication")
):
    """
    Enhanced WebSocket endpoint for real-time chat with rate limiting.
    Based on fastapi-chat patterns.
    
    Query parameters:
        chat_id: Chat room ID
        telegram_id: Telegram user ID for authentication
    """
    # Initialize rate limiter
    rate_limiter = None
    if settings.RATE_LIMIT_ENABLED:
        rate_limiter = WebSocketRateLimiter(
            times=settings.WS_RATE_LIMIT_TIMES,
            seconds=settings.WS_RATE_LIMIT_SECONDS
        )
    
    # 1) Auth - Get user by telegram_id
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            logger.warning(f"User not found for telegram_id={telegram_id}")
            await websocket.close(code=4401, reason="User not found")
            return
        
        user_id = user.get('id')
        user_role = user.get('role')
    except Exception as e:
        logger.error(f"Error authenticating user: {e}", exc_info=True)
        await websocket.close(code=4401, reason="Authentication failed")
        return

    # 2) Permission - Check if user can access chat
    try:
        chat = await get_chat_by_id(chat_id)
        if not chat:
            logger.warning(f"Chat {chat_id} not found")
            await websocket.close(code=4404, reason="Chat not found")
            return
        
        client_id = chat.get('client_id')
        operator_id = chat.get('operator_id')
        
        # Allow client, operator, or supervisor
        allowed_users = [client_id]
        if operator_id:
            allowed_users.append(operator_id)
        
        is_supervisor = user_role == 'callcenter_supervisor'
        
        if user_id not in allowed_users and not is_supervisor:
            logger.warning(f"User {user_id} not authorized for chat {chat_id}")
            await websocket.close(code=4403, reason="Access denied")
            return
    except Exception as e:
        logger.error(f"Error checking chat permission: {e}", exc_info=True)
        await websocket.close(code=4403, reason="Permission check failed")
        return

    # 3) Connect
    await manager.connect(chat_id, websocket)
    await manager.add_user_connection(user_id, websocket)
    
    logger.info(f"WebSocket connected: chat_id={chat_id}, user_id={user_id}, role={user_role}")

    try:
        while True:
            try:
                # Receive message (text or JSON)
                # Handle WebSocketDisconnect and RuntimeError (disconnect already received)
                try:
                    data = await websocket.receive_json()
                except (WebSocketDisconnect, RuntimeError) as e:
                    # Disconnect detected - break out of loop
                    if isinstance(e, RuntimeError) and "disconnect" in str(e).lower():
                        logger.info(f"WebSocket disconnect detected (RuntimeError): chat_id={chat_id}, user_id={user_id}")
                    else:
                        logger.info(f"WebSocket disconnected: chat_id={chat_id}, user_id={user_id}")
                    break
                except JSONDecodeError:
                    # Fallback to text if JSON decode fails
                    try:
                        data_text = await websocket.receive_text()
                        data = {"type": "text", "content": data_text}
                    except (WebSocketDisconnect, RuntimeError) as e:
                        # Disconnect detected while receiving text
                        if isinstance(e, RuntimeError) and "disconnect" in str(e).lower():
                            logger.info(f"WebSocket disconnect detected (RuntimeError) during text receive: chat_id={chat_id}, user_id={user_id}")
                        else:
                            logger.info(f"WebSocket disconnected during text receive: chat_id={chat_id}, user_id={user_id}")
                        break
                
                # Rate limiting check
                if rate_limiter:
                    if not await rate_limiter.check_rate_limit(websocket):
                        await manager.send_error(
                            "Rate limit exceeded. Please slow down.",
                            websocket
                        )
                        raise WebsocketTooManyRequests("Too many requests")
                
                # Handle message types
                message_type = data.get("type")
                
                # Heartbeat (ping/pong)
                if message_type == "ping" or data == "ping":
                    try:
                        await websocket.send_json({"type": "pong"})
                    except (WebSocketDisconnect, RuntimeError):
                        # Disconnect detected while sending pong
                        logger.info(f"WebSocket disconnected while sending pong: chat_id={chat_id}, user_id={user_id}")
                        break
                    continue
                
                # Handle other message types using manager handlers
                if message_type and message_type in manager.handlers:
                    handler = manager.handlers[message_type]
                    try:
                        await handler(
                            websocket=websocket,
                            incoming_message=data,
                            chat_id=chat_id,
                            user_id=user_id,
                            user_role=user_role,
                            chat=chat
                        )
                    except (WebSocketDisconnect, RuntimeError) as e:
                        # Disconnect detected in handler
                        if isinstance(e, RuntimeError) and "disconnect" in str(e).lower():
                            logger.info(f"WebSocket disconnect detected (RuntimeError) in handler: chat_id={chat_id}, user_id={user_id}")
                        else:
                            logger.info(f"WebSocket disconnected in handler: chat_id={chat_id}, user_id={user_id}")
                        break
                    except Exception as e:
                        logger.error(f"Error in handler {message_type}: {e}", exc_info=True)
                        try:
                            await manager.send_error(
                                f"Error processing {message_type}: {str(e)}",
                                websocket
                            )
                        except (WebSocketDisconnect, RuntimeError):
                            # Disconnect detected while sending error
                            logger.info(f"WebSocket disconnected while sending error: chat_id={chat_id}, user_id={user_id}")
                            break
                else:
                    # Unknown message type
                    logger.warning(f"Unknown message type: {message_type}")
                    try:
                        await manager.send_error(
                            f"Unknown message type: {message_type}",
                            websocket
                        )
                    except (WebSocketDisconnect, RuntimeError):
                        # Disconnect detected while sending error
                        logger.info(f"WebSocket disconnected while sending error: chat_id={chat_id}, user_id={user_id}")
                        break
                
            except WebsocketTooManyRequests:
                logger.warning(f"Rate limit exceeded for user {user_id} in chat {chat_id}")
                try:
                    await websocket.close(code=1008, reason="Rate limit exceeded")
                except (WebSocketDisconnect, RuntimeError):
                    pass
                break
            except (WebSocketDisconnect, RuntimeError) as e:
                # Disconnect detected in outer try-except
                if isinstance(e, RuntimeError) and "disconnect" in str(e).lower():
                    logger.info(f"WebSocket disconnect detected (RuntimeError) in outer handler: chat_id={chat_id}, user_id={user_id}")
                else:
                    logger.info(f"WebSocket disconnected in outer handler: chat_id={chat_id}, user_id={user_id}")
                break
            except JSONDecodeError as e:
                logger.warning(f"Invalid JSON from user {user_id}: {e}")
                try:
                    await manager.send_error("Invalid message format", websocket)
                except (WebSocketDisconnect, RuntimeError):
                    # Disconnect detected while sending error
                    logger.info(f"WebSocket disconnected while sending error: chat_id={chat_id}, user_id={user_id}")
                    break
                continue
            except Exception as e:
                logger.error(f"Error processing message from user {user_id}: {e}", exc_info=True)
                try:
                    await manager.send_error("Error processing message", websocket)
                except (WebSocketDisconnect, RuntimeError):
                    # Disconnect detected while sending error
                    logger.info(f"WebSocket disconnected while sending error: chat_id={chat_id}, user_id={user_id}")
                    break
                continue
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected (outer catch): chat_id={chat_id}, user_id={user_id}")
    except Exception as e:
        logger.exception(f"Unexpected error in WebSocket connection: {e}")
    finally:
        # Cleanup - clear typing status on disconnect
        await manager.set_typing_status(chat_id, user_id, False)
        await manager.disconnect(chat_id, websocket)
        await manager.remove_user_connection(user_id, websocket)
        try:
            await websocket.close()
        except:
            pass

