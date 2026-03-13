import asyncio
import chess as pychess
from datetime import UTC, datetime
from http import HTTPStatus
from json import JSONDecodeError
import os
import uuid
import redis.asyncio as redis

from dotenv import load_dotenv
from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
)
from pydantic import BaseModel, ValidationError
from structlog import get_logger
import structlog

from shared.redis import queued_key, request_hash_key, waiting_zset_key
from models import Color, Draw, Stalemate
from shared.utils import now_ms
from websocket.models import (
    ChatReceiveMsg,
    ChatSendMsg,
    GameCompleteMsg,
    GameRequestMsg,
    GameResignMsg,
    Message,
    MoveResultMsg,
    MoveSendMsg,
    PingMsg,
    PongMsg,
    msg_log_level,
)
from guest_auth import get_session_id_from_ws
from app_state import AppState
from models import ChatMessage


router = APIRouter()
logger: structlog.stdlib.BoundLogger = get_logger()


class MoveValidation(BaseModel):
    accepted: bool
    san: str | None = None
    reason: str | None = None


load_dotenv()
ALLOWED_ORIGINS = os.environ.get("WS_ALLOWED_ORIGINS", "http://localhost:5173")
ALLOWED_ORIGINS = ALLOWED_ORIGINS.split(",")


@router.get("/__schema/ws-messages", response_model=Message)
def ws_messages_schema_anchor():
    """This endpoint is only here to force the API client generator to create TypeScript
    definitions of the web socket message model. It should not be used."""
    raise RuntimeError("Schema anchor endpoint")


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Main websocket endpoint for the chess app."""
    state: AppState = ws.app.state.state
    origin = ws.headers.get("origin")
    if origin is None or origin not in ALLOWED_ORIGINS:
        await ws.close(code=1008)  # Policy violation
        return

    session_id = get_session_id_from_ws(ws)
    if not session_id:
        await ws.close(3000)  # Unauthorized
        return

    outgoing = await state.manager.connect(session_id, ws)

    try:
        await asyncio.gather(
            consumer_loop(state, session_id, ws),
            producer_loop(outgoing, session_id, ws),
        )
    finally:
        state.manager.disconnect(session_id)


async def consume(state: AppState, session_id: str, msg: Message):
    data = msg.data
    try:
        logger.log(msg_log_level(msg.data), "Received message", **data.model_dump())
        match data.msg_type:
            case "ping":
                await handle_ping(state, session_id, data)
            case "game_request":
                await handle_game_request(state, session_id, data)
            case "game_resign":
                await handle_game_resign(state, session_id, data)
            case "chat_send":
                await handle_chat_send(state, session_id, data)
            case "move_send":
                await handle_move(state, session_id, data)
            case _:
                raise HTTPException(
                    HTTPStatus.BAD_REQUEST,
                    detail=f"Unexpected message type {msg.data.msg_type}",
                )
    except Exception as e:
        logger.error("Unexpected error consuming message", msg=msg, exc_info=e)
        raise


async def consumer_loop(state: AppState, session_id: str, ws: WebSocket):
    while True:
        try:
            data = await ws.receive_json()
        except JSONDecodeError as e:
            logger.error(
                "Received invalid JSON through websocket", exc_info=e, msg=e.msg
            )
            break
        except WebSocketDisconnect:
            break

        try:
            msg = Message.model_validate(data)
            await consume(state, session_id, msg)
        except ValidationError:
            logger.info("Invalid message sent to websocket. Ignoring.", msg=data)


async def producer_loop(queue: asyncio.Queue[Message], session_id: str, ws: WebSocket):
    try:
        while True:
            msg = await queue.get()
            logger.log(msg_log_level(msg.data), "Sending message", **msg.model_dump())
            await ws.send_text(msg.model_dump_json())
    except Exception as e:
        logger.error("Unexpected error sending message", exc_info=e)
        raise


async def handle_ping(state: AppState, session_id: str, msg: PingMsg):
    cm = state.manager
    await cm.send_to(session_id, PongMsg(players=cm.player_count, games=0))


async def handle_game_request(state: AppState, session_id: str, msg: GameRequestMsg):
    """
    Authoritatively enqueue game request.
        - dedupe via mm:queued:{user_id} NX
        - store request details in hash
        - add to ZSET
        - emit to game requests stream to wake up matchmaking daemon
    """

    rc: redis.Redis = state.redis

    request_id = uuid.uuid4().hex
    enqueued_ms = now_ms()
    ttl_s = 600  # TODO: Config somewhere

    # If player already queued, return that fact (up to client what to do)
    ok = await rc.set(queued_key(session_id), request_id, nx=True, ex=ttl_s)
    if not ok:
        raise WebSocketException(
            code=1008, reason="Game already requested for this session ID"
        )

    # TODO: Look up player's rating from database
    rating = 1000

    # Store details and enqueue
    pipe = rc.pipeline()
    pipe.hset(
        request_hash_key(msg.time_control, session_id),
        mapping={
            "request_id": request_id,
            "session_id": session_id,
            "rating": str(rating),
            "time_control": msg.time_control,
            "enqueued_ms": str(enqueued_ms),
        },
    )

    # Keep hash roughly aligned with queued TTL so it doesn't leak
    pipe.expire(request_hash_key(msg.time_control, session_id), ttl_s)

    # Add game request to sorted set, using time of game request as the score
    pipe.zadd(waiting_zset_key(msg.time_control), {session_id: enqueued_ms})

    await pipe.execute()


async def handle_game_resign(state: AppState, session_id: str, msg: GameResignMsg):
    game = await state.game_store.get_game(msg.game_id)
    if game is None:
        return

    if session_id not in [game.white_id, game.black_id]:
        return

    winner = Color.White if session_id == game.black_id else Color.Black
    await state.game_store.end_by_resignation(msg.game_id, winner)

    completion_msg = GameCompleteMsg(game_id=msg.game_id, result=winner.value)
    for sid in [game.white_id, game.black_id]:
        await state.manager.send_to(sid, completion_msg)


async def handle_chat_send(state: AppState, session_id: str, msg: ChatSendMsg):
    timestamp = datetime.now(UTC)
    # Eventual TODO: Chat content filtering

    game = await state.game_store.get_game(msg.game_id)
    if game is None:
        return

    if session_id == game.white_id:
        receiver_session_id = game.black_id
    elif session_id == game.black_id:
        receiver_session_id = game.white_id
    else:
        # Someone tried to send a message to a game they're not playing in
        return

    await state.game_store.append_chat(
        msg.game_id,
        ChatMessage(player_id=session_id, timestamp=timestamp, content=msg.message),
    )
    outgoing_msg = ChatReceiveMsg(timestamp=timestamp, message=msg.message)
    await state.manager.send_to(receiver_session_id, outgoing_msg)


def _validate_move(moves: list[str], move_san: str, is_white: bool) -> MoveValidation:
    board = pychess.Board()
    for m in moves:
        board.push_san(m)

    if (board.turn == pychess.WHITE) != is_white:
        return MoveValidation(accepted=False, reason="Not your turn")

    try:
        move = board.parse_san(move_san)
        san = board.san(move)  # normalise to canonical SAN
        return MoveValidation(accepted=True, san=san)
    except (
        ValueError,
        pychess.InvalidMoveError,
        pychess.IllegalMoveError,
        pychess.AmbiguousMoveError,
    ):
        return MoveValidation(accepted=False, reason="Illegal move")


async def handle_move(state: AppState, session_id: str, msg: MoveSendMsg):
    game = await state.game_store.get_game(msg.game_id)
    if game is None:
        return

    if session_id not in (game.white_id, game.black_id):
        return

    is_white = session_id == game.white_id
    validation = _validate_move(game.moves, msg.move, is_white)

    if validation.accepted and validation.san:
        terminal_result = await state.game_store.append_move(
            msg.game_id, validation.san
        )
        opponent_id = game.black_id if is_white else game.white_id
        move_msg = MoveResultMsg(
            game_id=msg.game_id, accepted=True, move=validation.san
        )
        await state.manager.send_to(session_id, move_msg)
        await state.manager.send_to(opponent_id, move_msg)

        if terminal_result is not None:
            if isinstance(terminal_result, (Stalemate, Draw)):
                result_str = "draw"
            else:
                result_str = terminal_result.winner.value
            completion_msg = GameCompleteMsg(game_id=msg.game_id, result=result_str)
            for sid in [game.white_id, game.black_id]:
                await state.manager.send_to(sid, completion_msg)
    else:
        await state.manager.send_to(
            session_id,
            MoveResultMsg(
                game_id=msg.game_id, accepted=False, reason=validation.reason
            ),
        )
