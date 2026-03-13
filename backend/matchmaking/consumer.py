import asyncio

import redis.asyncio as redis
import structlog

from app_state import AppState
from models import Game
from shared.redis import MM_MATCHES_GROUP, MM_MATCHES_STREAM
from websocket.models import GameBeginMsg, Message

logger = structlog.get_logger()

BATCH_SIZE = 50
BLOCK_MS = 1000


async def matches_consumer(state: AppState, consumer_id: str):
    """
    Reads matched pairs from the mm:matches Redis stream and notifies both players
    via their WebSocket connections.
    """
    rc: redis.Redis = state.redis
    while True:
        try:
            resp = await rc.xreadgroup(
                groupname=MM_MATCHES_GROUP,
                consumername=consumer_id,
                streams={MM_MATCHES_STREAM: ">"},
                count=BATCH_SIZE,
                block=BLOCK_MS,
            )
            if not resp:
                continue

            for _stream, entries in resp:
                for msg_id, fields in entries:
                    try:
                        await _handle_match(state, fields)
                        await rc.xack(MM_MATCHES_STREAM, MM_MATCHES_GROUP, msg_id)
                    except Exception as e:
                        logger.error(
                            "Failed to handle match", msg_id=msg_id, exc_info=e
                        )

        except asyncio.CancelledError:
            logger.info("Matches consumer cancelled")
            raise
        except Exception as e:
            logger.error("Unexpected error in matches consumer", exc_info=e)


async def _handle_match(state: AppState, fields: dict):
    session_a = fields["session_a"]
    session_b = fields["session_b"]
    game_id = fields["game_id"]

    await state.game_store.create_game(
        game_id, Game(white_id=session_a, black_id=session_b)
    )

    await state.manager.send_to(
        session_a,
        GameBeginMsg(you_are_white=True, game_id=game_id),
    )
    await state.manager.send_to(
        session_b,
        GameBeginMsg(you_are_white=False, game_id=game_id),
    )
    logger.info("Game started", game_id=game_id, white=session_a, black=session_b)
