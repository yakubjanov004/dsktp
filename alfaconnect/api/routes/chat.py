"""
Chat-related API endpoints
"""
from fastapi import APIRouter, HTTPException, Query, Body, UploadFile, File
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import os
import uuid
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
from database.webapp.chat_queries import (
    create_chat,
    get_user_chats,
    get_chat_by_id,
    assign_chat_to_operator,
    close_chat,
    get_active_chats_count,
    update_chat_activity,
    mark_inactive_chats,
    get_supervisor_inbox,
    get_operator_chats,
    get_supervisor_active_chats,
    get_active_chat_counts,
    pin_chat,
    unpin_chat,
    get_pinned_chats
)
from api.routes.websocket import (
    send_chat_assigned_event,
    send_chat_inactive_event,
    send_chat_new_event,
    send_stats_changed_event,
)
from database.webapp.message_queries import (
    create_message,
    get_chat_messages,
    get_unread_messages_count,
    get_message_by_id,
    mark_message_read,
    get_message_reads,
    mark_chat_messages_read,
    get_message_reactions,
    toggle_message_reaction,
    search_messages,
    forward_message,
    get_chat_media,
    edit_message,
    get_message_thread
)
from database.webapp.user_queries import get_user_by_telegram_id, get_user_by_id
from config import settings
from database.webapp.staff_chat_queries import (
    create_staff_chat,
    get_staff_chats,
    get_staff_chat_by_id,
    create_staff_message,
    get_staff_messages,
    get_staff_message_by_id,
    get_available_staff,
    close_staff_chat
)
from database.webapp.ccs_statistics import (
    get_ccs_comprehensive_statistics,
    get_operator_statistics,
    get_online_users_summary,
    get_recent_clients
)

router = APIRouter()


class CreateChatRequest(BaseModel):
    client_id: int
    operator_id: Optional[int] = None  # Usually NULL, set by CCS via assign


class SendMessageRequest(BaseModel):
    chat_id: int
    sender_id: int
    message_text: str  # Required per new schema
    sender_type: str  # 'client', 'operator', or 'system'
    operator_id: Optional[int] = None  # Required when sender_type='operator', must match sender_id
    attachments: Optional[Dict[str, Any]] = None  # JSONB attachments
    reply_to_message_id: Optional[int] = None  # ID of the message being replied to


class AssignChatRequest(BaseModel):
    operator_id: int


class CreateStaffChatRequest(BaseModel):
    receiver_id: int


class SendStaffMessageRequest(BaseModel):
    sender_id: int
    message_text: str
    attachments: Optional[Dict[str, Any]] = None


class ReactionRequest(BaseModel):
    emoji: str  # Emoji string (e.g., "👍", "❤️", "😂")


@router.get("/list")
async def get_chats(
    telegram_id: int = Query(..., description="Telegram user ID"),
    status: Optional[str] = Query(None, description="Chat status filter (active, inactive)")
):
    """
    Get chats for user based on their role
    """
    try:
        # Get user to determine role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        role = user.get('role')
        
        # Debug logging
        print(f"[API] /chat/list: telegram_id={telegram_id}, user_id={user_id}, role={role}")
        
        chats = await get_user_chats(user_id, role, status)
        
        # Debug logging
        print(f"[API] /chat/list: Found {len(chats)} chats for user_id={user_id}")
        for chat in chats:
            print(f"[API] /chat/list: Chat id={chat.get('id')}, client_id={chat.get('client_id')}, status={chat.get('status')}")
        
        # Convert datetime objects to strings
        for chat in chats:
            if chat.get('created_at'):
                chat['created_at'] = chat['created_at'].isoformat()
            if chat.get('updated_at'):
                chat['updated_at'] = chat['updated_at'].isoformat()
            if chat.get('last_activity_at'):
                chat['last_activity_at'] = chat['last_activity_at'].isoformat()
            if chat.get('pinned_at'):
                chat['pinned_at'] = chat['pinned_at'].isoformat()
        
        return {"chats": chats, "count": len(chats)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching chats: {str(e)}")


@router.post("/create")
async def create_new_chat(request: CreateChatRequest):
    """
    Create a new chat or reactivate existing inactive chat for client.
    Ensures one active chat per client (enforced by partial unique constraint).
    Client sends first message -> chat created -> operator_id is NULL -> goes to CCS inbox.
    """
    try:
        # Validate request
        if not request.client_id:
            raise HTTPException(status_code=400, detail="client_id is required")
        
        # create_chat() handles: checking for existing active chat, reactivating inactive chat, or creating new
        # Returns full chat dict, not just ID
        chat = await create_chat(
            client_id=request.client_id,
            operator_id=request.operator_id  # Usually NULL, set by CCS via assign
        )
        
        if not chat:
            raise HTTPException(status_code=500, detail="Failed to create chat - no chat returned")
        
        # Get full chat details with user names
        chat_id = chat.get('id')
        if not chat_id:
            raise HTTPException(status_code=500, detail="Failed to create chat - no ID in returned chat")
        
        # Get the created/reactivated chat with full details (client_name, operator_name, etc.)
        chat = await get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=500, detail="Failed to retrieve created chat")
        
        # Convert datetime objects to strings
        if chat.get('created_at'):
            chat['created_at'] = chat['created_at'].isoformat()
        if chat.get('updated_at'):
            chat['updated_at'] = chat['updated_at'].isoformat()
        if chat.get('last_activity_at'):
            chat['last_activity_at'] = chat['last_activity_at'].isoformat()
        
        # Broadcast new chat event to supervisors/operators for real-time inbox updates
        await send_chat_new_event(chat)
        
        # Update stats so inbox counters refresh instantly
        stats = await get_active_chat_counts()
        await send_stats_changed_event(stats['inbox_count'], stats['operator_counts'])
        
        return chat
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating chat: {str(e)}")


# NOTE: /{chat_id} endpoints are placed AFTER static paths (/inbox, /active, /my, /stats/*, /mark-inactive)
# to avoid FastAPI routing conflicts. See section "DYNAMIC CHAT ID ENDPOINTS" below.


@router.get("/stats/active-count")
async def get_active_chats_count_endpoint(
    telegram_id: Optional[int] = Query(None, description="Telegram user ID (operator)")
):
    """
    Get count of active chats (legacy endpoint for backward compatibility)
    """
    try:
        operator_id = None
        if telegram_id:
            user = await get_user_by_telegram_id(telegram_id)
            if user:
                operator_id = user.get('id')
        
        count = await get_active_chats_count(operator_id)
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching active chats count: {str(e)}")


@router.get("/stats/active")
async def get_active_chat_stats():
    """
    Get active chat statistics: inbox_count and operator_counts in one call.
    Returns: { inbox_count: int, operator_counts: [{operator_id: int, cnt: int}, ...] }
    """
    try:
        stats = await get_active_chat_counts()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching active chat stats: {str(e)}")


@router.get("/inbox")
async def get_inbox(
    telegram_id: int = Query(..., description="Telegram user ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of chats"),
    cursor_ts: Optional[str] = Query(None, description="Cursor timestamp (ISO format)"),
    cursor_id: Optional[int] = Query(None, description="Cursor chat ID")
):
    """
    Get supervisor inbox (chats without operator) with cursor-based pagination.
    Only accessible by supervisors.
    """
    try:
        # Get user to verify role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        role = user.get('role')
        if role != 'callcenter_supervisor':
            raise HTTPException(status_code=403, detail="Only supervisors can access inbox")
        
        cursor_timestamp = None
        if cursor_ts and cursor_ts.strip():
            try:
                cursor_timestamp = datetime.fromisoformat(cursor_ts.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                raise HTTPException(status_code=400, detail="Invalid cursor_ts format. Use ISO format.")
        
        result = await get_supervisor_inbox(limit=limit, cursor_ts=cursor_timestamp, cursor_id=cursor_id)
        
        # get_supervisor_inbox returns a dict with "chats" and "count"
        chats = result.get("chats", [])
        count = result.get("count", len(chats))
        
        # Convert datetime objects to strings
        for chat in chats:
            if chat.get('created_at'):
                chat['created_at'] = chat['created_at'].isoformat()
            if chat.get('updated_at'):
                chat['updated_at'] = chat['updated_at'].isoformat()
            if chat.get('last_activity_at'):
                chat['last_activity_at'] = chat['last_activity_at'].isoformat()
        
        return {"chats": chats, "count": count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching inbox: {str(e)}")


@router.get("/active")
async def get_active_chats(
    telegram_id: int = Query(..., description="Telegram user ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of chats"),
    cursor_ts: Optional[str] = Query(None, description="Cursor timestamp (ISO format)"),
    cursor_id: Optional[int] = Query(None, description="Cursor chat ID")
):
    """
    Get supervisor active chats (assigned chats) with cursor-based pagination.
    Only accessible by supervisors.
    """
    try:
        # Get user to verify role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        role = user.get('role')
        if role != 'callcenter_supervisor':
            raise HTTPException(status_code=403, detail="Only supervisors can access active chats")
        
        cursor_timestamp = None
        if cursor_ts and cursor_ts.strip():
            try:
                cursor_timestamp = datetime.fromisoformat(cursor_ts.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                raise HTTPException(status_code=400, detail="Invalid cursor_ts format. Use ISO format.")
        
        result = await get_supervisor_active_chats(limit=limit, cursor_ts=cursor_timestamp, cursor_id=cursor_id)
        
        # get_supervisor_active_chats returns a dict with "chats" and "count"
        chats = result.get("chats", [])
        count = result.get("count", len(chats))
        
        # Convert datetime objects to strings
        for chat in chats:
            if chat.get('created_at'):
                chat['created_at'] = chat['created_at'].isoformat()
            if chat.get('updated_at'):
                chat['updated_at'] = chat['updated_at'].isoformat()
            if chat.get('last_activity_at'):
                chat['last_activity_at'] = chat['last_activity_at'].isoformat()
            if chat.get('last_client_activity_at'):
                chat['last_client_activity_at'] = chat['last_client_activity_at'].isoformat()
        
        return {"chats": chats, "count": count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching active chats: {str(e)}")


@router.get("/my")
async def get_my_chats(
    telegram_id: int = Query(..., description="Telegram user ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of chats"),
    cursor_ts: Optional[str] = Query(None, description="Cursor timestamp (ISO format)"),
    cursor_id: Optional[int] = Query(None, description="Cursor chat ID")
):
    """
    Get operator's assigned chats with cursor-based pagination.
    """
    try:
        # Get user to determine operator ID
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        role = user.get('role')
        
        if role != 'callcenter_operator':
            raise HTTPException(status_code=403, detail="Only operators can access this endpoint")
        
        cursor_timestamp = None
        if cursor_ts and cursor_ts.strip():
            try:
                cursor_timestamp = datetime.fromisoformat(cursor_ts.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                raise HTTPException(status_code=400, detail="Invalid cursor_ts format. Use ISO format.")
        
        result = await get_operator_chats(operator_id=user_id, limit=limit, cursor_ts=cursor_timestamp, cursor_id=cursor_id)
        
        # get_operator_chats returns a dict with "chats" and "count"
        chats = result.get("chats", [])
        count = result.get("count", len(chats))
        
        # Convert datetime objects to strings
        for chat in chats:
            if chat.get('created_at'):
                chat['created_at'] = chat['created_at'].isoformat()
            if chat.get('updated_at'):
                chat['updated_at'] = chat['updated_at'].isoformat()
            if chat.get('last_activity_at'):
                chat['last_activity_at'] = chat['last_activity_at'].isoformat()
        
        return {"chats": chats, "count": count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching operator chats: {str(e)}")


@router.post("/mark-inactive")
async def mark_inactive_chats_endpoint():
    """
    Mark chats as inactive if they haven't been active for 1 hour or more.
    This endpoint should be called periodically (e.g., every 5-10 minutes) by a cron job or scheduler.
    Sends WebSocket events: chat.inactive for each chat and stats.changed
    """
    import time
    from utils.monitoring import log_mark_inactive_result
    
    start_time = time.time()
    try:
        from api.routes.websocket import send_chat_inactive_event
        
        # Get chats that will be marked inactive (before marking)
        from database.webapp.chat_queries import get_chat_by_id
        import asyncpg
        from config import settings
        
        conn = await asyncpg.connect(settings.DB_URL)
        try:
            chat_ids = await conn.fetch("""
                SELECT id FROM chats
                WHERE status = 'active'
                  AND last_activity_at < now() - interval '1 hour'
            """)
        finally:
            await conn.close()
        
        # Mark as inactive
        count = await mark_inactive_chats()
        
        # Send chat.inactive events
        for row in chat_ids:
            await send_chat_inactive_event(row['id'])
        
        # Update stats and send stats.changed event
        if count > 0:
            stats = await get_active_chat_counts()
            await send_stats_changed_event(stats['inbox_count'], stats['operator_counts'])
        
        execution_time = time.time() - start_time
        await log_mark_inactive_result(count, execution_time)
        
        return {"status": "success", "chats_marked_inactive": count}
    except Exception as e:
        execution_time = time.time() - start_time
        await log_mark_inactive_result(0, execution_time)
        raise HTTPException(status_code=500, detail=f"Error marking inactive chats: {str(e)}")


# ============================================
# DYNAMIC CHAT ID ENDPOINTS
# NOTE: These endpoints use path parameter {chat_id} and MUST be placed
# AFTER all static paths (/inbox, /active, /my, /stats/*, /mark-inactive)
# to avoid FastAPI routing conflicts where "inbox" would be parsed as chat_id.
# ============================================

@router.get("/{chat_id}")
async def get_chat_by_id_endpoint(chat_id: int):
    """
    Get chat by ID
    """
    try:
        chat = await get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Convert datetime objects to strings
        if chat.get('created_at'):
            chat['created_at'] = chat['created_at'].isoformat()
        if chat.get('updated_at'):
            chat['updated_at'] = chat['updated_at'].isoformat()
        if chat.get('last_activity_at'):
            chat['last_activity_at'] = chat['last_activity_at'].isoformat()
        
        return chat
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching chat: {str(e)}")


@router.get("/{chat_id}/messages")
async def get_chat_messages_endpoint(
    chat_id: int,
    limit: int = Query(100, ge=1, le=200, description="Maximum number of messages"),
    offset: int = Query(0, ge=0, description="Offset for pagination (used if cursor not provided)"),
    cursor_ts: Optional[str] = Query(None, description="Cursor timestamp (ISO format)"),
    cursor_id: Optional[int] = Query(None, description="Cursor message ID"),
    since_ts: Optional[str] = Query(None, description="Get messages after this timestamp (ISO format)"),
    since_id: Optional[int] = Query(None, description="Get messages after this message ID"),
    all_messages: bool = Query(False, description="Return all messages in chronological order (for supervisors)")
):
    """
    Get messages for a chat with cursor-based pagination (preferred) or offset pagination (fallback)
    If all_messages=true, returns ALL messages in chronological order (oldest first)
    Supports since_ts/since_id for syncing messages after reconnect
    """
    try:
        print(f"[API] /chat/{chat_id}/messages: Request received", {
            "chat_id": chat_id,
            "limit": limit,
            "offset": offset,
            "cursor_ts": cursor_ts,
            "cursor_id": cursor_id,
            "since_ts": since_ts,
            "since_id": since_id,
            "all_messages": all_messages
        })
        
        # Verify chat exists
        chat = await get_chat_by_id(chat_id)
        if not chat:
            print(f"[API] /chat/{chat_id}/messages: Chat not found")
            raise HTTPException(status_code=404, detail=f"Chat {chat_id} not found")
        
        print(f"[API] /chat/{chat_id}/messages: Chat found", {
            "chat_id": chat.get('id'),
            "client_id": chat.get('client_id'),
            "operator_id": chat.get('operator_id'),
            "status": chat.get('status')
        })
        
        cursor_timestamp = None
        if cursor_ts:
            try:
                cursor_timestamp = datetime.fromisoformat(cursor_ts.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid cursor_ts format. Use ISO format.")
        
        since_timestamp = None
        if since_ts:
            try:
                since_timestamp = datetime.fromisoformat(since_ts.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid since_ts format. Use ISO format.")
        
        print(f"[API] /chat/{chat_id}/messages: Calling get_chat_messages", {
            "chat_id": chat_id,
            "limit": limit,
            "offset": offset,
            "all_messages": all_messages
        })
        
        messages = await get_chat_messages(
            chat_id, 
            limit=limit, 
            offset=offset,
            cursor_ts=cursor_timestamp,
            cursor_id=cursor_id,
            since_ts=since_timestamp,
            since_id=since_id,
            all_messages=all_messages
        )
        
        print(f"[API] /chat/{chat_id}/messages: Retrieved {len(messages)} messages from database")
        
        # Convert datetime objects to strings
        for message in messages:
            if message.get('created_at'):
                message['created_at'] = message['created_at'].isoformat()
        
        print(f"[API] /chat/{chat_id}/messages: Returning {len(messages)} messages")
        
        return {"messages": messages, "count": len(messages)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] /chat/{chat_id}/messages: Error occurred", {
            "chat_id": chat_id,
            "error": str(e),
            "error_type": type(e).__name__
        })
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching messages: {str(e)}")


@router.post("/{chat_id}/messages")
async def send_chat_message_endpoint(chat_id: int, request: SendMessageRequest):
    """
    Send a message in a chat.
    Messages are immutable (no updates/deletes allowed per schema).
    Chat activity is automatically updated by trigger.
    """
    try:
        # Verify chat exists
        chat = await get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Verify sender is participant
        client_id = chat.get('client_id')
        operator_id = chat.get('operator_id')
        
        # Get sender user to check role (for supervisor access)
        sender_user = None
        sender_role = None
        try:
            sender_user = await get_user_by_id(request.sender_id)
            sender_role = sender_user.get('role') if sender_user else None
        except Exception as e:
            logger.warning(f"Could not get sender user by id {request.sender_id}: {e}")
        
        # Allow client, operator, or supervisor to send messages
        allowed_users = [client_id]
        if operator_id:
            allowed_users.append(operator_id)
        
        # Supervisors can send messages to any chat
        is_supervisor = sender_role == 'callcenter_supervisor'
        
        if request.sender_id not in allowed_users and not is_supervisor:
            raise HTTPException(status_code=403, detail="User is not a participant in this chat")
        
        # Validate message text (required per new schema)
        if not request.message_text or not request.message_text.strip():
            raise HTTPException(status_code=400, detail="Message text cannot be empty")
        
        # Validate sender_type
        if request.sender_type not in ('client', 'operator', 'system'):
            raise HTTPException(status_code=400, detail="Invalid sender_type. Must be 'client', 'operator', or 'system'")
        
        # Determine operator_id and sender_id based on sender_type
        # GOTCHA: Operator messages must have operator_id = sender_id
        # GOTCHA: System messages must have sender_id = NULL and operator_id = NULL
        operator_id_for_message = None
        sender_id_for_message = request.sender_id
        
        if request.sender_type == 'operator':
            # For operator messages, operator_id must match sender_id (CHECK constraint requirement)
            if request.operator_id and request.operator_id != request.sender_id:
                raise HTTPException(
                    status_code=400, 
                    detail="operator_id must match sender_id for operator messages (gotcha: CHECK constraint requirement)"
                )
            operator_id_for_message = request.sender_id
        elif request.sender_type == 'system':
            # System messages: sender_id must be NULL (CHECK constraint requirement)
            # GOTCHA: System messages don't reactivate chat (trigger logic)
            sender_id_for_message = None
            operator_id_for_message = None
        # For client messages, operator_id is NULL
        
        # Validate reply_to_message_id if provided
        reply_to_message_id = request.reply_to_message_id
        if reply_to_message_id:
            # Verify that the reply message exists and belongs to the same chat
            reply_message = await get_message_by_id(reply_to_message_id)
            if not reply_message:
                raise HTTPException(status_code=404, detail="Reply message not found")
            if reply_message.get('chat_id') != chat_id:
                raise HTTPException(status_code=400, detail="Reply message must be in the same chat")
        
        message_id = await create_message(
            chat_id=chat_id,
            sender_id=sender_id_for_message,
            message_text=request.message_text.strip(),
            sender_type=request.sender_type,
            operator_id=operator_id_for_message,
            attachments=request.attachments,
            reply_to_message_id=reply_to_message_id
        )
        
        if not message_id:
            raise HTTPException(status_code=500, detail="Failed to create message - no ID returned")
        
        # Send WebSocket event to all connected clients (both old and new endpoints)
        message = await get_message_by_id(message_id)
        if message:
            from api.routes.websocket import send_chat_message_event
            await send_chat_message_event(chat_id, message)
        
        return {"message_id": message_id, "status": "sent"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending message: {str(e)}")


@router.put("/{chat_id}/close")
async def close_chat_by_id_endpoint(chat_id: int):
    """
    Mark chat as inactive (chats cannot be deleted per schema rules).
    This sets status='inactive' and operator_id=NULL.
    """
    try:
        success = await close_chat(chat_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to close chat")
        
        # Send WebSocket event with updated chat payload
        updated_chat = await get_chat_by_id(chat_id)
        await send_chat_inactive_event(chat_id, updated_chat)
        
        # Update stats
        stats = await get_active_chat_counts()
        from api.routes.websocket import send_stats_changed_event
        await send_stats_changed_event(stats['inbox_count'], stats['operator_counts'])
        
        return {"status": "inactive", "chat_id": chat_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error closing chat: {str(e)}")


@router.put("/{chat_id}/assign")
async def assign_chat_to_operator_endpoint(chat_id: int, request: AssignChatRequest):
    """
    Assign chat to operator with race condition check.
    Returns 409 if chat already assigned (race condition).
    Sends WebSocket events: chat.assigned, chat.operator_changed (if operator changed), and stats.changed
    """
    try:
        # Get current chat info to check if operator is changing
        chat = await get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        old_operator_id = chat.get('operator_id')
        
        success = await assign_chat_to_operator(chat_id, request.operator_id)
        if not success:
            # Chat already assigned by another supervisor (race condition)
            # Track conflict for monitoring
            from utils.monitoring import track_db_conflict
            await track_db_conflict("ux_chat_assignment_log_chat_open")
            raise HTTPException(
                status_code=409, 
                detail="Chat already assigned to another operator (race condition detected)"
            )
        
        # Send WebSocket events with updated chat payload
        updated_chat = await get_chat_by_id(chat_id)
        await send_chat_assigned_event(chat_id, request.operator_id, updated_chat)
        
        # Update stats and send stats.changed event
        stats = await get_active_chat_counts()
        await send_stats_changed_event(stats['inbox_count'], stats['operator_counts'])
        
        return {"status": "assigned", "chat_id": chat_id, "operator_id": request.operator_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error assigning chat: {str(e)}")


@router.get("/{chat_id}/client-info")
async def get_chat_client_info_endpoint(chat_id: int):
    """
    Get client info for a chat (for operators)
    """
    try:
        chat = await get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        client_id = chat.get('client_id')
        from database.webapp.user_queries import get_client_info
        
        client_info = await get_client_info(client_id)
        if not client_info:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Convert datetime objects to strings
        if client_info.get('created_at'):
            client_info['created_at'] = client_info['created_at'].isoformat()
        if client_info.get('updated_at'):
            client_info['updated_at'] = client_info['updated_at'].isoformat()
        
        return client_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching client info: {str(e)}")


# ============================================
# STAFF CHAT ENDPOINTS
# ============================================

@router.get("/staff/list")
async def get_staff_chats_endpoint(
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Get staff chats for a user (both as sender and receiver).
    Only accessible by operators and supervisors.
    """
    try:
        # Get user to determine role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        role = user.get('role')
        
        # Only allow operators and supervisors
        if role not in ('callcenter_operator', 'callcenter_supervisor'):
            raise HTTPException(status_code=403, detail="Only operators and supervisors can access staff chats")
        
        result = await get_staff_chats(user_id, limit=50, offset=0)
        chats = result.get('chats', [])
        
        # Convert datetime objects to strings
        for chat in chats:
            if chat.get('created_at'):
                chat['created_at'] = chat['created_at'].isoformat()
            if chat.get('updated_at'):
                chat['updated_at'] = chat['updated_at'].isoformat()
            if chat.get('last_activity_at'):
                chat['last_activity_at'] = chat['last_activity_at'].isoformat()
        
        return {"chats": chats, "count": result.get('count', len(chats))}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching staff chats: {str(e)}")


@router.post("/staff/create")
async def create_staff_chat_endpoint(
    telegram_id: int = Query(..., description="Telegram user ID (sender)"),
    request: CreateStaffChatRequest = Body(...)
):
    """
    Create a new staff chat or return existing active chat.
    Only accessible by operators and supervisors.
    """
    try:
        # Get user to determine role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        sender_id = user.get('id')
        role = user.get('role')
        
        # Only allow operators and supervisors
        if role not in ('callcenter_operator', 'callcenter_supervisor'):
            raise HTTPException(status_code=403, detail="Only operators and supervisors can create staff chats")
        
        if not request.receiver_id:
            raise HTTPException(status_code=400, detail="receiver_id is required")
        
        if sender_id == request.receiver_id:
            raise HTTPException(status_code=400, detail="Cannot create chat with yourself")
        
        # Create or get existing chat
        chat_result = await create_staff_chat(sender_id, request.receiver_id)
        
        if not chat_result or not chat_result.get('id'):
            raise HTTPException(status_code=500, detail="Failed to create staff chat - no ID returned")
        
        chat_id = chat_result.get('id')
        
        # Get the created/existing chat with user names
        chat = await get_staff_chat_by_id(chat_id, sender_id)
        if not chat:
            raise HTTPException(status_code=500, detail="Failed to retrieve created staff chat")
        
        # Convert datetime objects to strings
        if chat.get('created_at'):
            chat['created_at'] = chat['created_at'].isoformat()
        if chat.get('updated_at'):
            chat['updated_at'] = chat['updated_at'].isoformat()
        if chat.get('last_activity_at'):
            chat['last_activity_at'] = chat['last_activity_at'].isoformat()
        
        return chat
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating staff chat: {str(e)}")


@router.get("/staff/{chat_id}")
async def get_staff_chat_endpoint(
    chat_id: int,
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Get staff chat by ID (with authorization check).
    Only accessible by operators and supervisors who are participants.
    """
    try:
        # Get user to determine role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        role = user.get('role')
        
        # Only allow operators and supervisors
        if role not in ('callcenter_operator', 'callcenter_supervisor'):
            raise HTTPException(status_code=403, detail="Only operators and supervisors can access staff chats")
        
        chat = await get_staff_chat_by_id(chat_id, user_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Staff chat not found or unauthorized")
        
        # Convert datetime objects to strings
        if chat.get('created_at'):
            chat['created_at'] = chat['created_at'].isoformat()
        if chat.get('updated_at'):
            chat['updated_at'] = chat['updated_at'].isoformat()
        if chat.get('last_activity_at'):
            chat['last_activity_at'] = chat['last_activity_at'].isoformat()
        
        return chat
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching staff chat: {str(e)}")


@router.get("/staff/{chat_id}/messages")
async def get_staff_messages_endpoint(
    chat_id: int,
    telegram_id: int = Query(..., description="Telegram user ID"),
    limit: int = Query(100, ge=1, le=200, description="Maximum number of messages"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Get messages for a staff chat with pagination.
    Only accessible by operators and supervisors who are participants.
    """
    try:
        print(f"[API] /chat/staff/{chat_id}/messages: Request received", {
            "chat_id": chat_id,
            "telegram_id": telegram_id,
            "limit": limit,
            "offset": offset
        })
        
        # Get user to determine role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            print(f"[API] /chat/staff/{chat_id}/messages: User not found")
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        role = user.get('role')
        
        print(f"[API] /chat/staff/{chat_id}/messages: User found", {
            "user_id": user_id,
            "role": role
        })
        
        # Only allow operators and supervisors
        if role not in ('callcenter_operator', 'callcenter_supervisor'):
            print(f"[API] /chat/staff/{chat_id}/messages: Access denied - role not allowed", {"role": role})
            raise HTTPException(status_code=403, detail="Only operators and supervisors can access staff chats")
        
        # Verify user is participant
        chat = await get_staff_chat_by_id(chat_id, user_id)
        if not chat:
            print(f"[API] /chat/staff/{chat_id}/messages: Staff chat not found or unauthorized", {
                "chat_id": chat_id,
                "user_id": user_id
            })
            raise HTTPException(status_code=404, detail="Staff chat not found or unauthorized")
        
        print(f"[API] /chat/staff/{chat_id}/messages: Staff chat found", {
            "chat_id": chat.get('id'),
            "sender_id": chat.get('sender_id'),
            "receiver_id": chat.get('receiver_id'),
            "status": chat.get('status')
        })
        
        print(f"[API] /chat/staff/{chat_id}/messages: Calling get_staff_messages", {
            "chat_id": chat_id,
            "limit": limit,
            "offset": offset
        })
        
        messages = await get_staff_messages(chat_id, limit=limit, offset=offset)
        
        print(f"[API] /chat/staff/{chat_id}/messages: Retrieved {len(messages)} messages from database")
        
        # Convert datetime objects to strings
        for message in messages:
            if message.get('created_at'):
                message['created_at'] = message['created_at'].isoformat()
        
        print(f"[API] /chat/staff/{chat_id}/messages: Returning {len(messages)} messages")
        
        return {"messages": messages, "count": len(messages)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] /chat/staff/{chat_id}/messages: Error occurred", {
            "chat_id": chat_id,
            "error": str(e),
            "error_type": type(e).__name__
        })
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching staff messages: {str(e)}")


@router.post("/staff/{chat_id}/messages")
async def send_staff_message_endpoint(
    chat_id: int,
    telegram_id: int = Query(..., description="Telegram user ID (sender)"),
    request: SendStaffMessageRequest = Body(...)
):
    """
    Send a message in a staff chat.
    Only accessible by operators and supervisors who are participants.
    """
    try:
        # Get user to determine role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        sender_id = user.get('id')
        role = user.get('role')
        
        # Only allow operators and supervisors
        if role not in ('callcenter_operator', 'callcenter_supervisor'):
            raise HTTPException(status_code=403, detail="Only operators and supervisors can send staff messages")
        
        # Verify sender_id matches
        if request.sender_id != sender_id:
            raise HTTPException(status_code=403, detail="sender_id must match authenticated user")
        
        # Verify chat exists and user is participant
        chat = await get_staff_chat_by_id(chat_id, sender_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Staff chat not found or unauthorized")
        
        # Validate message text
        if not request.message_text or not request.message_text.strip():
            raise HTTPException(status_code=400, detail="Message text cannot be empty")
        
        # Create message
        message_id = await create_staff_message(
            chat_id=chat_id,
            sender_id=sender_id,
            message_text=request.message_text.strip(),
            attachments=request.attachments
        )
        
        if not message_id:
            raise HTTPException(status_code=500, detail="Failed to create staff message - no ID returned")
        
        # Send WebSocket event - get message by ID (more reliable than limit/offset)
        from api.routes.websocket import send_staff_message_event
        created_message = await get_staff_message_by_id(message_id)
        if created_message:
            await send_staff_message_event(chat_id, created_message)
        
        return {"message_id": message_id, "status": "sent"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending staff message: {str(e)}")


@router.get("/staff/available")
async def get_available_staff_endpoint(
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Get list of available staff members for chat (operators and supervisors).
    Excludes the requesting user.
    Only accessible by operators and supervisors.
    """
    try:
        # Get user to determine role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        role = user.get('role')
        
        # Only allow operators and supervisors
        if role not in ('callcenter_operator', 'callcenter_supervisor'):
            raise HTTPException(status_code=403, detail="Only operators and supervisors can access available staff list")
        
        staff_list = await get_available_staff(user_id, role)
        
        # Convert datetime objects to strings
        for staff in staff_list:
            if staff.get('created_at'):
                staff['created_at'] = staff['created_at'].isoformat()
            if staff.get('updated_at'):
                staff['updated_at'] = staff['updated_at'].isoformat()
        
        return {"staff": staff_list, "count": len(staff_list)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching available staff: {str(e)}")


@router.put("/staff/{chat_id}/close")
async def close_staff_chat_endpoint(
    chat_id: int,
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Mark staff chat as inactive.
    Only accessible by operators and supervisors who are participants.
    """
    try:
        # Get user to determine role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        role = user.get('role')
        
        # Only allow operators and supervisors
        if role not in ('callcenter_operator', 'callcenter_supervisor'):
            raise HTTPException(status_code=403, detail="Only operators and supervisors can close staff chats")
        
        success = await close_staff_chat(chat_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Staff chat not found or unauthorized")
        
        return {"status": "inactive", "chat_id": chat_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error closing staff chat: {str(e)}")


# ============================================
# CCS STATISTICS ENDPOINTS
# ============================================

@router.get("/ccs/statistics")
async def get_ccs_statistics_endpoint(
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Get comprehensive CCS statistics:
    - Operators list with online status, last seen, answered chats count
    - Clients list with online status, last seen
    - Overview statistics
    - Daily trends
    
    Only accessible by supervisors and operators.
    """
    try:
        # Get user to verify role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        role = user.get('role')
        if role not in ('callcenter_supervisor', 'callcenter_operator'):
            raise HTTPException(status_code=403, detail="Only supervisors and operators can access CCS statistics")
        
        stats = await get_ccs_comprehensive_statistics()
        
        # Convert datetime objects to strings
        for operator in stats.get('operators', []):
            if operator.get('last_seen_at'):
                operator['last_seen_at'] = operator['last_seen_at'].isoformat()
            if operator.get('created_at'):
                operator['created_at'] = operator['created_at'].isoformat()
        
        for client in stats.get('clients', []):
            if client.get('last_seen_at'):
                client['last_seen_at'] = client['last_seen_at'].isoformat()
            if client.get('created_at'):
                client['created_at'] = client['created_at'].isoformat()
            if client.get('last_chat_at'):
                client['last_chat_at'] = client['last_chat_at'].isoformat()
        
        for trend in stats.get('daily_trends', []):
            if trend.get('date'):
                trend['date'] = trend['date'].isoformat()
        
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching CCS statistics: {str(e)}")


@router.get("/ccs/operator/{operator_id}")
async def get_operator_stats_endpoint(
    operator_id: int,
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Get detailed statistics for a specific operator.
    Only accessible by supervisors and operators.
    """
    try:
        # Get user to verify role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        role = user.get('role')
        if role not in ('callcenter_supervisor', 'callcenter_operator'):
            raise HTTPException(status_code=403, detail="Only supervisors and operators can access operator statistics")
        
        stats = await get_operator_statistics(operator_id)
        
        if not stats:
            raise HTTPException(status_code=404, detail="Operator not found")
        
        # Convert datetime objects to strings
        if stats.get('operator'):
            op = stats['operator']
            if op.get('last_seen_at'):
                op['last_seen_at'] = op['last_seen_at'].isoformat()
            if op.get('created_at'):
                op['created_at'] = op['created_at'].isoformat()
        
        for activity in stats.get('daily_activity', []):
            if activity.get('date'):
                activity['date'] = activity['date'].isoformat()
        
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching operator statistics: {str(e)}")


@router.get("/ccs/online-summary")
async def get_online_summary_endpoint(
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Get quick summary of online users.
    Used for real-time updates via WebSocket.
    """
    try:
        # Get user to verify role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        role = user.get('role')
        if role not in ('callcenter_supervisor', 'callcenter_operator'):
            raise HTTPException(status_code=403, detail="Only supervisors and operators can access online summary")
        
        summary = await get_online_users_summary()
        return summary
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching online summary: {str(e)}")


@router.get("/ccs/recent-clients")
async def get_recent_clients_endpoint(
    telegram_id: int = Query(..., description="Telegram user ID"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of clients")
):
    """
    Get list of recently active clients (clients who have chatted).
    Only accessible by supervisors and operators.
    """
    try:
        # Get user to verify role
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        role = user.get('role')
        if role not in ('callcenter_supervisor', 'callcenter_operator'):
            raise HTTPException(status_code=403, detail="Only supervisors and operators can access client list")
        
        clients = await get_recent_clients(limit)
        
        # Convert datetime objects to strings
        for client in clients:
            if client.get('last_seen_at'):
                client['last_seen_at'] = client['last_seen_at'].isoformat()
            if client.get('last_activity_at'):
                client['last_activity_at'] = client['last_activity_at'].isoformat()
        
        return {"clients": clients, "count": len(clients)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching recent clients: {str(e)}")


@router.post("/{chat_id}/messages/{message_id}/reactions")
async def toggle_reaction(
    chat_id: int,
    message_id: int,
    telegram_id: int = Query(..., description="Telegram user ID"),
    reaction: ReactionRequest = Body(...)
):
    """
    Toggle a reaction on a message.
    If user already has this emoji reaction, remove it.
    If user has a different emoji reaction, replace it.
    If user has no reaction, add it.
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        
        # Verify message exists and belongs to chat
        message = await get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        if message.get('chat_id') != chat_id:
            raise HTTPException(status_code=400, detail="Message does not belong to this chat")
        
        # Validate emoji (basic validation - should be 1-10 characters)
        emoji = reaction.emoji.strip()
        
        if emoji and len(emoji) > 10:
            raise HTTPException(status_code=400, detail="Invalid emoji")
        
        # Toggle reaction (handles empty emoji for removal)
        result = await toggle_message_reaction(message_id, user_id, emoji)
        
        # Broadcast reaction event via WebSocket
        from api.routes.websocket import send_message_reaction_event
        await send_message_reaction_event(chat_id, message_id, user_id, emoji, result["action"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error toggling reaction: {str(e)}")


@router.get("/{chat_id}/messages/{message_id}/reactions")
async def get_reactions(
    chat_id: int,
    message_id: int,
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Get all reactions for a message.
    """
    try:
        # Get user (for auth, but reactions are visible to all chat participants)
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify message exists and belongs to chat
        message = await get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        if message.get('chat_id') != chat_id:
            raise HTTPException(status_code=400, detail="Message does not belong to this chat")
        
        # Get reactions
        reactions = await get_message_reactions(message_id)
        
        return {"reactions": reactions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching reactions: {str(e)}")


@router.get("/{chat_id}/search")
async def search_chat_messages(
    chat_id: int,
    query: str = Query(..., description="Search query string", min_length=1),
    limit: int = Query(50, description="Maximum number of results", ge=1, le=100),
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Search messages in a chat using full-text search.
    """
    try:
        # Get user (for auth)
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify chat exists
        chat = await get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Search messages
        messages = await search_messages(chat_id, query, limit)
        
        return {
            "chat_id": chat_id,
            "query": query,
            "results": messages,
            "count": len(messages)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching messages: {str(e)}")


class ForwardRequest(BaseModel):
    target_chat_id: int


@router.post("/{chat_id}/messages/{message_id}/forward")
async def forward_chat_message(
    chat_id: int,
    message_id: int,
    telegram_id: int = Query(..., description="Telegram user ID"),
    request: ForwardRequest = Body(...)
):
    """
    Forward a message to another chat.
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        user_role = user.get('role', 'client')
        
        # Verify source message exists and belongs to chat
        source_message = await get_message_by_id(message_id)
        if not source_message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        if source_message.get('chat_id') != chat_id:
            raise HTTPException(status_code=400, detail="Message does not belong to this chat")
        
        # Verify target chat exists
        target_chat = await get_chat_by_id(request.target_chat_id)
        if not target_chat:
            raise HTTPException(status_code=404, detail="Target chat not found")
        
        # Forward message
        sender_type = 'operator' if user_role == 'operator' else 'client'
        operator_id = user_id if user_role == 'operator' else None
        
        new_message_id = await forward_message(
            message_id,
            request.target_chat_id,
            user_id,
            sender_type,
            operator_id
        )
        
        if not new_message_id:
            raise HTTPException(status_code=500, detail="Failed to forward message")
        
        # Get the new forwarded message
        new_message = await get_message_by_id(new_message_id)
        
        # Broadcast forward event via WebSocket (uses same event as regular messages)
        from api.routes.websocket import send_chat_message_event
        await send_chat_message_event(request.target_chat_id, new_message)
        
        return {
            "success": True,
            "message_id": new_message_id,
            "target_chat_id": request.target_chat_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error forwarding message: {str(e)}")


# Audio file validation
ALLOWED_AUDIO_FORMATS = ["audio/mpeg", "audio/mp3", "audio/ogg", "audio/wav", "audio/webm", "audio/opus", "audio/mp4", "audio/aac", "audio/x-m4a"]
MAX_AUDIO_SIZE = 20 * 1024 * 1024  # 20MB


@router.post("/{chat_id}/messages/voice")
async def upload_voice_message(
    chat_id: int,
    telegram_id: int = Query(..., description="Telegram user ID"),
    audio: UploadFile = File(..., description="Audio file")
):
    """
    Upload a voice message to a chat.
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        user_role = user.get('role', 'client')
        
        # Verify chat exists
        chat = await get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Validate audio file
        if audio.content_type not in ALLOWED_AUDIO_FORMATS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid audio format. Allowed: {', '.join(ALLOWED_AUDIO_FORMATS)}"
            )
        
        # Read audio file
        audio_data = await audio.read()
        audio_size = len(audio_data)
        
        if audio_size > MAX_AUDIO_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Audio file too large. Maximum size: {MAX_AUDIO_SIZE / (1024 * 1024)}MB"
            )
        
        if audio_size == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        
        # Determine file extension
        content_type_to_ext = {
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/ogg": "ogg",
            "audio/wav": "wav",
            "audio/webm": "webm",
            "audio/opus": "opus",
            "audio/mp4": "mp4",
            "audio/aac": "aac",
            "audio/x-m4a": "m4a"
        }
        file_ext = content_type_to_ext.get(audio.content_type, "mp3")
        
        # Create message first to get message_id
        # Determine sender_type based on role
        if user_role in ('callcenter_operator', 'callcenter_supervisor'):
            sender_type = 'operator'
            operator_id = user_id
        else:
            sender_type = 'client'
            operator_id = None
        
        message_id = await create_message(
            chat_id=chat_id,
            sender_id=user_id,
            sender_type=sender_type,
            message_text="",
            operator_id=operator_id,
            attachments=None
        )
        
        if not message_id:
            raise HTTPException(status_code=500, detail="Failed to create message")
        
        # Save audio file and update message in one transaction
        voice_dir = Path(settings.MEDIA_ROOT) / "voice" / str(chat_id)
        voice_dir.mkdir(parents=True, exist_ok=True)
        
        audio_filename = f"{message_id}.{file_ext}"
        audio_path = voice_dir / audio_filename
        
        audio_url = f"/api/media/voice/{chat_id}/{audio_filename}"
        attachments = {
            "type": "voice",
            "url": audio_url,
            "filename": audio_filename,
            "size": audio_size,
            "duration": None
        }
        
        # Save file and update database in one try-except block
        import asyncpg
        conn = None
        try:
            # Save audio file first
            with open(audio_path, "wb") as f:
                f.write(audio_data)
            
            # Update message with audio attachment
            conn = await asyncpg.connect(settings.DB_URL)
            try:
                await conn.execute(
                    "UPDATE messages SET attachments = $1 WHERE id = $2",
                    asyncpg.types.pgjsonb.encode(attachments),
                    message_id
                )
            finally:
                await conn.close()
                conn = None
        except Exception as e:
            # If file save or DB update fails, clean up
            if conn:
                try:
                    await conn.execute("DELETE FROM messages WHERE id = $1", message_id)
                    await conn.close()
                except:
                    pass
            # Try to delete file if it was created
            try:
                if audio_path.exists():
                    audio_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Failed to save audio file: {str(e)}")
        
        # Get updated message
        message = await get_message_by_id(message_id)
        
        # Broadcast via WebSocket
        from api.routes.websocket import send_chat_message_event
        await send_chat_message_event(chat_id, message)
        
        return {
            "success": True,
            "message_id": message_id,
            "audio_url": audio_url
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading voice message: {str(e)}")


@router.post("/{chat_id}/messages/image")
async def upload_image_message(
    chat_id: int,
    telegram_id: int = Query(..., description="Telegram user ID"),
    image: UploadFile = File(..., description="Image file"),
    message_text: Optional[str] = Query("", description="Optional message text")
):
    """
    Upload an image message to a chat.
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        user_role = user.get('role', 'client')
        
        # Verify chat exists
        chat = await get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Verify sender is participant
        client_id = chat.get('client_id')
        operator_id = chat.get('operator_id')
        allowed_users = [client_id]
        if operator_id:
            allowed_users.append(operator_id)
        
        if user_id not in allowed_users:
            raise HTTPException(status_code=403, detail="User is not a participant in this chat")
        
        # Validate image file
        if image.content_type not in ALLOWED_IMAGE_FORMATS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid image format. Allowed: {', '.join(ALLOWED_IMAGE_FORMATS)}"
            )
        
        # Read image file
        image_data = await image.read()
        image_size = len(image_data)
        
        if image_size > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Image file too large. Maximum size: {MAX_IMAGE_SIZE / (1024 * 1024)}MB"
            )
        
        if image_size == 0:
            raise HTTPException(status_code=400, detail="Image file is empty")
        
        # Determine file extension
        content_type_to_ext = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
            "image/webp": "webp"
        }
        file_ext = content_type_to_ext.get(image.content_type, "jpg")
        
        # Determine sender_type based on role
        if user_role in ('callcenter_operator', 'callcenter_supervisor'):
            sender_type = 'operator'
            operator_id_for_message = user_id
        else:
            sender_type = 'client'
            operator_id_for_message = None
        
        # Create message first to get message_id
        message_id = await create_message(
            chat_id=chat_id,
            sender_id=user_id,
            sender_type=sender_type,
            message_text=message_text.strip() if message_text else "",
            operator_id=operator_id_for_message,
            attachments=None
        )
        
        if not message_id:
            raise HTTPException(status_code=500, detail="Failed to create message")
        
        # Save image file and update message
        image_dir = Path(settings.MEDIA_ROOT) / "images" / str(chat_id)
        image_dir.mkdir(parents=True, exist_ok=True)
        
        image_filename = f"{message_id}.{file_ext}"
        image_path = image_dir / image_filename
        
        image_url = f"/api/media/images/{chat_id}/{image_filename}"
        attachments = {
            "type": "image",
            "url": image_url,
            "filename": image_filename,
            "size": image_size,
            "width": None,
            "height": None
        }
        
        # Save file and update database
        import asyncpg
        conn = None
        try:
            # Save image file first
            with open(image_path, "wb") as f:
                f.write(image_data)
            
            # Update message with image attachment
            conn = await asyncpg.connect(settings.DB_URL)
            try:
                await conn.execute(
                    "UPDATE messages SET attachments = $1 WHERE id = $2",
                    asyncpg.types.pgjsonb.encode(attachments),
                    message_id
                )
            finally:
                await conn.close()
                conn = None
        except Exception as e:
            # If file save or DB update fails, clean up
            if conn:
                try:
                    await conn.execute("DELETE FROM messages WHERE id = $1", message_id)
                    await conn.close()
                except:
                    pass
            # Try to delete file if it was created
            try:
                if image_path.exists():
                    image_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Failed to save image file: {str(e)}")
        
        # Get updated message
        message = await get_message_by_id(message_id)
        
        # Broadcast via WebSocket
        from api.routes.websocket import send_chat_message_event
        await send_chat_message_event(chat_id, message)
        
        return {
            "success": True,
            "message_id": message_id,
            "image_url": image_url
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading image message: {str(e)}")


@router.get("/{chat_id}/media")
async def get_chat_media_endpoint(
    chat_id: int,
    telegram_id: int = Query(..., description="Telegram user ID"),
    media_type: Optional[str] = Query(None, description="Media type filter: 'image', 'video', or None for all"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of media items")
):
    """
    Get media files (images/videos) from a chat.
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        user_role = user.get('role', 'client')
        
        # Verify chat exists
        chat = await get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Check access
        chat_client_id = chat.get('client_id')
        chat_operator_id = chat.get('operator_id')
        
        has_access = False
        if user_role == 'client' and chat_client_id == user_id:
            has_access = True
        elif user_role in ('callcenter_operator', 'callcenter_supervisor'):
            if user_role == 'callcenter_supervisor' or chat_operator_id == user_id:
                has_access = True
        
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Validate media_type
        if media_type and media_type not in ('image', 'video'):
            raise HTTPException(status_code=400, detail="Invalid media_type. Use 'image', 'video', or omit for all")
        
        # Get media messages
        media_messages = await get_chat_media(chat_id, media_type, limit)
        
        # Convert datetime objects to strings
        for msg in media_messages:
            if msg.get('created_at'):
                msg['created_at'] = msg['created_at'].isoformat()
        
        return {"media": media_messages, "count": len(media_messages)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching media: {str(e)}")


class EditMessageRequest(BaseModel):
    message_text: str


@router.put("/{chat_id}/messages/{message_id}")
async def edit_message_endpoint(
    chat_id: int,
    message_id: int,
    telegram_id: int = Query(..., description="Telegram user ID"),
    request: EditMessageRequest = Body(...)
):
    """
    Edit a message. Only the message owner can edit it within 15 minutes.
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        
        # Validate message text
        if not request.message_text or not request.message_text.strip():
            raise HTTPException(status_code=400, detail="Message text cannot be empty")
        
        # Verify chat exists
        chat = await get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Edit message
        updated_message = await edit_message(message_id, request.message_text.strip(), user_id)
        
        if not updated_message:
            raise HTTPException(
                status_code=403,
                detail="Cannot edit message. Either you are not the owner, the time limit (15 minutes) has passed, or the message does not exist."
            )
        
        # Broadcast via WebSocket
        from api.routes.websocket import send_chat_message_event
        await send_chat_message_event(chat_id, updated_message, event_type="message.edited")
        
        return {
            "success": True,
            "message": updated_message
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error editing message: {str(e)}")


@router.post("/{chat_id}/pin")
async def pin_chat_endpoint(
    chat_id: int,
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Pin a chat for a user.
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        
        # Verify chat exists
        chat = await get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Pin chat
        success = await pin_chat(user_id, chat_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to pin chat")
        
        return {"success": True, "message": "Chat pinned successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error pinning chat: {str(e)}")


@router.delete("/{chat_id}/pin")
async def unpin_chat_endpoint(
    chat_id: int,
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Unpin a chat for a user.
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        
        # Unpin chat
        success = await unpin_chat(user_id, chat_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Chat is not pinned")
        
        return {"success": True, "message": "Chat unpinned successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error unpinning chat: {str(e)}")


@router.get("/pinned")
async def get_pinned_chats_endpoint(
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Get all pinned chats for a user.
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        
        # Get pinned chats
        pinned_chats = await get_pinned_chats(user_id)
        
        return {"pinned_chats": pinned_chats, "count": len(pinned_chats)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching pinned chats: {str(e)}")


@router.post("/{chat_id}/messages/{message_id}/read")
async def mark_message_read_endpoint(
    chat_id: int,
    message_id: int,
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Mark a message as read.
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        
        # Verify message exists and belongs to chat
        message = await get_message_by_id(message_id)
        if not message or message.get('chat_id') != chat_id:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Don't mark own messages as read
        message_sender_id = message.get('sender_id')
        if message_sender_id == user_id:
            return {"success": True, "message": "Cannot mark own message as read"}
        
        # Mark as read
        success = await mark_message_read(message_id, user_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to mark message as read")
        
        # Broadcast via WebSocket
        from api.routes.websocket import send_message_read_event
        await send_message_read_event(chat_id, message_id, user_id)
        
        return {"success": True, "message": "Message marked as read"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marking message as read: {str(e)}")


@router.get("/{chat_id}/messages/{message_id}/reads")
async def get_message_reads_endpoint(
    chat_id: int,
    message_id: int,
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Get list of users who read a message.
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify message exists and belongs to chat
        message = await get_message_by_id(message_id)
        if not message or message.get('chat_id') != chat_id:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Get reads
        reads = await get_message_reads(message_id)
        
        return {"reads": reads, "count": len(reads)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching message reads: {str(e)}")


@router.post("/{chat_id}/read")
async def mark_chat_read_endpoint(
    chat_id: int,
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Mark all unread messages in a chat as read.
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user.get('id')
        
        # Verify chat exists
        chat = await get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Mark all messages as read
        count = await mark_chat_messages_read(chat_id, user_id)
        
        return {"success": True, "count": count, "message": f"Marked {count} messages as read"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marking chat as read: {str(e)}")


@router.get("/{chat_id}/messages/{message_id}/thread")
async def get_message_thread_endpoint(
    chat_id: int,
    message_id: int,
    telegram_id: int = Query(..., description="Telegram user ID")
):
    """
    Get all replies to a specific message (thread).
    """
    try:
        # Get user
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify message exists and belongs to chat
        message = await get_message_by_id(message_id)
        if not message or message.get('chat_id') != chat_id:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Get thread messages
        thread_messages = await get_message_thread(message_id)
        
        # Convert datetime objects to strings
        for msg in thread_messages:
            if msg.get('created_at'):
                msg['created_at'] = msg['created_at'].isoformat()
            if msg.get('edited_at'):
                msg['edited_at'] = msg['edited_at'].isoformat()
        
        return {"messages": thread_messages, "count": len(thread_messages)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching thread: {str(e)}")

