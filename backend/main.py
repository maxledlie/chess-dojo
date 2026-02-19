import asyncio
import os
import string
import threading
from datetime import datetime, UTC
from fastapi import (
    APIRouter,
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from models import (
    ChatReceiveMsg,
    ChatSendMsg,
    GameCompleteMsg,
    Message,
    GameResignMsg,
    GameBeginMsg,
    SessionResponse,
)
from pydantic import BaseModel, ValidationError
from http import HTTPStatus
from guest_auth import ensure_guest_session, get_session_id_from_ws
import secrets
from dotenv import load_dotenv


class ConnectionManager:
    def __init__(self):
        self._clients: dict[str, tuple[WebSocket, asyncio.Queue[Message]]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        queue = asyncio.Queue()
        self._clients[session_id] = (websocket, queue)
        return queue

    def disconnect(self, session_id: str):
        del self._clients[session_id]

    async def send_to(self, session_id: str, message: Message):
        if session_id not in self._clients:
            return
        (_, q) = self._clients[session_id]
        await q.put(message)


class Game(BaseModel):
    white_session_id: str
    black_session_id: str


# Move this state into something like Redis later for persistence through redeploys
class AppState:
    def __init__(self):
        self.game_requests: list[str] = []
        self.ongoing_games: dict[str, Game] = {}
        self.manager: ConnectionManager = ConnectionManager()
        self._game_request_lock: threading.Lock = threading.Lock()

    @property
    def game_request_lock(self):
        """Return an async context manager for the lock"""
        return _ThreadingLockAsyncWrapper(self._game_request_lock)


class _ThreadingLockAsyncWrapper:
    """Wraps a threading.Lock to be used with async with"""

    def __init__(self, lock: threading.Lock):
        self.lock = lock

    async def __aenter__(self):
        self.lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.lock.release()
        return False


load_dotenv()
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
ALLOWED_ORIGINS = ALLOWED_ORIGINS.split(",")


async def consume(state: AppState, session_id: str, msg: Message):
    data = msg.data
    try:
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
        import traceback

        traceback.print_exc()
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
            raise HTTPException(HTTPStatus.BAD_REQUEST)


async def producer_loop(queue: asyncio.Queue[Message], session_id: str, ws: WebSocket):
    try:
        while True:
            msg = await queue.get()
            await ws.send_text(msg.model_dump_json())
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise


router = APIRouter()


@router.get(
    "/session",
    description="""If using cress as a guest, call this endpoint before establishing a websocket connection
    to receive a session cookie. This will enable you to rejoin a game in the event of a temporary disconnection.""",
    response_model=SessionResponse,
)
async def ensure_session(request: Request, response: Response):
    return ensure_guest_session(request, response)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
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
    game = state.ongoing_games.get(msg.game_id)
    if game is None:
        return

    if session_id not in [game.white_session_id, game.black_session_id]:
        # TODO: Logging
        return

    result = "white" if session_id == game.black_session_id else "black"

    completion_msg = GameCompleteMsg(game_id=msg.game_id, result=result)
    for session_id in [game.white_session_id, game.black_session_id]:
        await state.manager.send_to(session_id, Message(data=completion_msg))

    # TODO: Don't delete the game record until completion acknowledged by both parties.
    # (And require similar acknowledgement in other cases)
    del state.ongoing_games[msg.game_id]


async def handle_chat_send(state: AppState, session_id: str, msg: ChatSendMsg):
    timestamp = datetime.now(UTC)
    # Eventual TODO: Chat content filtering

    game = state.ongoing_games.get(msg.game_id, None)
    if game is None:
        return

    if session_id == game.white_session_id:
        receiver_session_id = game.black_session_id
    elif session_id == game.black_session_id:
        receiver_session_id = game.white_session_id
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
    state.ongoing_games[game_id] = Game(
        white_session_id=host_session_id, black_session_id=joiner_session_id
    )


def generate_game_id(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


def create_app() -> FastAPI:
    app = FastAPI()
    app.state.state = AppState()
    app.include_router(router)

    # TODO: Get frontend origin from environment variables for deployment
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()
