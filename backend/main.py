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
from websocket.endpoint import router as ws_router



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


def create_app() -> FastAPI:
    app = FastAPI()
    app.state.state = AppState()
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


app = create_app()
