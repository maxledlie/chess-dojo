from pydantic import BaseModel
from enum import Enum


class MessageType(str, Enum):
    GameRequest = "game_request"
    GameBegin = "game_begin"


class Message(BaseModel):
    type: MessageType
