from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import asyncpg
import asyncio
import json
from app.api import deps
from app.models import User
from urllib.parse import quote_plus
from app.core.config import get_settings
from app.schemas.logger import logger

router = APIRouter()

encoded_password = quote_plus(get_settings().database.password.get_secret_value())
DATABASE_URL = (
    f"postgresql://{get_settings().database.username}:{encoded_password}@"
    f"{get_settings().database.hostname}:{get_settings().database.port}/{get_settings().database.db}"
)

@router.websocket("/ws/session-status")
async def websocket_session_status(
    websocket: WebSocket,
    session_id: Optional[str] = Query(None, description="Session ID")
):
    await websocket.accept()
    conn = None

    session_notification_queue = asyncio.Queue()

    async def handle_session_notification(connection, pid, channel, payload):
        data = json.loads(payload)
        await session_notification_queue.put(data)

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        logger.info("CONNECTION ESTABLISHED")
        logger.debug(f"SESSION ID ---> {session_id}")

        await conn.add_listener('session_id_status_channel', handle_session_notification)
        while True:
            payload = await session_notification_queue.get()
            if session_id:
                if payload.get('session_id') == session_id:
                    await websocket.send_text(json.dumps(payload))
            else:
                await websocket.send_text(json.dumps(payload))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        if conn:
            logger.info("CONNECTION CLOSING")
            await conn.remove_listener('session_id_status_channel', handle_session_notification)
            await conn.close()

@router.websocket("/ws/ensid-status")
async def websocket_ensid_status(
    websocket: WebSocket,
    session_id: str = Query(..., description="Session ID")
):
    await websocket.accept()
    conn = None

    ensid_notification_queue = asyncio.Queue()

    async def handle_ensid_notification(connection, pid, channel, payload):
        data = json.loads(payload)
        await ensid_notification_queue.put(data)

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        logger.info("CONNECTION ESTABLISHED")

        await conn.add_listener('ens_id_status_channel', handle_ensid_notification)
        while True:
            payload = await ensid_notification_queue.get()
            if payload.get('session_id') == session_id:
                await websocket.send_text(json.dumps(payload))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        if conn:
            logger.info("CONNECTION CLOSING")
            await conn.remove_listener('ens_id_status_channel', handle_ensid_notification)
            await conn.close()
