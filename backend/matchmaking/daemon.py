import asyncio
import secrets
import string

import structlog
from shared.redis import (
    MM_MATCHES_STREAM,
    MM_REQUESTS_GROUP,
    MM_REQUESTS_STREAM,
    redis_client,
)
from dataclasses import dataclass, asdict

from shared.utils import now_ms


logger = structlog.get_logger()


# Number of matchmaking requests to read at once
MM_BATCH_SIZE = 50

# How long to wait for a matchmaking request before retrying if the queue is empty
MM_WAIT_TIME = 1000


@dataclass(frozen=True)
class MMRequest:
    msg_id: str
    session_id: str
    rating: int
    time_control: str
    created_ts: int


@dataclass(frozen=True)
class Match:
    game_id: str
    msg_id_a: str
    msg_id_b: str
    session_a: str
    session_b: str
    time_control: str


async def _amain(daemon_id: str):
    async with redis_client() as rc:
        # Clear pending entries list on startup

        # In memory queue for waiting players per time control
        waiting: dict[str, list[MMRequest]] = {}

        while True:
            try:
                resp = await rc.xreadgroup(
                    groupname=MM_REQUESTS_GROUP,
                    consumername=daemon_id,
                    streams={MM_REQUESTS_STREAM: ">"},
                    count=MM_BATCH_SIZE,
                    block=MM_WAIT_TIME,
                )
                if not resp:
                    # Timed out waiting for the first game request. Restart read.
                    continue

                for stream, entries in resp:
                    for msg_id, fields in entries:
                        req = MMRequest(
                            msg_id=msg_id,
                            session_id=fields["session_id"],
                            rating=int(fields.get("rating", "1200")),
                            time_control=fields.get("time_control", "blitz_5p0"),
                            created_ts=int(fields.get("ts", str(now_ms()))),
                        )
                        logger.info("Consuming matchmaking request", **asdict(req))

                        # Add to waiting pool
                        pool = waiting.setdefault(req.time_control, [])
                        pool.append(req)

                        matches = find_matches(pool)

                        # Persist "match found" events and acknowledge the requests so other
                        # running daemons won't try to pair them.
                        for match in matches:
                            logger.info(
                                "Created match",
                                session_a=match.session_a,
                                session_b=match.session_b,
                            )
                            await rc.xadd(
                                MM_MATCHES_STREAM,
                                fields={
                                    "session_a": match.session_a,
                                    "session_b": match.session_b,
                                    "game_id": match.game_id,
                                    "time_control": match.time_control,
                                    "created_ts": str(now_ms()),
                                },
                                maxlen=10_000,
                                approximate=True,
                            )

                            for msg_id in [match.msg_id_a, match.msg_id_b]:
                                logger.debug(
                                    "Sending ack for game request", msg_id=msg_id
                                )
                                await rc.xack(
                                    MM_REQUESTS_STREAM, MM_REQUESTS_GROUP, msg_id
                                )

            except asyncio.CancelledError:
                logger.info("Matchmaking daemon task cancelled")
                raise


def find_matches(pool: list[MMRequest]) -> list[Match]:
    """
    Runs a single matchmaking iteration on a pool of waiting players.
    NOTE: This mutates the pool by removing players who are matched
    """

    # Naive implementation. Just match first two players in same time control
    # TODO:
    # - Prefer players closer in rating
    # - Prefer players who have been waiting longer
    # - Gradually widen acceptable rating range the longer players have been waiting
    # This may require moving waiting players into a separate redis ZSET so we can
    # efficiently search based on rating ranges.

    if len(pool) >= 2:
        a = pool.pop()
        b = pool.pop()

        game_id = generate_game_id()

        return [
            Match(
                game_id=game_id,
                msg_id_a=a.msg_id,
                msg_id_b=b.msg_id,
                session_a=a.session_id,
                session_b=b.session_id,
                time_control=a.time_control,
            )
        ]
    else:
        return []


def generate_game_id(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


async def main(daemon_id: str):
    try:
        logger.bind(daemon_id=daemon_id)
        await _amain(daemon_id)
    except Exception as e:
        logger.error("Unhandled exception", exc_info=e)
