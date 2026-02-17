import asyncio
import os
import string
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from models import (
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


app = FastAPI()

# TODO: Get frontend origin from environment variables for deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


load_dotenv()
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
ALLOWED_ORIGINS = ALLOWED_ORIGINS.split(",")


@app.get("/")
async def root():
    return {"message": "Hello World"}


class Game(BaseModel):
    white_session_id: str
    black_session_id: str


class ConnectionManager:
    _clients: dict[str, tuple[WebSocket, asyncio.Queue[Message]]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        queue = asyncio.Queue()
        self._clients[session_id] = (websocket, queue)
        return queue

    def disconnect(self, session_id: str):
        del self._clients[session_id]

    async def send_to(self, session_id: str, message: Message):
        (_, q) = self._clients[session_id]
        await q.put(message)


game_requests: list[str] = []
ongoing_games: dict[str, Game] = {}
manager = ConnectionManager()


async def consume(session_id: str, msg: Message):
    data = msg.data
    match data.msg_type:
        case "game_request":
            await handle_game_request(session_id)
        case "game_resign":
            await handle_game_resign(session_id, data)
        case _:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST,
                detail=f"Unexpected message type {msg.data.msg_type}",
            )


async def consumer_loop(session_id: str, ws: WebSocket):
    while True:
        try:
            data = await ws.receive_json()
        except WebSocketDisconnect:
            break

        try:
            msg = Message.model_validate(data)
            await consume(session_id, msg)
        except ValidationError:
            raise HTTPException(HTTPStatus.BAD_REQUEST)


async def producer_loop(queue: asyncio.Queue[Message], ws: WebSocket):
    while True:
        msg = await queue.get()
        await ws.send_text(msg.model_dump_json())


@app.get(
    "/session",
    description="""If using cress as a guest, call this endpoint before establishing a websocket connection
    to receive a session cookie. This will enable you to rejoin a game in the event of a temporary disconnection.""",
    response_model=SessionResponse,
)
async def ensure_session(request: Request, response: Response):
    return ensure_guest_session(request, response)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    origin = ws.headers.get("origin")
    if origin is None or origin not in ALLOWED_ORIGINS:
        await ws.close(code=1008)  # Policy violation
        return

    session_id = get_session_id_from_ws(ws)
    if not session_id:
        await ws.close(3000)  # Unauthorized
        return

    outgoing = await manager.connect(session_id, ws)

    # TODO: Handle disconnect
    await asyncio.gather(consumer_loop(session_id, ws), producer_loop(outgoing, ws))


async def handle_game_request(session_id: str):
    if len(game_requests) > 0:
        try:
            await setup_game(game_requests[0], session_id)
        except IndexError:
            # There's a chance a different player might have jumped in with that host in the meantime
            raise HTTPException(500, "Unhandled concurrency error")
    else:
        game_requests.append(session_id)


async def handle_game_resign(session_id: str, msg: GameResignMsg):
    # Broadcast the result to both players
    game = ongoing_games.get(msg.game_id)
    if game is None:
        return

    if session_id not in [game.white_session_id, game.black_session_id]:
        # TODO: Logging
        return

    result = "white" if session_id == game.black_session_id else "black"

    completion_msg = GameCompleteMsg(game_id=msg.game_id, result=result)
    for session_id in [game.white_session_id, game.black_session_id]:
        await manager.send_to(session_id, Message(data=completion_msg))

    # TODO: Don't delete the game record until completion acknowledged by both parties.
    # (And require similar acknowledgement in other cases)
    del ongoing_games[msg.game_id]


async def setup_game(host_session_id: str, joiner_session_id: str):
    # Randomly generate a unique identifier for the game
    game_id = generate_game_id()
    await manager.send_to(
        host_session_id, Message(data=GameBeginMsg(game_id=game_id, you_are_white=True))
    )
    await manager.send_to(
        joiner_session_id,
        Message(data=GameBeginMsg(game_id=game_id, you_are_white=False)),
    )
    ongoing_games[game_id] = Game(
        white_session_id=host_session_id, black_session_id=joiner_session_id
    )


def generate_game_id(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))
