from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()

# Redis event streams
MM_REQUESTS_STREAM = "mm:requests"
MM_MATCHES_STREAM = "mm:matches"

# Redis consumer groups
MM_REQUESTS_GROUP = "mm-requests-daemons"
MM_MATCHES_GROUP = "mm-matches-apis"


@asynccontextmanager
async def redis_client():
    rc = redis.Redis(
        host=os.environ["REDIS_ENDPOINT"],
        port=16791,
        decode_responses=True,
        username="default",
        password=os.environ["REDIS_PASSWORD"],
    )
    await _ensure_groups(rc)

    try:
        yield rc
    finally:
        await rc.close()


async def _ensure_groups(rc: redis.Redis):
    await _ensure_group(rc, MM_MATCHES_STREAM, MM_MATCHES_GROUP)
    await _ensure_group(rc, MM_REQUESTS_STREAM, MM_REQUESTS_GROUP)


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
