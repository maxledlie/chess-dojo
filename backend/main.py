import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from models import Message, MessageType
from pydantic import BaseModel, ValidationError
from http import HTTPStatus
from uuid import UUID, uuid4


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
    host_session_id: UUID
    joiner_session_id: UUID


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
pending_games: list[Game] = []
ongoing_games: list[Game] = []
manager = ConnectionManager()


async def consume(session_id: UUID, msg: Message):
    match msg.type:
        case MessageType.GameRequest:
            await handle_game_request(session_id)
        case _:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST, detail=f"Unexpected message type {msg.type}"
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
        await ws.send_json(msg.model_dump())


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    session_id = uuid4()
    outgoing = await manager.connect(session_id, ws)

    # TODO: Handle disconnect
    await asyncio.gather(consumer_loop(session_id, ws), producer_loop(outgoing, ws))


async def handle_game_request(session_id: UUID):
    print("Handling game request")
    if len(game_requests) > 0:
        try:
            await setup_game(game_requests[0], session_id)
        except IndexError:
            # There's a chance a different player might have jumped in with that host in the meantime
            raise HTTPException(500, "Unhandled concurrency error")
    else:
        game_requests.append(session_id)


async def setup_game(host_session_id: UUID, joiner_session_id: UUID):
    await manager.send_to(host_session_id, Message(type=MessageType.GameBegin))
    await manager.send_to(joiner_session_id, Message(type=MessageType.GameBegin))


game_requests = []
