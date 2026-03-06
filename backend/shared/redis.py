from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv
import redis.asyncio as redis
import structlog

load_dotenv()

# Redis event streams
MM_MATCHES_STREAM = "mm:matches"

# Redis consumer groups
MM_MATCHES_GROUP = "mm-matches-apis"

logger = structlog.get_logger()


@asynccontextmanager
async def redis_client():
    host = os.environ["REDIS_ENDPOINT"]
    port = int(os.environ.get("REDIS_PORT", 6379))

    logger.info("Establishing connection to Redis", host=host, port=port)

    rc = redis.Redis(
        host=host,
        port=port,
        decode_responses=True,
        username="default",
        password=os.environ["REDIS_PASSWORD"],
    )
    await _ensure_groups(rc)

    try:
        logger.info("Redis connection successful")
        yield rc
    finally:
        logger.info("Closing connection to Redis")
        await rc.close()


async def _ensure_groups(rc: redis.Redis):
    await _ensure_group(rc, MM_MATCHES_STREAM, MM_MATCHES_GROUP)


async def _ensure_group(r: redis.Redis, stream: str, group: str):
    """
    Create a consumer group if it doesn't exist.
    """
    try:
        await r.xgroup_create(name=stream, groupname=group, id="$", mkstream=True)
    except Exception as e:
        # BUSYGROUP means the group already exists
        if "BUSYGROUP" not in str(e):
            raise


def waiting_zset_key(time_control: str) -> str:
    return f"mm:wait:{time_control}"


def queued_key(session_id: str) -> str:
    return f"mm:queued:{session_id}"


def request_hash_key(time_control: str, session_id: str) -> str:
    return f"mm:req:{time_control}:{session_id}"
