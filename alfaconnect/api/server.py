"""
FastAPI server for webapp
Provides REST API and WebSocket endpoints for chat system
Enhanced with patterns from fastapi-chat
"""
import logging
import logging.config
from urllib.parse import urlparse
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

# CORS configuration
allowed_origins = [WEBAPP_ORIGIN]
if settings.ALLOWED_ORIGINS:
    # Add additional allowed origins from settings
    additional_origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
    allowed_origins.extend(additional_origins)

logger.info(f"[CORS] Allowing origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,  # Required for WebSocket connections
    allow_methods=["*"],
    allow_headers=["*"],  # Includes Upgrade and Connection headers needed for WebSocket
)

# Include routers with /api prefix only (Next.js rewrite strips it and adds again)
# This way: /api/user/bootstrap → http://localhost:8001/api/user/bootstrap
app.include_router(user.router, prefix="/api/user", tags=["user"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])
app.include_router(ws_chat.router, prefix="/api", tags=["websocket-new"])  # New WS endpoint: /api/ws/chat
app.include_router(metrics.router, prefix="/api", tags=["metrics"])
app.include_router(webapp_auth_router, tags=["webapp-auth"])  # WebApp validation: /api/webapp/validate


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
async def get_config(request: Request):
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

    response = {
        "apiBaseUrl": "/api",
        "wsBaseUrl": f"{WS_BASE_URL}/api",
        "timestamp": datetime.utcnow().isoformat(),
    }
    logger.info(f"[/config] Returning production domain-based config: {response}")
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

