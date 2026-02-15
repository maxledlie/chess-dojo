from uuid import UUID
from pydantic import BaseModel
from enum import Enum


class MessageType(str, Enum):
    GameRequest = "game_request"
    GameBegin = "game_begin"
    GameResign = "game_resign"
    GameComplete = "game_complete"


class MessageBase(BaseModel):
    type: MessageType


class GameBeginData(BaseModel):
    you_are_white: bool


class GameBeginMessage(MessageBase):
    type: MessageType = MessageType.GameBegin
    data: GameBeginData


class GameCompleteData(BaseModel):
    winner_id: UUID | None


class GameCompleteMessage(MessageBase):
    type: MessageType = MessageType.GameComplete
    data: GameCompleteData
