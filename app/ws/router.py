# app/ws/router.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.ws.manager import manager

router = APIRouter()

@router.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # 클라이언트가 보내는 메시지 대기
    except WebSocketDisconnect:
        manager.disconnect(websocket)
