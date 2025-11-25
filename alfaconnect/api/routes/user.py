"""
User-related API endpoints
"""
from fastapi import APIRouter, HTTPException, Query, Body, status, Depends
from fastapi.responses import JSONResponse
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from database.webapp.user_queries import (
    get_user_by_telegram_id,
    get_user_by_id,
    get_client_info,
    get_available_clients,
    search_clients,
    get_operators,
    create_or_get_user
)
from database.webapp.user_status_queries import (
    update_user_last_seen,
    is_user_online
)
from api.dependencies import get_current_user_from_init_data
from typing import Optional

router = APIRouter()


class BootstrapUserRequest(BaseModel):
    telegram_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None


@router.post("/bootstrap", status_code=status.HTTP_201_CREATED)
async def bootstrap_user(
    request: BootstrapUserRequest = Body(...),
    current_user: Optional[dict] = Depends(get_current_user_from_init_data)
):
    """
    Bootstrap user: get existing user or create new one
    Returns 200 if user exists, 201 if created
    
    🔐 Authentication: Uses Telegram WebApp initData from X-Telegram-Init-Data header (optional).
    If initData is provided, validates it. Otherwise uses request.telegram_id (fallback for compatibility).
    
    ⚡ Lightweight: Simple DB lookup/insert, no external calls.
    """
    try:
        # If we have authenticated user from initData, use it
        if current_user:
            # User already authenticated via initData
            telegram_id = current_user.get('telegram_id')
            
            # Convert datetime objects to strings
            created_at = current_user.get('created_at')
            if created_at and hasattr(created_at, 'isoformat'):
                created_at = created_at.isoformat()
            
            updated_at = current_user.get('updated_at')
            if updated_at and hasattr(updated_at, 'isoformat'):
                updated_at = updated_at.isoformat()
            
            # Calculate is_online from last_seen_at
            last_seen_at = current_user.get('last_seen_at')
            calculated_is_online = is_user_online(last_seen_at)
            if last_seen_at and hasattr(last_seen_at, 'isoformat'):
                last_seen_at = last_seen_at.isoformat()
            
            return JSONResponse(
                content={
                    **current_user,
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'is_online': calculated_is_online,
                    'last_seen_at': last_seen_at
                },
                status_code=status.HTTP_200_OK
            )
        
        # Fallback: use request.telegram_id (for backward compatibility)
        # Check if user already exists
        existing_user = await get_user_by_telegram_id(request.telegram_id)
        if existing_user:
            # Convert datetime objects to strings
            created_at = existing_user.get('created_at')
            if created_at and hasattr(created_at, 'isoformat'):
                created_at = created_at.isoformat()
            
            updated_at = existing_user.get('updated_at')
            if updated_at and hasattr(updated_at, 'isoformat'):
                updated_at = updated_at.isoformat()
            
            # Calculate is_online from last_seen_at
            last_seen_at = existing_user.get('last_seen_at')
            calculated_is_online = is_user_online(last_seen_at)
            if last_seen_at and hasattr(last_seen_at, 'isoformat'):
                last_seen_at = last_seen_at.isoformat()
            
            # Return existing user with 200 status
            return JSONResponse(
                content={
                    **existing_user,
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'is_online': calculated_is_online,
                    'last_seen_at': last_seen_at
                },
                status_code=status.HTTP_200_OK
            )
        
        # Create new user
        new_user = await create_or_get_user(
            telegram_id=request.telegram_id,
            first_name=request.first_name,
            last_name=request.last_name,
            username=request.username
        )
        
        # Convert datetime objects to strings
        created_at = new_user.get('created_at')
        if created_at and hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()
        
        updated_at = new_user.get('updated_at')
        if updated_at and hasattr(updated_at, 'isoformat'):
            updated_at = updated_at.isoformat()
        
        # Calculate is_online from last_seen_at
        last_seen_at = new_user.get('last_seen_at')
        calculated_is_online = is_user_online(last_seen_at) if last_seen_at else False
        if last_seen_at and hasattr(last_seen_at, 'isoformat'):
            last_seen_at = last_seen_at.isoformat()
        
        # Return 201 Created status
        return {
            **new_user,
            'created_at': created_at,
            'updated_at': updated_at,
            'is_online': calculated_is_online,
            'last_seen_at': last_seen_at
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.exception(f"Error bootstrapping user: {e}")
        raise HTTPException(status_code=500, detail=f"Error bootstrapping user: {str(e)}")


@router.get("/info")
async def get_user_info(telegram_id: int = Query(..., description="Telegram user ID")):
    """
    Get user info by telegram_id
    """
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Convert datetime objects to strings
        if user.get('created_at'):
            user['created_at'] = user['created_at'].isoformat()
        if user.get('updated_at'):
            user['updated_at'] = user['updated_at'].isoformat()
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user: {str(e)}")


@router.get("/role")
async def get_user_role(telegram_id: int = Query(..., description="Telegram user ID")):
    """
    Get user role by telegram_id
    """
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "telegram_id": telegram_id,
            "role": user.get('role'),
            "user_id": user.get('id')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user role: {str(e)}")


@router.get("/client-info")
async def get_client_information(user_id: int = Query(..., description="Client user ID")):
    """
    Get detailed client information (for operators)
    """
    try:
        client_info = await get_client_info(user_id)
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


@router.get("/clients")
async def list_clients(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of clients"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Get list of available clients (for operators)
    """
    try:
        clients = await get_available_clients(limit=limit, offset=offset)
        
        # Convert datetime objects to strings
        for client in clients:
            if client.get('created_at'):
                client['created_at'] = client['created_at'].isoformat()
        
        return {"clients": clients, "count": len(clients)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clients: {str(e)}")


@router.get("/clients/search")
async def search_clients_endpoint(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results")
):
    """
    Search clients by name, phone, or abonent_id
    """
    try:
        if len(q) < 2:
            return {"clients": [], "count": 0}
        
        clients = await search_clients(q, limit=limit)
        
        # Convert datetime objects to strings
        for client in clients:
            if client.get('created_at'):
                client['created_at'] = client['created_at'].isoformat()
        
        return {"clients": clients, "count": len(clients)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching clients: {str(e)}")


@router.get("/operators")
async def list_operators(
    limit: int = Query(100, ge=1, le=200, description="Maximum number of operators")
):
    """
    Get list of call center operators (for supervisors and clients).
    Includes is_online and last_seen_at for presence tracking.
    """
    try:
        from database.webapp.user_status_queries import is_user_online
        
        operators = await get_operators(limit=limit)
        
        # Convert datetime objects to strings and calculate is_online from last_seen_at
        for operator in operators:
            if operator.get('created_at'):
                operator['created_at'] = operator['created_at'].isoformat()
            if operator.get('updated_at'):
                operator['updated_at'] = operator['updated_at'].isoformat()
            
            # Calculate is_online from last_seen_at using TTL
            last_seen_at = operator.get('last_seen_at')
            if last_seen_at and hasattr(last_seen_at, 'isoformat'):
                operator['last_seen_at'] = last_seen_at.isoformat()
                operator['is_online'] = is_user_online(last_seen_at)
            else:
                operator['is_online'] = False
                if last_seen_at:
                    operator['last_seen_at'] = last_seen_at.isoformat() if hasattr(last_seen_at, 'isoformat') else last_seen_at
        
        return {"operators": operators, "count": len(operators)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching operators: {str(e)}")


class UpdateStatusRequest(BaseModel):
    is_online: bool


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_authenticated_user(
    current_user: dict = Depends(get_current_user_from_init_data)
):
    """
    Get current authenticated user info including role and operator_id.
    This endpoint determines user role for frontend routing.
    
    🔐 Authentication: Uses Telegram WebApp initData from X-Telegram-Init-Data header.
    No query params needed - all auth info comes from validated initData.
    
    ⚡ Lightweight: No external HTTP calls, no heavy queries, just DB lookup.
    
    Returns user info with role for frontend role-based routing.
    """
    try:
        # current_user is already validated and fetched from database
        # Just format the response
        
        # Convert datetime objects to strings
        created_at = current_user.get('created_at')
        if created_at and hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()
        
        updated_at = current_user.get('updated_at')
        if updated_at and hasattr(updated_at, 'isoformat'):
            updated_at = updated_at.isoformat()
        
        # Add operator_id field for compatibility
        # For operators and supervisors, operator_id is the same as user id
        # For clients, operator_id is null
        operator_id = None
        if current_user.get('role') in ('callcenter_operator', 'callcenter_supervisor'):
            operator_id = current_user.get('id')
        
        # Calculate is_online from last_seen_at using TTL
        last_seen_at = current_user.get('last_seen_at')
        calculated_is_online = is_user_online(last_seen_at)
        
        # Convert datetime objects to strings
        if last_seen_at and hasattr(last_seen_at, 'isoformat'):
            last_seen_at = last_seen_at.isoformat()
        
        return {
            "id": current_user.get('id'),
            "telegram_id": current_user.get('telegram_id'),
            "full_name": current_user.get('full_name'),
            "username": current_user.get('username'),
            "phone": current_user.get('phone'),
            "role": current_user.get('role'),
            "operator_id": operator_id,
            "language": current_user.get('language'),
            "region": current_user.get('region'),
            "address": current_user.get('address'),
            "abonent_id": current_user.get('abonent_id'),
            "is_blocked": current_user.get('is_blocked'),
            "is_online": calculated_is_online,  # Calculated from last_seen_at
            "last_seen_at": last_seen_at,
            "created_at": created_at,
            "updated_at": updated_at
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.exception(f"Error in get_authenticated_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching authenticated user: {str(e)}"
        )


@router.post("/me/status", status_code=status.HTTP_200_OK)
async def update_user_status(
    request: UpdateStatusRequest,
    current_user: dict = Depends(get_current_user_from_init_data)
):
    """
    Update user last_seen_at timestamp (heartbeat).
    is_online is calculated from last_seen_at using TTL (60 seconds), not stored.
    
    ⚡ Lightweight: Simple DB update, no external calls.
    
    🔐 Authentication: Uses Telegram WebApp initData from X-Telegram-Init-Data header.
    """
    try:
        # current_user is already validated and fetched
        user_id = current_user.get('id')
        user_role = current_user.get('role')
        now = datetime.now(timezone.utc)
        
        # Always update last_seen_at (heartbeat)
        # If is_online=false, we still update timestamp (explicit offline signal)
        success = await update_user_last_seen(
            user_id=user_id,
            last_seen_at=now
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update user last_seen_at in database")
        
        # Calculate actual is_online from updated last_seen_at
        calculated_is_online = is_user_online(now) if request.is_online else False
        
        # Update in-memory presence tracking (used by WebSocket system)
        try:
            from api.routes.websocket import online_users, online_status_timestamp, broadcast_user_status
            online_users[user_id] = calculated_is_online
            online_status_timestamp[user_id] = now
            
            # Broadcast status change to other users via WebSocket
            await broadcast_user_status(user_id, calculated_is_online, user_role)
        except Exception as ws_error:
            # WebSocket broadcast is optional, log but don't fail
            import logging
            logging.warning(f"WebSocket broadcast failed: {ws_error}")
        
        return {
            "status": "success",
            "is_online": calculated_is_online,  # Calculated from last_seen_at
            "user_id": user_id,
            "last_seen_at": now.isoformat(),
            "timestamp": now.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating user status: {str(e)}")