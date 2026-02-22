import asyncio
from datetime import UTC, datetime
from http import HTTPStatus
import os
import secrets
import string

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from structlog import get_logger
import structlog

from models import Game
from websocket.models import (
    ChatReceiveMsg,
    ChatSendMsg,
    GameBeginMsg,
    GameCompleteMsg,
    GameResignMsg,
    Message,
)
from guest_auth import get_session_id_from_ws
from main import AppState


router = APIRouter()
logger: structlog.stdlib.BoundLogger = get_logger()

load_dotenv()
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
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
        # Remove from game requests if still waiting
        async with state.game_request_lock:
            if session_id in state.game_requests:
                state.game_requests.remove(session_id)


async def consume(state: AppState, session_id: str, msg: Message):
    data = msg.data
    try:
        logger.info("Received message", **data.model_dump())
        match data.msg_type:
            case "game_request":
                await handle_game_request(state, session_id)
            case "game_resign":
                await handle_game_resign(state, session_id, data)
            case "chat_send":
                await handle_chat_send(state, session_id, data)
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
        except WebSocketDisconnect:
            break

        try:
            msg = Message.model_validate(data)
            await consume(state, session_id, msg)
        except ValidationError:
            logger.info("Invalid message sent to websocket", msg=data)
            raise HTTPException(HTTPStatus.BAD_REQUEST)


async def producer_loop(queue: asyncio.Queue[Message], session_id: str, ws: WebSocket):
    try:
        while True:
            msg = await queue.get()
            logger.info("Sending message", **msg.model_dump())
            await ws.send_text(msg.model_dump_json())
    except Exception as e:
        logger.error("Unexpected error sending message", exc_info=e)
        raise


async def handle_game_request(state: AppState, session_id: str):
    async with state.game_request_lock:
        if len(state.game_requests) > 0:
            try:
                host_session_id = state.game_requests.pop(0)
                await setup_game(state, host_session_id, session_id)
            except IndexError:
                # There's a chance a different player might have jumped in with that host in the meantime
                raise HTTPException(500, "Unhandled concurrency error")
        else:
            state.game_requests.append(session_id)


async def handle_game_resign(state: AppState, session_id: str, msg: GameResignMsg):
    # Broadcast the result to both players
    game = state.games.get(msg.game_id)
    if game is None:
        return

    if session_id not in [game.white_id, game.black_id]:
        # TODO: Logging
        return

    result = "white" if session_id == game.black_id else "black"

    completion_msg = GameCompleteMsg(game_id=msg.game_id, result=result)
    for session_id in [game.white_id, game.black_id]:
        await state.manager.send_to(session_id, Message(data=completion_msg))

    # TODO: Don't delete the game record until completion acknowledged by both parties.
    # (And require similar acknowledgement in other cases)
    del state.games[msg.game_id]


async def handle_chat_send(state: AppState, session_id: str, msg: ChatSendMsg):
    timestamp = datetime.now(UTC)
    # Eventual TODO: Chat content filtering

    game = state.games.get(msg.game_id, None)
    if game is None:
        return

    if session_id == game.white_id:
        receiver_session_id = game.black_id
    elif session_id == game.black_id:
        receiver_session_id = game.white_id
    else:
        # Someone tried to send a message to a game they're not playing in
        return

    outgoing_msg = Message(
        data=ChatReceiveMsg(timestamp=timestamp, message=msg.message)
    )
    await state.manager.send_to(receiver_session_id, outgoing_msg)


async def setup_game(state: AppState, host_session_id: str, joiner_session_id: str):
    # Randomly generate a unique identifier for the game
    game_id = generate_game_id()
    await state.manager.send_to(
        host_session_id, Message(data=GameBeginMsg(game_id=game_id, you_are_white=True))
    )
    await state.manager.send_to(
        joiner_session_id,
        Message(data=GameBeginMsg(game_id=game_id, you_are_white=False)),
    )
    state.games[game_id] = Game(
        white_id=host_session_id, black_id=joiner_session_id, moves=[], chat=[]
    )


def generate_game_id(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))
