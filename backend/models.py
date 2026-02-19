from typing import Literal, Union
from pydantic import BaseModel, Field
from datetime import datetime

# ------------------------
# HTTP
# ------------------------


class SessionResponse(BaseModel):
    session_id: str


class ChatMessage(BaseModel):
    player_id: str
    timestamp: datetime
    content: str


class Game(BaseModel):
    white_id: str
    black_id: str
    moves: list[str]
    chat: list[ChatMessage]


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


class ChatSendMsg(BaseModel):
    msg_type: Literal["chat_send"] = "chat_send"
    game_id: str
    message: str = Field(min_length=1, max_length=512)


class ChatReceiveMsg(BaseModel):
    msg_type: Literal["chat_receive"] = "chat_receive"
    message: str
    timestamp: datetime


MessagePayload = Union[
    GameRequestMsg,
    GameBeginMsg,
    GameResignMsg,
    GameCompleteMsg,
    ChatSendMsg,
    ChatReceiveMsg,
]


class Message(BaseModel):
    data: MessagePayload = Field(discriminator="msg_type")
