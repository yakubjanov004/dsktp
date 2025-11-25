"""
FastAPI dependencies for authentication and common utilities
"""
from fastapi import Header, HTTPException, status
from typing import Optional
import urllib.parse
import hmac
import hashlib
import json
import logging

from database.webapp.user_queries import get_user_by_telegram_id
from database.webapp.user_status_queries import is_user_online
from config import settings

logger = logging.getLogger(__name__)


async def get_current_user_from_init_data(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
) -> dict:
    """
    Get current user from Telegram WebApp initData header.
    Validates Telegram signature and extracts user info.
    
    This is the secure way to authenticate users in Telegram WebApp.
    No query params needed - all auth info comes from validated initData.
    
    Args:
        x_telegram_init_data: Telegram WebApp initData from X-Telegram-Init-Data header
        
    Returns:
        User dict from database
        
    Raises:
        HTTPException 401: If initData is missing or invalid
        HTTPException 404: If user not found in database
    """
    # If no initData header, try to get from query (fallback for development)
    if not x_telegram_init_data:
        # For development/testing - allow query param fallback
        # In production, this should be removed
        logger.warning("No X-Telegram-Init-Data header found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Telegram initData. Please provide X-Telegram-Init-Data header."
        )
    
    try:
        # 1. Parse and validate initData
        data = dict(urllib.parse.parse_qsl(x_telegram_init_data))
        check_hash = data.pop("hash", None)
        
        if not check_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid initData: missing hash"
            )
        
        # 2. Verify Telegram signature
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(data.items())
        )
        
        secret_key = hmac.new(
            b"WebAppData",
            settings.BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if calculated_hash != check_hash:
            logger.warning("Invalid Telegram signature detected")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram signature"
            )
        
        # 3. Extract user telegram_id from initData
        user_data_raw = data.get("user")
        if not user_data_raw:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No user data in initData"
            )
        
        try:
            user_data = json.loads(user_data_raw)
            telegram_id = user_data.get("id")
            if not telegram_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No telegram_id in user data"
                )
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user JSON in initData"
            )
        
        # 4. Get user from database
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in database"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in get_current_user_from_init_data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )

