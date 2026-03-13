from datetime import datetime
import logging
from typing import Literal, Union

from pydantic import BaseModel, Field

from models import ChatMessageContent


# -------------------
# Lobby
# -------------------


class PingMsg(BaseModel):
    """Sent from each connected client to the server every 2500ms to confirm connection still
    active and measure latency."""

    msg_type: Literal["ping"] = "ping"


class PongMsg(BaseModel):
    """Sent from the server to the client on receipt of a ping message.
    Includes the number of active players and ongoing games."""

    msg_type: Literal["pong"] = "pong"
    players: int
    games: int


class GameRequestMsg(BaseModel):
    """Send from client to server when player requests a lobby game."""

    msg_type: Literal["game_request"] = "game_request"
    time_control: str  # TODO: Validation


class GameBeginMsg(BaseModel):
    """Send from server to client when a player's game request has been fulfilled.
    Should trigger the client to navigate to the URL for the created game ID."""

    msg_type: Literal["game_begin"] = "game_begin"
    you_are_white: bool
    game_id: str


# --------------------
# Gameplay
# --------------------


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
    message: str = ChatMessageContent


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
    move: str | None = None  # canonical SAN if accepted
    reason: str | None = None  # rejection reason if not accepted


MessagePayload = Union[
    PingMsg,
    PongMsg,
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


def msg_log_level(msg: MessagePayload) -> int:
    match msg.msg_type:
        case "ping" | "pong":
            return logging.DEBUG
        case _:
            return logging.INFO
