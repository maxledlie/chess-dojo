import redis.asyncio as redis

from shared.game_store import GameStore
from websocket.manager import ConnectionManager


class AppState:
    def __init__(self, redis: redis.Redis, game_store: GameStore):
        self.redis = redis
        self.game_store = game_store
        self.manager: ConnectionManager = ConnectionManager()
