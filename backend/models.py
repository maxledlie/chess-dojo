from typing import Literal, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class SessionResponse(BaseModel):
    session_id: str


ChatMessageContent = Field(min_length=1, max_length=200)


class ChatMessage(BaseModel):
    player_id: str
    timestamp: datetime
    content: str = ChatMessageContent


class Color(str, Enum):
    White = "white"
    Black = "black"


class ClockFlag(BaseModel):
    winner: Color
    result_type: Literal["clock_flag"] = "clock_flag"


class Stalemate(BaseModel):
    result_type: Literal["stalemate"] = "stalemate"


class Resign(BaseModel):
    winner: Color
    result_type: Literal["resign"] = "resign"


class Mate(BaseModel):
    winner: Color
    result_type: Literal["mate"] = "mate"


class DrawReason(str, Enum):
    Repetition = "repetition"
    Agreement = "agreement"
    InsufficientMaterial = "insufficient_material"
    SeventyFiveMove = "seventy_five_move"


class Draw(BaseModel):
    result_type: Literal["draw"] = "draw"
    reason: DrawReason


GameResult = Union[Mate, Resign, Stalemate, ClockFlag, Draw]

STANDARD_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class Game(BaseModel):
    white_id: str
    black_id: str
    moves: list[str] = []
    chat: list[ChatMessage] = []
    result: GameResult | None = Field(default=None, discriminator="result_type")
    starting_fen: str = STANDARD_FEN
