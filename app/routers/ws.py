from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from typing import Optional
from app.ws.manager import manager
from jose import jwt, JWTError
import os
import json

router = APIRouter()

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

async def verify_token(token: Optional[str] = Query(default=None)) -> Optional[str]:
    """
    쿼리스트링 token=? 로 온 JWT를 검증하고 이메일(또는 user_id)을 반환.
    토큰이 없으면 익명 허용(원하면 필수로 바꿔도됨)
    """
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None

@router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    place_id: str = Query(..., description="구독할 room(예: place_id)"),
    user_sub: Optional[str] = Depends(verify_token),
):
    """
    - 클라이언트는 ws://.../ws?place_id=...&token=... 로 접속
    - 접속 후 서버는 room에 join, 클라가 보내는 메시지는 같은 room에 브로드캐스트(샘플)
    """
    await manager.connect(websocket, place_id)
    try:
        # 접속 알림
        await manager.broadcast_room(place_id, {
            "type": "system:join",
            "data": {"place_id": place_id, "user": user_sub},
        })

        while True:
            msg = await websocket.receive_text()
            # 들어온 payload를 검사하고 그대로 브로드캐스트(프런트 채팅/상태 공유 등)
            # 프런트에서 {type, data} 형태로 보내는 것을 권장
            try:
                parsed = json.loads(msg)
                if not isinstance(parsed, dict):
                    raise ValueError("invalid message")
            except Exception:
                parsed = {"type": "client:raw", "data": msg}

            await manager.broadcast_room(place_id, {
                "type": parsed.get("type", "client:message"),
                "data": parsed.get("data", parsed),
                "from": user_sub
            })

    except WebSocketDisconnect:
        await manager.disconnect(websocket, place_id)
        await manager.broadcast_room(place_id, {
            "type": "system:leave",
            "data": {"place_id": place_id, "user": user_sub},
        })
    except Exception as e:
        await manager.disconnect(websocket, place_id)
        await manager.broadcast_room(place_id, {
            "type": "system:error",
            "data": {"error": str(e)}
        })
