from pydantic import BaseModel
from datetime import datetime
import redis.asyncio as redis

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
    def __init__(self, redis: redis.Redis):
        self.manager: ConnectionManager = ConnectionManager()
        self.redis = redis
