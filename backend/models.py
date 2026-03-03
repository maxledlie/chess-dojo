from typing import Literal
from pydantic import BaseModel
from datetime import datetime


class SessionResponse(BaseModel):
    session_id: str


class ChatMessage(BaseModel):
    player_id: str
    timestamp: datetime
    content: str


GameResult = Literal["white", "black", "draw"]

GameTermination = Literal[
    # One side wins
    "checkmate",
    "resignation",
    "timeout",
    "abandonment",
    # Draw
    "stalemate",
    "repetition",
    "fifty_move",
    "agreement",
    "insufficient_material",
]


class Game(BaseModel):
    white_id: str
    black_id: str
    moves: list[str] = []
    chat: list[ChatMessage] = []
    status: Literal["active", "complete"] = "active"
    result: GameResult | None = None
    termination: GameTermination | None = None
