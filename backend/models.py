import threading
from pydantic import BaseModel
from datetime import datetime

from websocket.manager import ConnectionManager

# ------------------------
# HTTP
# ------------------------


class SessionResponse(BaseModel):
    session_id: str


class ChatMessage(BaseModel):
    player_id: str
    timestamp: datetime
    content: str


class Game(BaseModel):
    white_id: str
    black_id: str
    moves: list[str]
    chat: list[ChatMessage]


class AppState:
    def __init__(self):
        self.game_requests: list[str] = []
        self.games: dict[str, Game] = {}
        self.manager: ConnectionManager = ConnectionManager()
        self._game_request_lock: threading.Lock = threading.Lock()

    @property
    def game_request_lock(self):
        """Return an async context manager for the lock"""
        return _ThreadingLockAsyncWrapper(self._game_request_lock)


class _ThreadingLockAsyncWrapper:
    """Wraps a threading.Lock to be used with async with"""

    def __init__(self, lock: threading.Lock):
        self.lock = lock

    async def __aenter__(self):
        self.lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.lock.release()
        return False