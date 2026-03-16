from models import Game, Color, Resign
from websocket.endpoint import consume
from websocket.models import (
    ChatReceiveMsg,
    GameCompleteMsg,
    Message,
    MoveSendMsg,
    MoveResultMsg,
    GameResignMsg,
    ChatSendMsg,
)
from tests.conftest import make_state, connect_session, drain


WHITE = "session-white"
BLACK = "session-black"
GAME_ID = "game-1"


async def setup_game(state, starting_fen: str | None = None):
    """Create a game and connect both players. Returns (white_queue, black_queue)."""
    if starting_fen is not None:
        game = Game(white_id=WHITE, black_id=BLACK, starting_fen=starting_fen)
    else:
        game = Game(white_id=WHITE, black_id=BLACK)
    await state.game_store.create_game(GAME_ID, game)
    white_q = await connect_session(state, WHITE)
    black_q = await connect_session(state, BLACK)
    return white_q, black_q


# ---------------------------------------------------------------------------
# Move handling
# ---------------------------------------------------------------------------


async def test_valid_move_accepted_and_broadcast():
    state = make_state()
    white_q, black_q = await setup_game(state)

    await consume(state, WHITE, Message(data=MoveSendMsg(game_id=GAME_ID, move="e4")))

    game = await state.game_store.get_game(GAME_ID)
    assert game is not None
    assert game.moves == ["e4"]

    white_msgs = drain(white_q)
    black_msgs = drain(black_q)
    assert len(white_msgs) == 1
    assert isinstance(white_msgs[0], MoveResultMsg)
    assert white_msgs[0].accepted is True
    assert white_msgs[0].move == "e4"

    assert len(black_msgs) == 1
    assert isinstance(black_msgs[0], MoveResultMsg)
    assert black_msgs[0].accepted is True


async def test_illegal_move_rejected():
    state = make_state()
    white_q, black_q = await setup_game(state)

    await consume(state, WHITE, Message(data=MoveSendMsg(game_id=GAME_ID, move="e5")))

    game = await state.game_store.get_game(GAME_ID)
    assert game is not None
    assert game.moves == []

    white_msgs = drain(white_q)
    black_msgs = drain(black_q)
    assert len(white_msgs) == 1
    assert isinstance(white_msgs[0], MoveResultMsg)
    assert white_msgs[0].accepted is False
    assert len(black_msgs) == 0


async def test_move_by_wrong_color_rejected():
    """Black cannot move on White's turn."""
    state = make_state()
    white_q, black_q = await setup_game(state)

    await consume(state, BLACK, Message(data=MoveSendMsg(game_id=GAME_ID, move="e5")))

    game = await state.game_store.get_game(GAME_ID)
    assert game is not None
    assert game.moves == []

    assert len(drain(white_q)) == 0
    black_msgs = drain(black_q)
    assert len(black_msgs) == 1
    assert isinstance(black_msgs[0], MoveResultMsg)
    assert black_msgs[0].accepted is False


async def test_move_after_game_over_rejected():
    """Once a game has a result, further moves should be rejected."""
    state = make_state()
    white_q, black_q = await setup_game(state)

    # Manually end the game
    await state.game_store.end_by_resignation(GAME_ID, Color.White)

    await consume(state, WHITE, Message(data=MoveSendMsg(game_id=GAME_ID, move="e4")))

    game = await state.game_store.get_game(GAME_ID)
    assert game is not None
    assert game.moves == []

    white_msgs = drain(white_q)
    assert len(white_msgs) == 1
    assert isinstance(white_msgs[0], MoveResultMsg)
    assert white_msgs[0].accepted is False


async def test_move_nonexistent_game_ignored():
    state = make_state()
    sender_q = await connect_session(state, WHITE)

    await consume(state, WHITE, Message(data=MoveSendMsg(game_id="no-such-game", move="e4")))

    assert len(drain(sender_q)) == 0


async def test_move_by_non_participant_ignored():
    state = make_state()
    white_q, black_q = await setup_game(state)
    outsider_q = await connect_session(state, "outsider")

    await consume(state, "outsider", Message(data=MoveSendMsg(game_id=GAME_ID, move="e4")))

    game = await state.game_store.get_game(GAME_ID)
    assert game is not None
    assert game.moves == []
    assert len(drain(white_q)) == 0
    assert len(drain(black_q)) == 0


# ---------------------------------------------------------------------------
# Resignation
# ---------------------------------------------------------------------------


async def test_resign_sets_result_and_broadcasts():
    state = make_state()
    white_q, black_q = await setup_game(state)

    await consume(state, WHITE, Message(data=GameResignMsg(game_id=GAME_ID)))

    game = await state.game_store.get_game(GAME_ID)
    assert game is not None
    assert isinstance(game.result, Resign)
    assert game.result.winner == Color.Black  # White resigned → Black wins

    white_msgs = drain(white_q)
    black_msgs = drain(black_q)
    assert len(white_msgs) == 1
    assert isinstance(white_msgs[0], GameCompleteMsg)
    assert white_msgs[0].result == "black"

    assert len(black_msgs) == 1
    assert isinstance(black_msgs[0], GameCompleteMsg)
    assert black_msgs[0].result == "black"


async def test_resign_by_black():
    state = make_state()
    white_q, black_q = await setup_game(state)

    await consume(state, BLACK, Message(data=GameResignMsg(game_id=GAME_ID)))

    game = await state.game_store.get_game(GAME_ID)
    assert game is not None
    assert isinstance(game.result, Resign)
    assert game.result.winner == Color.White

    white_msg = drain(white_q)[0]
    black_msg = drain(black_q)[0]
    assert isinstance(white_msg, GameCompleteMsg)
    assert isinstance(black_msg, GameCompleteMsg)
    assert white_msg.result == "white"
    assert black_msg.result == "white"


async def test_resign_by_non_participant_ignored():
    state = make_state()
    white_q, black_q = await setup_game(state)

    await consume(state, "outsider", Message(data=GameResignMsg(game_id=GAME_ID)))

    game = await state.game_store.get_game(GAME_ID)
    assert game is not None
    assert game.result is None
    assert len(drain(white_q)) == 0
    assert len(drain(black_q)) == 0


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


async def test_chat_delivered_to_opponent_only():
    state = make_state()
    white_q, black_q = await setup_game(state)

    await consume(state, WHITE, Message(data=ChatSendMsg(game_id=GAME_ID, message="hello")))

    game = await state.game_store.get_game(GAME_ID)
    assert game is not None
    assert len(game.chat) == 1
    assert game.chat[0].content == "hello"
    assert game.chat[0].player_id == WHITE

    assert len(drain(white_q)) == 0  # sender does NOT get echo

    black_msgs = drain(black_q)
    assert len(black_msgs) == 1
    assert isinstance(black_msgs[0], ChatReceiveMsg)
    assert black_msgs[0].message == "hello"


async def test_chat_by_non_participant_ignored():
    state = make_state()
    white_q, black_q = await setup_game(state)

    await consume(state, "outsider", Message(data=ChatSendMsg(game_id=GAME_ID, message="hi")))

    game = await state.game_store.get_game(GAME_ID)
    assert game is not None
    assert len(game.chat) == 0
    assert len(drain(white_q)) == 0
    assert len(drain(black_q)) == 0
