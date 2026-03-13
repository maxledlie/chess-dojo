import asyncio
import secrets
import string

import structlog
from shared.redis import (
    MM_MATCHES_STREAM,
    redis_client,
)

from matchmaking.game_request_store import GameRequestStore, RedisGameRequestStore
from shared.utils import now_ms


logger = structlog.get_logger()

POLL_INTERVAL_S = 0.5


async def _amain(daemon_id: str):
    async with redis_client() as rc:
        store = RedisGameRequestStore(rc)
        while True:
            try:
                await _poll_and_match(rc, store)
                await asyncio.sleep(POLL_INTERVAL_S)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Unexpected error in matchmaking loop", exc_info=e)
                await asyncio.sleep(POLL_INTERVAL_S)


async def _poll_and_match(rc, store: GameRequestStore):
    tc_keys = await rc.keys("mm:wait:*")
    for tc_key in tc_keys:
        time_control = tc_key[len("mm:wait:"):]
        valid = await store.list_requests(time_control)

        while len(valid) >= 2:
            session_a = valid.pop(0)
            session_b = valid.pop(0)
            game_id = generate_game_id()

            await store.cancel_request(session_a)
            await store.cancel_request(session_b)
            await rc.xadd(
                MM_MATCHES_STREAM,
                fields={
                    "session_a": session_a,
                    "session_b": session_b,
                    "game_id": game_id,
                    "time_control": time_control,
                    "created_ts": str(now_ms()),
                },
                maxlen=10_000,
                approximate=True,
            )
            logger.info("Created match", game_id=game_id, session_a=session_a, session_b=session_b)


def generate_game_id(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


async def main(daemon_id: str):
    try:
        logger.bind(daemon_id=daemon_id)
        await _amain(daemon_id)
    except Exception as e:
        logger.error("Unhandled exception", exc_info=e)
