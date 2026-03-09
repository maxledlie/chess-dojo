import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Input } from "@base-ui/react/input";
import { Chessboard } from "react-chessboard";
import type {
    PieceDropHandlerArgs,
    PieceHandlerArgs,
    SquareHandlerArgs,
} from "react-chessboard";
import "./$gameId.css";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Button } from "@base-ui/react/button";
import { Flag, Undo, X } from "lucide-react";
import { useGetGame } from "../queries/games";
import { useWebSocket } from "../components/WebSocketProvider";
import { Chess, Move, type Color, type Piece, type Square } from "chess.js";
import type { Game } from "../client";

export const Route = createFileRoute("/$gameId")({
    component: GamePage,
});

interface ChatReceiveData {
    msg_type: "chat_receive";
    game_id: string;
    message: string;
}

interface MoveResultData {
    msg_type: "move_result";
    game_id: string;
    accepted: boolean;
    move?: string;
    reason?: string;
}

interface GameBeginData {
    msg_type: "game_begin";
    game_id: string;
    you_are_white: boolean;
}

function GamePage() {
    const { gameId } = Route.useParams();
    const [isWhite, setIsWhite] = useState(
        () => sessionStorage.getItem(`cress:game-color:${gameId}`) === "true",
    );
    const { data: game, isPending, refetch: refetchGame } = useGetGame(gameId);

    const navigate = useNavigate({ from: "/$gameId" });
    const [isSearchingOpponent, setIsSearchingOpponent] = useState(false);

    const [messages, setMessages] = useState<
        { text: string; isOwn: boolean }[]
    >([]);

    const [selectedSquare, setSelectedSquare] = useState<Square | null>(null);
    const [prevMoveFrom, setPrevMoveFrom] = useState<Square | null>(null);
    const [prevMoveTo, setPrevMoveTo] = useState<Square | null>(null);
    const [optionSquares, setOptionSquares] = useState<Square[]>([]);

    const chessRef = useRef(new Chess());
    const [fen, setFen] = useState(chessRef.current.fen());
    // Tracks the SAN of a move we sent and are awaiting confirmation for.
    const pendingMoveRef = useRef<string | null>(null);
    // Ensures we initialise from the server snapshot only once.
    const initializedRef = useRef(false);

    const { sendMessage, lastMessage } = useWebSocket();

    // Reset board state whenever we navigate to a new game.
    useEffect(() => {
        const chess = new Chess();
        chessRef.current = chess;
        setFen(chess.fen());
        setPrevMoveFrom(null);
        setPrevMoveTo(null);
        setSelectedSquare(null);
        setOptionSquares([]);
        setIsSearchingOpponent(false);
        pendingMoveRef.current = null;
        initializedRef.current = false;
    }, [gameId]);

    // Initialise board and chat from the server snapshot on first load.
    useEffect(() => {
        if (initializedRef.current || !game) return;
        initializedRef.current = true;

        const chess = new Chess();
        for (const san of game.moves ?? []) {
            try {
                chess.move(san);
            } catch {}
        }
        chessRef.current = chess;
        setFen(chess.fen());

        const mySessionId = sessionStorage.getItem("cress:session-id");
        setMessages(
            (game.chat ?? []).map((c) => ({
                text: c.content,
                isOwn: c.player_id === mySessionId,
            })),
        );
    }, [game]);

    // Handle messages
    useEffect(() => {
        if (!lastMessage) {
            return;
        }

        const msg = JSON.parse(lastMessage.data).data;
        switch (msg.msg_type) {
            case "chat_receive": {
                const data: ChatReceiveData = msg;
                setMessages((messages) => [
                    ...messages,
                    { text: data.message, isOwn: false },
                ]);
                break;
            }
            case "game_complete": {
                refetchGame();
                break;
            }
            case "game_begin": {
                const data: GameBeginData = msg;
                sessionStorage.setItem(
                    `cress:game-color:${data.game_id}`,
                    String(data.you_are_white),
                );
                setIsWhite(data.you_are_white);
                navigate({
                    to: "/$gameId",
                    params: { gameId: data.game_id },
                });
                break;
            }
            case "move_result": {
                const data: MoveResultData = msg;
                if (data.accepted && data.move) {
                    if (pendingMoveRef.current !== null) {
                        // Our own move was accepted — already applied optimistically, nothing to do.
                        pendingMoveRef.current = null;
                    } else {
                        // Opponent's move — apply it now.
                        try {
                            const move = chessRef.current.move(data.move);
                            setPrevMoveFrom(move.from);
                            setPrevMoveTo(move.to);
                        } catch {}
                        setFen(chessRef.current.fen());
                    }
                } else if (!data.accepted) {
                    // Our move was rejected — revert the optimistic update.
                    pendingMoveRef.current = null;
                    chessRef.current.undo();
                    setFen(chessRef.current.fen());
                }
                break;
            }
        }
    }, [lastMessage]);

    /**
     * @param square
     * @returns The piece that would be selected by clicking or starting a drag on that square, or null if no
     * piece would be selected.
     */
    function checkSelectable(square: Square): Piece | null {
        const chess = chessRef.current;
        const piece = chess.get(square);
        if (!piece) {
            return null;
        }
        const playerColor = isWhite ? "w" : "b";
        return piece.color === playerColor ? piece : null;
    }

    /**
     * @param square
     * @returns An array of moves playable starting from that square
     */
    function selectSquare(square: Square): Move[] {
        const chess = chessRef.current;
        const moves = chess.moves({ square, verbose: true });
        const options = moves.map((m) => m.to);
        setSelectedSquare(square);
        setOptionSquares(options);
        return moves;
    }

    function deselectSquare() {
        setSelectedSquare(null);
        setOptionSquares([]);
    }

    function handleSquareClick({ square }: SquareHandlerArgs) {
        const sq = square as Square;

        // No square selected: select the square if allowed.
        if (!selectedSquare) {
            if (checkSelectable(sq)) {
                selectSquare(sq);
            }
            return;
        }

        // A "from" square is already selected. Try to move the piece to the newly selected square.
        // If this is not a valid move, either select the new square, or clear selection.
        const move = localApplyMove(selectedSquare, sq);
        if (move) {
            commitMove(move);
        } else {
            if (checkSelectable(sq)) {
                selectSquare(sq);
            } else {
                deselectSquare();
            }
        }
    }

    function localApplyMove(from: Square, to: Square): Move | null {
        const chess = chessRef.current;
        try {
            return chess.move({
                from,
                to,
                promotion: "q",
            });
        } catch {
            return null; // illegal locally — snap back
        }
    }

    function handlePieceDrag({ square }: PieceHandlerArgs) {
        const sq = square as Square;
        if (checkSelectable(sq)) {
            selectSquare(sq);
        } else {
            deselectSquare();
        }
    }

    function handlePieceDrop({
        sourceSquare,
        targetSquare,
    }: PieceDropHandlerArgs): boolean {
        if (!targetSquare) return false;

        const move = localApplyMove(
            sourceSquare as Square,
            targetSquare as Square,
        );
        if (!move) {
            return false;
        }
        commitMove(move);
        return true;
    }

    function commitMove(move: Move) {
        pendingMoveRef.current = move.san;
        setFen(chessRef.current.fen());
        sendMessage({
            msg_type: "move_send",
            game_id: gameId,
            move: move.san,
        });
        setPrevMoveFrom(move.from);
        setPrevMoveTo(move.to);
        deselectSquare();
    }

    function findCheckedSquares(): Square[] {
        // Unless we're playing some variant, there should only be one checked square.
        // But since it's easy to make this generic, we might as well.
        const chess = chessRef.current;
        const ret: Square[] = [];
        for (const color of ["w", "b"]) {
            const otherColor = color === "w" ? "b" : "w";
            const kingSquares = chess.findPiece({
                color: color as Color,
                type: "k",
            });
            for (const square of kingSquares) {
                if (chess.isAttacked(square, otherColor)) {
                    ret.push(square);
                }
            }
        }
        return ret;
    }

    if (isPending) {
        return <></>;
    }

    if (!game) {
        return (
            <div
                style={{
                    height: "90vh",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "center",
                    alignItems: "center",
                }}
            >
                <div>We can't find what you're looking for...</div>
                <div style={{ fontSize: 80 }}>!?</div>
            </div>
        );
    }

    const checkedSquares = findCheckedSquares();

    // Set square styles
    const selectionColor = "rgba(52, 120, 49, 0.4)";
    const selectionStyle = { backgroundColor: selectionColor };
    const previousMoveStyle = { backgroundColor: "rgba(255, 255, 0, 0.4)" };
    const optionStyle = {
        background: `radial-gradient(circle, ${selectionColor} 25%, transparent 25%)`,
    };
    const checkStyle = {
        background: `radial-gradient(circle, rgb(255, 0, 0) 25%, transparent 90%)`,
    };

    const squareStyles: Record<string, CSSProperties> = {
        [selectedSquare as string]: selectionStyle,
        [prevMoveFrom as string]: previousMoveStyle,
        [prevMoveTo as string]: previousMoveStyle,
    };
    for (const option of optionSquares) {
        squareStyles[option as string] = optionStyle;
    }
    for (const square of checkedSquares) {
        squareStyles[square as string] = checkStyle;
    }

    function canDragPiece({ square }: PieceHandlerArgs) {
        return !!checkSelectable(square as Square);
    }

    return (
        <div className="game-layout">
            <ChatPanel
                messages={messages}
                sendMessage={(m) => {
                    sendMessage({
                        msg_type: "chat_send",
                        game_id: gameId,
                        message: m,
                    });
                    setMessages((messages) => [
                        ...messages,
                        { text: m, isOwn: true },
                    ]);
                }}
            />
            <div className="board-panel">
                <Chessboard
                    options={{
                        position: fen,
                        boardOrientation: isWhite ? "white" : "black",
                        squareStyles,
                        canDragPiece,
                        onSquareClick: handleSquareClick,
                        onPieceDrag: handlePieceDrag,
                        onPieceDrop: handlePieceDrop,
                    }}
                />
            </div>
            <MovesPanel
                game={game}
                isSearchingOpponent={isSearchingOpponent}
                onFindNewOpponent={() => {
                    sendMessage({
                        msg_type: "game_request",
                        time_control: "blitz_5p0",
                    });
                    setIsSearchingOpponent(true);
                }}
            />
        </div>
    );
}

interface ChatPanelProps {
    messages: { text: string; isOwn: boolean }[];
    sendMessage: (m: string) => void;
}
function ChatPanel({ messages, sendMessage }: ChatPanelProps) {
    const [inputValue, setInputValue] = useState("");

    function handleChatSubmit() {
        if (inputValue.trim()) {
            sendMessage(inputValue);
            setInputValue("");
        }
    }

    function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
        if (event.key === "Enter") {
            event.preventDefault();
            handleChatSubmit();
        }
    }

    return (
        <div className="chat-panel">
            <div className="chat-messages">
                {messages.map((m, i) => (
                    <div
                        key={i}
                        className={`chat-message ${m.isOwn ? "chat-message--own" : "chat-message--opponent"}`}
                    >
                        {m.text}
                    </div>
                ))}
            </div>
            <Input
                placeholder="Please be nice in the chat!"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
            />
        </div>
    );
}

function resultShorthand(result: NonNullable<Game["result"]>): string {
    switch (result.result_type) {
        case "clock_flag":
        case "mate":
        case "resign":
            return result.winner === "white" ? "1-0" : "0-1";
        case "draw":
        case "stalemate":
            return "½-½";
    }
}

function resultLonghand(result: NonNullable<Game["result"]>): string {
    switch (result.result_type) {
        case "stalemate":
            return "Stalemate";
        case "draw":
            switch (result.reason) {
                case "agreement":
                    return "Draw by mututal agreement";
                case "seventy_five_move":
                    return "Draw by 75-move rule";
                case "insufficient_material":
                    return "Insufficient material • Draw";
                case "repetition":
                    return "Threefold repetition • Draw";
            }
    }

    const winner = result.winner === "white" ? "White" : "Black";
    const loser = result.winner === "white" ? "Black" : "White";

    switch (result.result_type) {
        case "clock_flag":
            return `${loser} time out • ${winner} is victorious`;
        case "mate":
            return `Checkmate • ${winner} is victorious`;
        case "resign":
            return `${loser} resigned • ${winner} is victorious`;
    }
}

interface MovePanelProps {
    game: Game;
    isSearchingOpponent: boolean;
    onFindNewOpponent: () => void;
}

const MovesPanel = ({
    game,
    isSearchingOpponent,
    onFindNewOpponent,
}: MovePanelProps) => {
    return (
        <div className="move-panel">
            {game.result && (
                <>
                    <div className="results-panel">
                        <b>{resultShorthand(game.result)}</b>
                        <em>{resultLonghand(game.result)}</em>
                    </div>
                    {isSearchingOpponent ? (
                        <p style={{ textAlign: "center" }}>Searching...</p>
                    ) : (
                        <Button
                            className="postgame-button"
                            onClick={onFindNewOpponent}
                        >
                            NEW OPPONENT
                        </Button>
                    )}
                </>
            )}
            {!game.result && <ActionButtons />}
        </div>
    );
};

const ActionButtons = ({}) => {
    const { sendMessage } = useWebSocket();
    const [resignPending, setResignPending] = useState(false);
    const { gameId } = Route.useParams();

    function resignFirstClick() {
        setResignPending(true);
        setTimeout(() => {
            setResignPending(false);
        }, 3000);
    }

    return (
        <div className="game-actions">
            <Button
                title="Propose Takeback"
                onClick={() => {
                    sendMessage({
                        msg_type: "game_takeback_request",
                        game_id: gameId,
                    });
                }}
            >
                <Undo />
            </Button>
            <Button
                style={{ fontSize: 24 }}
                title="Propose Draw"
                onClick={() => {
                    sendMessage({ msg_type: "game_draw", game_id: gameId });
                }}
            >
                ½
            </Button>
            <Button
                title="Resign"
                className={resignPending ? "resign-button-active" : ""}
                onClick={() => {
                    if (resignPending) {
                        sendMessage({
                            msg_type: "game_resign",
                            game_id: gameId,
                        });
                    } else {
                        resignFirstClick();
                    }
                }}
            >
                <Flag />
            </Button>
            <Button
                style={{ visibility: resignPending ? "visible" : "hidden" }}
                title="Cancel"
                id="cancel-button"
                onClick={() => setResignPending(false)}
            >
                <X />
            </Button>
        </div>
    );
};
