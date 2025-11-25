"""
Telegram WebApp Authentication
Validates Telegram WebApp initData signature
"""
from fastapi import APIRouter, HTTPException, Query
import urllib.parse
import hmac
import hashlib
import json
from config import settings

router = APIRouter(prefix="/api/webapp", tags=["WebApp Auth"])


@router.get("/validate")
async def validate_telegram_webapp(init_data: str = Query(..., description="Telegram WebApp initData")):
    """
    Validate Telegram WebApp initData signature
    
    🔐 This validates that the user data comes from Telegram's official servers
    using HMAC-SHA256 signature verification
    
    Args:
        init_data: URL-encoded string from window.Telegram.WebApp.initData
        
    Returns:
        {
            "ok": true,
            "user": {
                "id": 123456789,
                "first_name": "John",
                "last_name": "Doe",
                "username": "johndoe",
                ...
            }
        }
        
    Raises:
        400: Missing or invalid data
        403: Invalid Telegram signature (security violation)
    """
    try:
        # 1. Parse initData from Telegram WebApp
        data = dict(urllib.parse.parse_qsl(init_data))
        check_hash = data.pop("hash", None)
        
        if not check_hash:
            raise HTTPException(
                status_code=400,
                detail="Missing hash in initData"
            )
        
        # 2. Build data_check_string (sorted alphabetically by key)
        # This matches Telegram's signature verification algorithm
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(data.items())
        )
        
        # 3. Calculate HMAC-SHA256
        # Step 1: Create secret key from BOT_TOKEN
        secret_key = hmac.new(
            b"WebAppData",
            settings.BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()
        
        # Step 2: Create HMAC signature
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # 4. Compare signatures
        if calculated_hash != check_hash:
            print(f"[SECURITY] Invalid Telegram signature!")
            print(f"  Expected: {check_hash}")
            print(f"  Calculated: {calculated_hash}")
            raise HTTPException(
                status_code=403,
                detail="Invalid Telegram signature - possible tampering detected"
            )
        
        print(f"✅ [Telegram WebApp] initData signature verified successfully")
        
        # 5. Parse user JSON from initData
        user_data = {}
        user_data_raw = data.get("user")
        
        if user_data_raw:
            try:
                user_data = json.loads(user_data_raw)
                print(f"   User: {user_data.get('first_name')} {user_data.get('last_name')} (ID: {user_data.get('id')})")
            except json.JSONDecodeError as e:
                print(f"⚠️ [Telegram WebApp] Failed to parse user JSON: {e}")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid user JSON in initData"
                )
        
        return {
            "ok": True,
            "user": user_data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [Telegram WebApp] Validation error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"initData validation error: {str(e)}"
        )
