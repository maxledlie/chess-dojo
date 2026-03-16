import redis.asyncio as redis

from matchmaking.game_request_store import GameRequestStore
from shared.game_store import GameStore
from websocket.manager import ConnectionManager


class AppState:
    def __init__(self, redis: redis.Redis | None, game_store: GameStore, game_request_store: GameRequestStore):
        self.redis = redis
        self.game_store = game_store
        self.game_request_store = game_request_store
        self.manager: ConnectionManager = ConnectionManager(game_request_store)
