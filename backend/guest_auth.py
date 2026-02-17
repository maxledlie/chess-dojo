import os
import time
from dotenv import load_dotenv
import secrets
from fastapi import Request, Response, WebSocket
from itsdangerous import BadSignature, URLSafeSerializer

from models import SessionResponse


load_dotenv()

SECRET_KEY = os.environ.get("SESSION_SECRET")
if SECRET_KEY is None:
    raise Exception("Could not find secret session token")

SESSION_COOKIE_NAME = "session"
MAX_AGE = 60 * 60 * 24 * 30  # Guest session cookies expire after 30 days

signer = URLSafeSerializer(SECRET_KEY, salt="session")


def ensure_guest_session(request: Request, response: Response) -> SessionResponse:
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
    session_id = _session_id_from_cookie(cookie_value)

    if not session_id:
        # Generate and set a session cookie containing a guest session ID if not present.
        session_id = _new_guest_id()
        cookie_value = _make_session(session_id)
        is_prod = os.environ.get("ENV") == "prod"
        response.set_cookie(
            SESSION_COOKIE_NAME,
            value=cookie_value,
            max_age=MAX_AGE,
            httponly=True,
            secure=is_prod,
            samesite="lax",
            path="/",
        )
    return SessionResponse(session_id=session_id)


def get_session_id_from_ws(ws: WebSocket) -> str | None:
    cookie_value = ws.cookies.get(SESSION_COOKIE_NAME)
    return _session_id_from_cookie(cookie_value)


def _session_id_from_cookie(cookie_value: str | None) -> str | None:
    if not cookie_value:
        return None
    try:
        return _read_session(cookie_value)["session_id"]
    except BadSignature:
        return None


def _new_guest_id():
    return "guest_" + secrets.token_urlsafe(16)


def _read_session(value: str) -> dict:
    return signer.loads(value)


def _make_session(session_id: str) -> str:
    return signer.dumps({"session_id": session_id, "iat": int(time.time())})
