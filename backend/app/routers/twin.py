import httpx
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from app.config import settings
from app.services import twin_client

router = APIRouter(tags=["twin"])


@router.get("/twin/{entity_type}")
async def get_twin_state_list(entity_type: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{settings.twin_engine_http_url}/state/{entity_type}")
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


@router.get("/twin/{entity_type}/{entity_id}")
async def get_twin_state(entity_type: str, entity_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{settings.twin_engine_http_url}/state/{entity_type}/{entity_id}")
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


@router.websocket("/ws/live")
async def live_feed(websocket: WebSocket) -> None:
    await websocket.accept()
    twin_client.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        twin_client.unregister(websocket)
