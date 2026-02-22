import asyncio

from fastapi import WebSocket
from websocket.models import Message


class ConnectionManager:
    def __init__(self):
        self._clients: dict[str, tuple[WebSocket, asyncio.Queue[Message]]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        queue = asyncio.Queue()
        self._clients[session_id] = (websocket, queue)
        return queue

    def disconnect(self, session_id: str):
        del self._clients[session_id]

    async def send_to(self, session_id: str, message: Message):
        if session_id not in self._clients:
            return
        (_, q) = self._clients[session_id]
        await q.put(message)
