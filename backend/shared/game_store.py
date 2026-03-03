import json

import redis.asyncio as redis

from models import ChatMessage, Game


def _game_key(game_id: str) -> str:
    return f"game:{game_id}"


def _moves_key(game_id: str) -> str:
    return f"game:{game_id}:moves"


def _chat_key(game_id: str) -> str:
    return f"game:{game_id}:chat"


async def create_game(rc: redis.Redis, game_id: str, white_id: str, black_id: str) -> None:
    await rc.hset(
        _game_key(game_id),
        mapping={"white_id": white_id, "black_id": black_id, "status": "active"},
    )


async def get_game(rc: redis.Redis, game_id: str) -> Game | None:
    pipe = rc.pipeline()
    pipe.hgetall(_game_key(game_id))
    pipe.lrange(_moves_key(game_id), 0, -1)
    pipe.lrange(_chat_key(game_id), 0, -1)
    meta, moves, chat_raw = await pipe.execute()

    if not meta:
        return None

    chat = [ChatMessage(**json.loads(c)) for c in chat_raw]
    return Game(
        white_id=meta["white_id"],
        black_id=meta["black_id"],
        moves=moves,
        chat=chat,
    )


async def get_moves(rc: redis.Redis, game_id: str) -> list[str]:
    return await rc.lrange(_moves_key(game_id), 0, -1)


async def append_move(rc: redis.Redis, game_id: str, san: str) -> None:
    await rc.rpush(_moves_key(game_id), san)


async def append_chat(rc: redis.Redis, game_id: str, msg: ChatMessage) -> None:
    await rc.rpush(_chat_key(game_id), msg.model_dump_json())


async def delete_game(rc: redis.Redis, game_id: str) -> None:
    await rc.delete(_game_key(game_id), _moves_key(game_id), _chat_key(game_id))
