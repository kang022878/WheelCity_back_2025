# from typing import Dict, Set
# from fastapi import WebSocket
# from collections import defaultdict
# import json
# import asyncio

# class ConnectionManager:
#     """
#     - room(예: place_id) 단위로 WebSocket을 관리
#     - broadcast_room(): 같은 room에 연결된 모든 클라이언트에게 메시지 전송
#     """
#     def __init__(self) -> None:
#         self.rooms: Dict[str, Set[WebSocket]] = defaultdict(set)
#         self._lock = asyncio.Lock()

#     async def connect(self, ws: WebSocket, room: str):
#         await ws.accept()
#         async with self._lock:
#             self.rooms[room].add(ws)

#     async def disconnect(self, ws: WebSocket, room: str):
#         async with self._lock:
#             if room in self.rooms and ws in self.rooms[room]:
#                 self.rooms[room].remove(ws)
#             if room in self.rooms and not self.rooms[room]:
#                 self.rooms.pop(room, None)

#     async def broadcast_room(self, room: str, message: dict):
#         # JSON으로 일괄 전송
#         dead = []
#         payload = json.dumps(message, ensure_ascii=False)
#         for ws in list(self.rooms.get(room, [])):
#             try:
#                 await ws.send_text(payload)
#             except Exception:
#                 dead.append(ws)
#         # 끊어진 소켓 정리
#         for ws in dead:
#             await self.disconnect(ws, room)

# manager = ConnectionManager()

# app/ws/manager.py
from typing import List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"🔌 Connected: {len(self.active_connections)} clients")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"❌ Disconnected: {len(self.active_connections)} clients")

    async def broadcast(self, message: str):
        for conn in self.active_connections:
            await conn.send_text(message)

manager = ConnectionManager()
