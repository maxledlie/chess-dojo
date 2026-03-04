import json
from abc import ABC, abstractmethod

import redis.asyncio as redis
from pydantic import TypeAdapter

from models import ChatMessage, Game, GameResult

_result_adapter: TypeAdapter[GameResult] = TypeAdapter(GameResult)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class GameStore(ABC):
    @abstractmethod
    async def create_game(self, game_id: str, game: Game) -> None: ...

    @abstractmethod
    async def get_game(self, game_id: str) -> Game | None: ...

    @abstractmethod
    async def get_moves(self, game_id: str) -> list[str]: ...

    @abstractmethod
    async def append_move(self, game_id: str, san: str) -> None: ...

    @abstractmethod
    async def append_chat(self, game_id: str, msg: ChatMessage) -> None: ...

    @abstractmethod
    async def set_result(self, game_id: str, result: GameResult) -> None: ...

    @abstractmethod
    async def delete_game(self, game_id: str) -> None: ...


# ---------------------------------------------------------------------------
# Redis implementation
# ---------------------------------------------------------------------------


def _game_key(game_id: str) -> str:
    return f"game:{game_id}"


def _moves_key(game_id: str) -> str:
    return f"game:{game_id}:moves"


def _chat_key(game_id: str) -> str:
    return f"game:{game_id}:chat"


class RedisGameStore(GameStore):
    def __init__(self, rc: redis.Redis):
        self._rc = rc

    async def create_game(self, game_id: str, game: Game) -> None:
        mapping: dict[str, str] = {
            "white_id": game.white_id,
            "black_id": game.black_id,
        }
        if game.result is not None:
            mapping["result"] = game.result.model_dump_json()
        await self._rc.hset(_game_key(game_id), mapping=mapping)

    async def get_game(self, game_id: str) -> Game | None:
        pipe = self._rc.pipeline()
        pipe.hgetall(_game_key(game_id))
        pipe.lrange(_moves_key(game_id), 0, -1)
        pipe.lrange(_chat_key(game_id), 0, -1)
        meta, moves, chat_raw = await pipe.execute()

        if not meta:
            return None

        result_raw = meta.get("result")
        chat = [ChatMessage(**json.loads(c)) for c in chat_raw]
        return Game(
            white_id=meta["white_id"],
            black_id=meta["black_id"],
            result=_result_adapter.validate_json(result_raw) if result_raw else None,
            moves=moves,
            chat=chat,
        )

    async def get_moves(self, game_id: str) -> list[str]:
        return await self._rc.lrange(_moves_key(game_id), 0, -1)

    async def append_move(self, game_id: str, san: str) -> None:
        await self._rc.rpush(_moves_key(game_id), san)

    async def append_chat(self, game_id: str, msg: ChatMessage) -> None:
        await self._rc.rpush(_chat_key(game_id), msg.model_dump_json())

    async def set_result(self, game_id: str, result: GameResult) -> None:
        await self._rc.hset(_game_key(game_id), mapping={"result": result.model_dump_json()})

    async def delete_game(self, game_id: str) -> None:
        await self._rc.delete(
            _game_key(game_id), _moves_key(game_id), _chat_key(game_id)
        )


# ---------------------------------------------------------------------------
# In-memory implementation (for unit tests)
# ---------------------------------------------------------------------------


class MemoryGameStore(GameStore):
    def __init__(self):
        self._games: dict[str, Game] = {}

    async def create_game(self, game_id: str, game: Game) -> None:
        self._games[game_id] = game.model_copy(deep=True)

    async def get_game(self, game_id: str) -> Game | None:
        game = self._games.get(game_id)
        return game.model_copy(deep=True) if game is not None else None

    async def get_moves(self, game_id: str) -> list[str]:
        game = self._games.get(game_id)
        return list(game.moves) if game is not None else []

    async def append_move(self, game_id: str, san: str) -> None:
        game = self._games.get(game_id)
        if game is not None:
            game.moves.append(san)

    async def append_chat(self, game_id: str, msg: ChatMessage) -> None:
        game = self._games.get(game_id)
        if game is not None:
            game.chat.append(msg)

    async def set_result(self, game_id: str, result: GameResult) -> None:
        game = self._games.get(game_id)
        if game is not None:
            game.result = result

    async def delete_game(self, game_id: str) -> None:
        self._games.pop(game_id, None)
