from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()


@asynccontextmanager
async def redis_client():
    rc = redis.Redis(
        host=os.environ["REDIS_ENDPOINT"],
        port=16791,
        decode_responses=True,
        username="default",
        password=os.environ["REDIS_PASSWORD"],
    )
    try:
        yield rc
    finally:
        await rc.close()


async def ensure_group(r: redis.Redis, stream: str, group: str):
    """
    Create a consumer group if it doesn't exist.
    """
    try:
        await r.xgroup_create(name=stream, groupname=group, id="$", mkstream=True)
    except Exception as e:
        # BUSYGROUP means the group already exists
        if "BUSYGROUP" not in str(e):
            raise
