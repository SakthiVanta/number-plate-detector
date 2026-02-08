from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.config import settings
import redis.asyncio as redis
import asyncio
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    
    if not settings.USE_CELERY:
        # Lite Mode: Send a startup message and sleep
        await websocket.send_text('{"event_type": "SYSTEM", "message": "Real-time logs disabled (In-Process Mode)", "level": "INFO"}')
        try:
            while True:
                await asyncio.sleep(10) # Keep connection open but idle
        except WebSocketDisconnect:
            pass
        return

    r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("system_logs")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
    finally:
        await pubsub.unsubscribe("system_logs")
        await r.close()
