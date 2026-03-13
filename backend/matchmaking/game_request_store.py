from abc import ABC, abstractmethod

import redis.asyncio as redis
import structlog

from shared.redis import queued_key, request_hash_key, waiting_zset_key
from shared.utils import now_ms

logger = structlog.get_logger()

TTL_S = 600


class GameRequestStore(ABC):
    @abstractmethod
    async def register_request(self, session_id: str, time_control: str) -> bool:
        """Registers a game request for the given session ID with the given time control.
        Returns a boolean indicating success. May fail if the player already has an active
        game request."""
        pass

    @abstractmethod
    async def cancel_request(self, session_id: str) -> bool:
        """Cancels any existing game request for the given session ID.
        Returns True if a request existed, else False."""
        pass

    @abstractmethod
    async def list_requests(self, time_control: str) -> list[str]:
        """Lists all session IDs of players that have active game requests for the given
        time control, returning them in descending order of time spent waiting."""
        pass


class RedisGameRequestStore(GameRequestStore):
    def __init__(self, rc: redis.Redis):
        self._rc = rc

    async def register_request(self, session_id: str, time_control: str) -> bool:
        rc = self._rc
        ok = await rc.set(queued_key(session_id), time_control, nx=True, ex=TTL_S)
        if not ok:
            return False

        enqueued_ms = now_ms()
        pipe = rc.pipeline()
        pipe.hset(
            request_hash_key(time_control, session_id),
            mapping={
                "session_id": session_id,
                "time_control": time_control,
                "enqueued_ms": str(enqueued_ms),
            },
        )
        pipe.expire(request_hash_key(time_control, session_id), TTL_S)
        pipe.zadd(waiting_zset_key(time_control), {session_id: enqueued_ms})
        await pipe.execute()
        return True

    async def cancel_request(self, session_id: str) -> bool:
        rc = self._rc
        time_control = await rc.get(queued_key(session_id))
        if time_control is None:
            return False

        pipe = rc.pipeline()
        pipe.delete(queued_key(session_id))
        pipe.delete(request_hash_key(time_control, session_id))
        pipe.zrem(waiting_zset_key(time_control), session_id)
        await pipe.execute()
        return True

    async def list_requests(self, time_control: str) -> list[str]:
        rc = self._rc
        tc_key = waiting_zset_key(time_control)
        members = await rc.zrange(tc_key, 0, -1)  # oldest first

        valid = []
        for session_id in members:
            stored_tc = await rc.get(queued_key(session_id))
            if stored_tc == time_control:
                valid.append(session_id)
            else:
                await rc.zrem(tc_key, session_id)
                logger.info("Pruned stale queue entry", session_id=session_id)
        return valid
