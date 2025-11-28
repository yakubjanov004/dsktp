"""
FastAPI server for webapp
Provides REST API and WebSocket endpoints for chat system
Enhanced with patterns from fastapi-chat
"""
import logging
import logging.config
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message
from pathlib import Path

from api.routes import user, chat, websocket, metrics
from api.ws import chat as ws_chat
from api.webapp_auth import router as webapp_auth_router
from api.exceptions import APIException
from config import settings

logger = logging.getLogger(__name__)

# Configure logging
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "default": {
            "level": settings.LOG_LEVEL,
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "": {
            "handlers": ["default"],
            "level": settings.LOG_LEVEL,
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["default"],
            "level": logging.ERROR,
            "propagate": False,
        },
    },
}

if not settings.ENVIRONMENT == "test":
    logging.config.dictConfig(LOGGING_CONFIG)

# Create FastAPI app
app = FastAPI(
    title="AlfaConnect WebApp API",
    description="API for Telegram bot webapp",
    version="1.0.0"
)

# Production hostname requirements
WEBAPP_URL = settings.WEBAPP_URL
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL environment variable must be set for AlfaConnect API")

parsed = urlparse(WEBAPP_URL)
if not parsed.scheme or not parsed.netloc:
    raise RuntimeError("WEBAPP_URL must include scheme and host (e.g. https://webapp.darrov.uz)")

WEBAPP_ORIGIN = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
WS_BASE_URL = WEBAPP_ORIGIN.replace("https://", "wss://").replace("http://", "ws://")


def normalize_origin(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    parsed_value = urlparse(value)
    if parsed_value.scheme and parsed_value.netloc:
        return f"{parsed_value.scheme}://{parsed_value.netloc}".rstrip("/")
    return None


def resolve_client_origin(request: Request, explicit_origin: Optional[str]) -> Optional[str]:
    candidates = [
        explicit_origin,
        request.headers.get("origin"),
        request.headers.get("referer"),
    ]
    for candidate in candidates:
        normalized = normalize_origin(candidate)
        if normalized:
            return normalized

    forwarded_host = request.headers.get("x-forwarded-host")
    forwarded_proto = request.headers.get("x-forwarded-proto") or request.headers.get("x-scheme")
    if forwarded_host:
        candidate = f"{forwarded_proto or request.url.scheme}://{forwarded_host}"
        normalized = normalize_origin(candidate)
        if normalized:
            return normalized

    host_header = request.headers.get("host")
    if host_header:
        candidate = f"{request.url.scheme}://{host_header}"
        normalized = normalize_origin(candidate)
        if normalized:
            return normalized

    return None

# CORS configuration
allowed_origins = [WEBAPP_ORIGIN]
if settings.ALLOWED_ORIGINS:
    # Add additional allowed origins from settings
    additional_origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
    allowed_origins.extend(additional_origins)

dev_origin_regex: Optional[str] = None
if settings.ENVIRONMENT != "production":
    dev_origins = [
        "http://localhost",
        "http://localhost:3200",
        "http://127.0.0.1",
        "http://127.0.0.1:3200",
    ]
    allowed_origins.extend(dev_origins)
    dev_origin_regex = (
        r"https://.*\.ngrok(-free)?\.(app|dev|io)"
        r"|http://(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})(:\d{1,5})?"
    )

# Remove duplicates while preserving order
seen = set()
deduped_origins = []
for origin in allowed_origins:
    if origin and origin not in seen:
        seen.add(origin)
        deduped_origins.append(origin)

logger.info(f"[CORS] Allowing origins: {deduped_origins}")
if dev_origin_regex:
    logger.info(f"[CORS] Allow origin regex: {dev_origin_regex}")

cors_kwargs = {
    "allow_origins": deduped_origins,
    "allow_credentials": True,  # Required for WebSocket connections
    "allow_methods": ["*"],
    "allow_headers": ["*"],  # Includes Upgrade and Connection headers needed for WebSocket
}

if dev_origin_regex:
    cors_kwargs["allow_origin_regex"] = dev_origin_regex

app.add_middleware(
    CORSMiddleware,
    **cors_kwargs,
)

# Middleware to add ngrok-skip-browser-warning header to all responses
class NgrokSkipWarningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Add ngrok-skip-browser-warning header to all responses
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

app.add_middleware(NgrokSkipWarningMiddleware)

# Include routers with /api prefix only (Next.js rewrite strips it and adds again)
# This way: /api/user/bootstrap → http://localhost:8001/api/user/bootstrap
app.include_router(user.router, prefix="/api/user", tags=["user"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])
app.include_router(ws_chat.router, prefix="/api", tags=["websocket-new"])  # New WS endpoint: /api/ws/chat
app.include_router(metrics.router, prefix="/api", tags=["metrics"])
app.include_router(webapp_auth_router, tags=["webapp-auth"])  # WebApp validation: /api/webapp/validate


# Media files endpoint
@app.get("/api/media/voice/{chat_id}/{filename}")
async def get_voice_file(
    chat_id: int,
    filename: str,
    telegram_id: int = Query(..., description="Telegram user ID for authorization")
):
    """Serve voice message files with access control"""
    from database.webapp.user_queries import get_user_by_telegram_id
    from database.webapp.chat_queries import get_chat_by_id
    import asyncpg
    
    # Get user
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user.get('id')
    user_role = user.get('role', 'client')
    
    # Verify chat exists and user has access
    chat = await get_chat_by_id(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Check access: client can only access their own chats, operators can access assigned chats
    chat_client_id = chat.get('client_id')
    chat_operator_id = chat.get('operator_id')
    
    has_access = False
    if user_role == 'client' and chat_client_id == user_id:
        has_access = True
    elif user_role in ('callcenter_operator', 'callcenter_supervisor'):
        # Operators can access if assigned or supervisor
        if user_role == 'callcenter_supervisor' or chat_operator_id == user_id:
            has_access = True
    
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Extract message_id from filename (format: {message_id}.{ext})
    try:
        message_id = int(filename.split('.')[0])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename format")
    
    # Verify message belongs to this chat
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        message = await conn.fetchrow(
            "SELECT id, chat_id FROM messages WHERE id = $1",
            message_id
        )
        if not message or message['chat_id'] != chat_id:
            raise HTTPException(status_code=404, detail="File not found")
    finally:
        await conn.close()
    
    media_path = Path(settings.MEDIA_ROOT) / "voice" / str(chat_id) / filename
    if not media_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(media_path, media_type="audio/mpeg")


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    logger.info("Application is starting up")
    
    # Initialize Redis if enabled
    if settings.REDIS_ENABLED:
        try:
            import redis.asyncio as aioredis
            from api.ws.pubsub_manager import RedisPubSubManager
            
            # Create Redis connection pool
            redis_pool = aioredis.ConnectionPool(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=False
            )
            
            # Test connection
            redis_client = aioredis.Redis(connection_pool=redis_pool)
            await redis_client.ping()
            await redis_client.close()
            
            logger.info("Redis connection pool initialized successfully")
            
            # Update WebSocket manager to use Redis PubSub
            from api.ws.manager import manager
            pubsub_manager = RedisPubSubManager(redis_pool=redis_pool)
            manager.use_redis_pubsub = True
            manager.pubsub_manager = pubsub_manager
            
            logger.info("WebSocket manager configured with Redis PubSub")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            logger.warning("Continuing without Redis PubSub support")
    else:
        logger.info("Redis PubSub is disabled")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Application is shutting down")
    
    # Disconnect Redis PubSub if enabled
    if settings.REDIS_ENABLED:
        try:
            from api.ws.manager import manager
            if manager.pubsub_manager:
                await manager.pubsub_manager.disconnect()
                logger.info("Redis PubSub disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting Redis: {e}")


@app.get("/api/health")
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "webapp-api",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/config")
@app.get("/config")
async def get_config(request: Request, origin: Optional[str] = Query(default=None)):
    """
    Get runtime configuration for WebApp client
    
    Windows local development mode:
    - Frontend loads from http://localhost:3200 or http://YOUR_LOCAL_IP:3200
    - Backend runs on http://localhost:8001 or http://YOUR_LOCAL_IP:8001
    - WebSocket uses ws://localhost:8001 or ws://YOUR_LOCAL_IP:8001
    
    Production mode (domain-based):
    - Frontend loads from configured WEBAPP_URL
    - Backend runs on configured API_HOST:API_PORT
    - WebSocket uses configured WS_URL
    """
    logger.debug(f"[/config] WEBAPP_URL from .env: {WEBAPP_URL}")
    logger.debug(f"[/config] Request origin: {request.headers.get('origin')}")
    logger.debug(f"[/config] Request host: {request.headers.get('host')}")
    
    if not WEBAPP_URL:
        raise HTTPException(status_code=500, detail="WEBAPP_URL is not configured")

    client_origin = resolve_client_origin(request, origin)
    resolved_origin = client_origin or WEBAPP_ORIGIN
    api_base_url = f"{resolved_origin}/api" if resolved_origin else "/api"
    ws_origin = resolved_origin.replace("https://", "wss://").replace("http://", "ws://") if resolved_origin else WS_BASE_URL
    ws_base_url = f"{ws_origin}/api"

    logger.info(f"[/config] Resolved origin: {resolved_origin}")
    logger.info(f"[/config] API base: {api_base_url}")
    logger.info(f"[/config] WS base: {ws_base_url}")

    response = {
        "apiBaseUrl": api_base_url,
        "wsBaseUrl": ws_base_url,
        "timestamp": datetime.utcnow().isoformat(),
    }
    logger.info(f"[/config] Returning runtime config: {response}")
    return response


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    """Handle custom API exceptions."""
    logger.warning(f"API exception: {exc.detail} (status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning(f"HTTP exception: {exc.detail} (status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled exceptions."""
    logger.exception(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

