import logging

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket
from fastapi.websockets import WebSocketState
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.core.ws_tickets import redeem_ticket

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notifications"])


@router.websocket("/ws/live")
async def live_updates(websocket: WebSocket, ticket: str) -> None:
    settings = get_settings()
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    try:
        user_id = await redeem_ticket(redis_client, ticket)
    except Exception:
        logger.exception("WS ticket redemption failed; closing connection.")
        await websocket.close(code=1011)
        await redis_client.aclose()
        return

    if user_id is None:
        await websocket.close(code=1008)  # policy violation: invalid/expired/reused ticket
        await redis_client.aclose()
        return

    await websocket.accept()
    channel = f"notifications:{user_id}"
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            if websocket.client_state != WebSocketState.CONNECTED:
                break
            await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await redis_client.aclose()
