from contextlib import contextmanager
from typing import ContextManager, Iterator, Callable
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from models import GameBeginMsg, GameRequestMsg, Message
from main import create_app
import pytest
import os
from dotenv import load_dotenv


load_dotenv()
ORIGIN = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")[0]


WSFactory = Callable[[], ContextManager[WebSocketTestSession]]


@pytest.fixture
def app():
    return create_app()

@pytest.fixture
def ws_user(app: FastAPI) -> WSFactory:
    @contextmanager
    def _ws_user() -> Iterator[WebSocketTestSession]:
        with TestClient(app) as client:
            res = client.get("/session", headers={"origin": ORIGIN})
            assert res.status_code == 200
            with client.websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
                yield ws

    return _ws_user


def test_trivial_matchmaking(ws_user: WSFactory):
    game_request = Message(data=GameRequestMsg())
    with ws_user() as ws1, ws_user() as ws2:
        ws1.send_json(game_request.model_dump())
        ws2.send_json(game_request.model_dump())

        # Both clients should receive the same game ID
        res1 = Message.model_validate(ws1.receive_json())
        res2 = Message.model_validate(ws2.receive_json())

        assert isinstance(res1.data, GameBeginMsg) and isinstance(
            res2.data, GameBeginMsg
        )
        assert res1.data.game_id == res2.data.game_id
