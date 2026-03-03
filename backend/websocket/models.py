from datetime import datetime
from typing import Literal, Union

from pydantic import BaseModel, Field


class GameRequestMsg(BaseModel):
    msg_type: Literal["game_request"] = "game_request"
    time_control: str  # TODO: Validation


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


class ChatSendMsg(BaseModel):
    msg_type: Literal["chat_send"] = "chat_send"
    game_id: str
    message: str = Field(min_length=1, max_length=512)


class ChatReceiveMsg(BaseModel):
    msg_type: Literal["chat_receive"] = "chat_receive"
    message: str
    timestamp: datetime


class MoveSendMsg(BaseModel):
    msg_type: Literal["move_send"] = "move_send"
    game_id: str
    move: str  # SAN string, e.g. "e4", "Nf3", "O-O"


class MoveResultMsg(BaseModel):
    msg_type: Literal["move_result"] = "move_result"
    game_id: str
    accepted: bool
    move: str | None = None    # canonical SAN if accepted
    reason: str | None = None  # rejection reason if not accepted


MessagePayload = Union[
    GameRequestMsg,
    GameBeginMsg,
    GameResignMsg,
    GameCompleteMsg,
    ChatSendMsg,
    ChatReceiveMsg,
    MoveSendMsg,
    MoveResultMsg,
]


class Message(BaseModel):
    data: MessagePayload = Field(discriminator="msg_type")
