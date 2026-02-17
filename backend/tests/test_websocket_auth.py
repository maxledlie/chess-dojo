import pytest
from main import create_app
from fastapi.testclient import TestClient
from fastapi import WebSocketDisconnect
from models import GameRequestMsg, Message, SessionResponse
from dotenv import load_dotenv
import os


load_dotenv()


@pytest.mark.anyio
async def test_unauthenticated_ws_rejected():
    """Attempting to connect to the websocket without a session cookie should fail."""
    client = TestClient(create_app())

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as ws:
            req = Message(data=GameRequestMsg())
            ws.send_json(req.model_dump())


async def _ensure_session(client: TestClient) -> str:
    res = client.get("/session")
    res = SessionResponse.model_validate(res.json())
    return res.session_id


@pytest.mark.anyio
@pytest.mark.parametrize("origin", [None, "", "https://evil.com"])
async def test_invalid_origin_rejected(origin: str):
    client = TestClient(create_app())
    await _ensure_session(client)
    headers = {} if origin is None else {"origin": origin}
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers=headers) as ws:
            req = Message(data=GameRequestMsg())
            ws.send_json(req.model_dump())


@pytest.mark.anyio
async def test_successful_auth():
    origin = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")[0]
    client = TestClient(create_app())
    await _ensure_session(client)
    with client.websocket_connect("/ws", headers={"origin": origin}) as ws:
        req = Message(data=GameRequestMsg())
        ws.send_json(req.model_dump())
