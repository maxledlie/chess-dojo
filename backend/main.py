import asyncio
import string
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from models import GameCompleteMsg, Message, GameResignMsg, GameBeginMsg
from pydantic import BaseModel, ValidationError
from http import HTTPStatus
from uuid import UUID, uuid4
import secrets


app = FastAPI()

# TODO: Get frontend origin from environment variables for deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Hello World"}


class Game(BaseModel):
    white_session_id: UUID
    black_session_id: UUID


class ConnectionManager:
    _clients: dict[UUID, tuple[WebSocket, asyncio.Queue[Message]]] = {}

    async def connect(self, session_id: UUID, websocket: WebSocket):
        await websocket.accept()
        queue = asyncio.Queue()
        self._clients[session_id] = (websocket, queue)
        return queue

    def disconnect(self, session_id: UUID):
        del self._clients[session_id]

    async def send_to(self, session_id: UUID, message: Message):
        (_, q) = self._clients[session_id]
        await q.put(message)


game_requests: list[UUID] = []
ongoing_games: dict[str, Game] = {}
manager = ConnectionManager()


async def consume(session_id: UUID, msg: Message):
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


async def consumer_loop(session_id: UUID, ws: WebSocket):
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


@app.websocket("/ws")
async def matchmake(ws: WebSocket):
    session_id = uuid4()
    outgoing = await manager.connect(session_id, ws)

    # TODO: Handle disconnect
    await asyncio.gather(consumer_loop(session_id, ws), producer_loop(outgoing, ws))


async def handle_game_request(session_id: UUID):
    if len(game_requests) > 0:
        try:
            await setup_game(game_requests[0], session_id)
        except IndexError:
            # There's a chance a different player might have jumped in with that host in the meantime
            raise HTTPException(500, "Unhandled concurrency error")
    else:
        game_requests.append(session_id)


async def handle_game_resign(session_id: UUID, msg: GameResignMsg):
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


async def setup_game(host_session_id: UUID, joiner_session_id: UUID):
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
