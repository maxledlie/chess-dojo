import asyncio
from typing import cast

from fastapi import WebSocket

from app_state import AppState
from matchmaking.game_request_store import MemoryGameRequestStore
from shared.game_store import MemoryGameStore
from websocket.models import MessagePayload


class FakeWebSocket:
    async def accept(self):
        pass


def make_state() -> AppState:
    request_store = MemoryGameRequestStore()
    return AppState(
        redis=None,
        game_store=MemoryGameStore(),
        game_request_store=request_store,
    )


async def connect_session(state: AppState, session_id: str) -> asyncio.Queue:
    return await state.manager.connect(session_id, cast(WebSocket, FakeWebSocket()))


def drain(queue: asyncio.Queue) -> list[MessagePayload]:
    msgs = []
    while not queue.empty():
        msgs.append(queue.get_nowait().data)
    return msgs
