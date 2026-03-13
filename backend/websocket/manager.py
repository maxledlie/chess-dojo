import asyncio

import structlog
from fastapi import WebSocket
from matchmaking.game_request_store import GameRequestStore
from websocket.models import Message, MessagePayload

logger = structlog.get_logger()


class ConnectionManager:
    def __init__(self, game_request_store: GameRequestStore):
        self._clients: dict[str, tuple[WebSocket, asyncio.Queue[Message]]] = {}
        self._game_request_store = game_request_store

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        logger.info("Websocket connection established", session_id=session_id)
        queue = asyncio.Queue()
        self._clients[session_id] = (websocket, queue)
        return queue

    async def disconnect(self, session_id: str):
        logger.info("Websocket connection lost", session_id=session_id)
        del self._clients[session_id]
        await self._game_request_store.cancel_request(session_id)

    async def send_to(self, session_id: str, message: MessagePayload):
        if session_id not in self._clients:
            return
        (_, q) = self._clients[session_id]
        await q.put(Message(data=message))

    @property
    def player_count(self):
        return len(self._clients.keys())
