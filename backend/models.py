from typing import Literal, Union
from pydantic import BaseModel, Field

# ------------------------
# HTTP
# ------------------------


class SessionResponse(BaseModel):
    session_id: str


# ------------------------
# WEBSOCKET
# ------------------------


class GameRequestMsg(BaseModel):
    msg_type: Literal["game_request"] = "game_request"


class GameBeginMsg(BaseModel):
    msg_type: Literal["game_begin"] = "game_begin"
    you_are_white: bool
    game_id: str


class GameResignMsg(BaseModel):
    msg_type: Literal["game_resign"] = "game_resign"
    game_id: str


class GameCompleteMsg(BaseModel):
    msg_type: Literal["game_complete"] = "game_complete"
    game_id: str
    result: Literal["white", "black", "draw"]


MessagePayload = Union[GameRequestMsg, GameBeginMsg, GameResignMsg, GameCompleteMsg]


class Message(BaseModel):
    data: MessagePayload = Field(discriminator="msg_type")
