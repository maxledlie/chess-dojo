import asyncio
from contextlib import asynccontextmanager

from fastapi import (
    APIRouter,
    FastAPI,
    HTTPException,
    Request,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware
from models import (
    AppState,
    Game,
    SessionResponse,
)
from http import HTTPStatus
from guest_auth import ensure_guest_session
from matchmaking.consumer import matches_consumer
from shared.redis import redis_client
from websocket.endpoint import router as ws_router
import structlog
import logging

# Configure logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

router = APIRouter()


@router.get(
    "/session",
    description="""If using cress as a guest, call this endpoint before establishing a websocket connection
    to receive a session cookie. This will enable you to rejoin a game in the event of a temporary disconnection.""",
    response_model=SessionResponse,
)
async def ensure_session(request: Request, response: Response):
    return ensure_guest_session(request, response)


@router.get("/{game_id}", operation_id="get_game")
async def get_game(req: Request, game_id: str) -> Game:
    state: AppState = req.app.state.state
    game = state.games.get(game_id, None)
    if game is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, detail=f"No game found with id {game_id}"
        )

    return game


def create_app(api_instance_id: str) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with redis_client() as rc:
            app.state.state = AppState(redis=rc)
            task = asyncio.create_task(
                matches_consumer(app.state.state, api_instance_id)
            )
            try:
                yield
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    app.include_router(ws_router)

    # TODO: Get frontend origin from environment variables for deployment
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app
