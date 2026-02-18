from contextlib import contextmanager
import time
from typing import ContextManager, Iterator, Callable
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from models import ChatSendMsg, ChatReceiveMsg, GameBeginMsg, GameRequestMsg, Message
from main import create_app
import pytest
import os
from dotenv import load_dotenv


load_dotenv()
ORIGIN = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")[0]


ClientFactory = Callable[[], ContextManager[TestClient]]
WSFactory = Callable[[], ContextManager[WebSocketTestSession]]


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def make_client(app: FastAPI) -> ClientFactory:
    @contextmanager
    def _factory() -> Iterator[TestClient]:
        with TestClient(app) as client:
            res = client.get("/session", headers={"origin": ORIGIN})
            assert res.status_code == 200
            yield client

    return _factory


@pytest.fixture
def make_ws_user(make_client: ClientFactory) -> WSFactory:
    @contextmanager
    def _ws_user() -> Iterator[WebSocketTestSession]:
        with make_client() as client:
            with client.websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
                yield ws

    return _ws_user


def test_happy_path(make_ws_user: WSFactory):
    game_msg = Message(data=GameRequestMsg())
    with make_ws_user() as ws1, make_ws_user() as ws2:
        ws1.send_json(game_msg.model_dump())
        ws2.send_json(game_msg.model_dump())

        # Both clients should receive the same game ID
        res1 = Message.model_validate(ws1.receive_json())
        print("Got one game begin message")
        res2 = Message.model_validate(ws2.receive_json())
        print("Got both game begin messages")

        assert isinstance(res1.data, GameBeginMsg) and isinstance(
            res2.data, GameBeginMsg
        )
        assert res1.data.game_id == res2.data.game_id

        # Subsequent chat requests within that game should be routed to the other player
        chat_msg = Message(data=ChatSendMsg(message="glhf", game_id=res1.data.game_id))
        ws1.send_json(chat_msg.model_dump())

        chat_res = Message.model_validate(ws2.receive_json())
        assert isinstance(chat_res.data, ChatReceiveMsg)
        assert chat_res.data.message == "glhf"


def test_temporary_disconnects(make_client: ClientFactory):
    """Depending on how the app is built, navigating from the matchmaking page to the gameplay page
    may require disconnecting from the initial websocket connection and establishing a new one from
    the gameplay page. Moreover, short disconnects due to poor internet should not prevent play."""

    game_msg = Message(data=GameRequestMsg())
    with make_client() as client1, make_client() as client2:
        with (
            client1.websocket_connect("/ws", headers={"origin": ORIGIN}) as ws1,
            client2.websocket_connect("/ws", headers={"origin": ORIGIN}) as ws2,
        ):
            ws1.send_json(game_msg.model_dump())
            ws2.send_json(game_msg.model_dump())
            res1 = Message.model_validate(ws1.receive_json())
            _ = Message.model_validate(ws2.receive_json())
            assert isinstance(res1.data, GameBeginMsg)

        # Both players disconnect and establish new connections
        with (
            client1.websocket_connect("/ws", headers={"origin": ORIGIN}) as ws1,
            client2.websocket_connect("/ws", headers={"origin": ORIGIN}) as ws2,
        ):
            chat_msg = Message(
                data=ChatSendMsg(message="glhf", game_id=res1.data.game_id)
            )
            ws1.send_json(chat_msg.model_dump())

            chat_res = Message.model_validate(ws2.receive_json())
            assert isinstance(chat_res.data, ChatReceiveMsg)
            assert chat_res.data.message == "glhf"
