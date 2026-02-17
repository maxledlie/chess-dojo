import pytest
from main import app
from fastapi.testclient import TestClient
from models import GameRequestMsg, Message


@pytest.mark.anyio
async def test_happy_path():
    """Two players request a game.
    They should be connected and given the ID of the created game.
    Chat requests should be forwarded to the other party via the server.
    """

    client = TestClient(app)

    with client.websocket_connect("/ws") as ws1, client.websocket_connect("/ws") as ws2:
        req = Message(data=GameRequestMsg())

        # Both clients should receive a signed session token
        ws1.send_json(req.model_dump())
        ws2.send_json(req.model_dump())

        # Both clients should receive invitations to the game
        res1 = ws1.receive_json()
        res2 = ws2.receive_json()
        breakpoint()
