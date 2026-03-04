import json
from abc import ABC, abstractmethod

import chess as pychess
import redis.asyncio as redis
from pydantic import TypeAdapter

from models import ChatMessage, ClockFlag, Color, Draw, DrawReason, Game, GameResult, Mate, Resign, Stalemate

_result_adapter: TypeAdapter[GameResult] = TypeAdapter(GameResult)


def _result_from_moves(moves: list[str]) -> GameResult | None:
    board = pychess.Board()
    for m in moves:
        board.push_san(m)
    outcome = board.outcome()
    if outcome is None:
        return None
    if outcome.termination == pychess.Termination.CHECKMATE:
        winner = Color.White if outcome.winner else Color.Black
        return Mate(winner=winner)
    if outcome.termination == pychess.Termination.STALEMATE:
        return Stalemate()
    if outcome.termination == pychess.Termination.INSUFFICIENT_MATERIAL:
        return Draw(reason=DrawReason.InsufficientMaterial)
    if outcome.termination == pychess.Termination.SEVENTYFIVE_MOVES:
        return Draw(reason=DrawReason.SeventyFiveMove)
    if outcome.termination == pychess.Termination.FIVEFOLD_REPETITION:
        return Draw(reason=DrawReason.Repetition)
    return None


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
    async def append_move(self, game_id: str, san: str) -> GameResult | None:
        """Append a move and atomically set the game result if the move is terminal
        (checkmate, stalemate, insufficient material, seventy-five move rule, or
        fivefold repetition). Returns the terminal GameResult, or None if the game
        continues. For all other termination conditions use the explicit end_by_*
        methods below."""
        ...

    @abstractmethod
    async def append_chat(self, game_id: str, msg: ChatMessage) -> None: ...

    @abstractmethod
    async def end_by_resignation(self, game_id: str, winner: Color) -> None: ...

    @abstractmethod
    async def end_by_timeout(self, game_id: str, winner: Color) -> None: ...

    @abstractmethod
    async def end_by_draw_agreement(self, game_id: str) -> None: ...

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

    async def append_move(self, game_id: str, san: str) -> GameResult | None:
        current_moves = await self._rc.lrange(_moves_key(game_id), 0, -1)
        result = _result_from_moves(current_moves + [san])
        pipe = self._rc.pipeline()
        pipe.rpush(_moves_key(game_id), san)
        if result is not None:
            pipe.hset(_game_key(game_id), mapping={"result": result.model_dump_json()})
        await pipe.execute()
        return result

    async def append_chat(self, game_id: str, msg: ChatMessage) -> None:
        await self._rc.rpush(_chat_key(game_id), msg.model_dump_json())

    async def _set_result(self, game_id: str, result: GameResult) -> None:
        await self._rc.hset(_game_key(game_id), mapping={"result": result.model_dump_json()})

    async def end_by_resignation(self, game_id: str, winner: Color) -> None:
        await self._set_result(game_id, Resign(winner=winner))

    async def end_by_timeout(self, game_id: str, winner: Color) -> None:
        await self._set_result(game_id, ClockFlag(winner=winner))

    async def end_by_draw_agreement(self, game_id: str) -> None:
        await self._set_result(game_id, Draw(reason=DrawReason.Agreement))

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

    async def append_move(self, game_id: str, san: str) -> GameResult | None:
        game = self._games.get(game_id)
        if game is None:
            return None
        game.moves.append(san)
        result = _result_from_moves(game.moves)
        if result is not None:
            game.result = result
        return result

    async def append_chat(self, game_id: str, msg: ChatMessage) -> None:
        game = self._games.get(game_id)
        if game is not None:
            game.chat.append(msg)

    def _set_result(self, game_id: str, result: GameResult) -> None:
        game = self._games.get(game_id)
        if game is not None:
            game.result = result

    async def end_by_resignation(self, game_id: str, winner: Color) -> None:
        self._set_result(game_id, Resign(winner=winner))

    async def end_by_timeout(self, game_id: str, winner: Color) -> None:
        self._set_result(game_id, ClockFlag(winner=winner))

    async def end_by_draw_agreement(self, game_id: str) -> None:
        self._set_result(game_id, Draw(reason=DrawReason.Agreement))

    async def delete_game(self, game_id: str) -> None:
        self._games.pop(game_id, None)
