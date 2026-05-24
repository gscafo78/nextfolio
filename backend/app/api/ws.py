"""
WebSocket /ws/prices — prezzi live via Redis pub/sub.

Il client si connette con il token JWT come query param:
  ws://localhost:8000/ws/prices?token=<access_token>&asset_ids=1,2,3

Ogni aggiornamento pubblicato su Redis viene filtrato per gli asset_ids
sottoscritti dal client e inoltrato come JSON.
"""

import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.security import decode_token

router = APIRouter()


@router.websocket("/ws/prices")
async def prices_ws(
    websocket: WebSocket,
    token: str = Query(...),
    asset_ids: str = Query(""),  # comma-separated list
):
    # Autenticazione via query param (gli header non sono supportati nei WS browser)
    payload = decode_token(token)
    if not payload.get("sub") or payload.get("type") != "access":
        await websocket.close(code=4001)
        return

    subscribed: set[int] = set()
    if asset_ids:
        try:
            subscribed = {int(x) for x in asset_ids.split(",") if x.strip()}
        except ValueError:
            await websocket.close(code=4002)
            return

    await websocket.accept()

    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("prices")

    async def _listen():
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            asset_id = data.get("asset_id")
            # Se il client ha sottoscritto asset specifici, filtra
            if subscribed and asset_id not in subscribed:
                continue

            try:
                await websocket.send_json(data)
            except Exception:
                return

    listen_task = asyncio.create_task(_listen())

    try:
        while True:
            # Legge eventuali messaggi dal client (es. aggiornamento subscription)
            msg = await websocket.receive_text()
            try:
                cmd = json.loads(msg)
                if cmd.get("action") == "subscribe" and "asset_ids" in cmd:
                    subscribed = {int(x) for x in cmd["asset_ids"]}
            except (json.JSONDecodeError, ValueError):
                pass
    except WebSocketDisconnect:
        pass
    finally:
        listen_task.cancel()
        await pubsub.unsubscribe("prices")
        await redis_client.aclose()
