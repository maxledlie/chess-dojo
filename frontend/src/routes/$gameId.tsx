import { createFileRoute } from "@tanstack/react-router";
import { Input } from "@base-ui/react/input";
import { Chessboard } from "react-chessboard";
import type { PieceDropHandlerArgs } from "react-chessboard";
import "./$gameId.css";
import { useEffect, useRef, useState } from "react";
import { Button } from "@base-ui/react/button";
import { Flag, Undo, X } from "lucide-react";
import { useGetGame } from "../queries/games";
import { useWebSocket } from "../components/WebSocketProvider";
import { Chess } from "chess.js";
import type { Game } from "../client";

export const Route = createFileRoute("/$gameId")({
    validateSearch: (s: Record<string, unknown>) => ({
        color: (s.color as "white" | "black") ?? "white",
    }),
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

function GamePage() {
    const { gameId } = Route.useParams();
    const { color } = Route.useSearch();
    const { data: game, isPending, refetch: refetchGame } = useGetGame(gameId);

    const [messages, setMessages] = useState<string[]>([]);

    const chessRef = useRef(new Chess());
    const [fen, setFen] = useState(chessRef.current.fen());
    // Tracks the SAN of a move we sent and are awaiting confirmation for.
    const pendingMoveRef = useRef<string | null>(null);
    // Ensures we initialise from the server snapshot only once.
    const initializedRef = useRef(false);

    const { sendMessage, lastMessage } = useWebSocket();

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

        setMessages((game.chat ?? []).map((c) => c.content));
    }, [game]);

    // Handle messages
    useEffect(() => {
        if (!lastMessage) {
            return;
        }

        console.log("Message received", lastMessage.data);
        const msg = JSON.parse(lastMessage.data).data;
        switch (msg.msg_type) {
            case "chat_receive": {
                const data: ChatReceiveData = msg;
                setMessages((messages) => [...messages, data.message]);
                break;
            }
            case "game_complete": {
                refetchGame();
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
                            chessRef.current.move(data.move);
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

    function handleDrop({
        sourceSquare,
        targetSquare,
    }: PieceDropHandlerArgs): boolean {
        if (!targetSquare) return false;
        const chess = chessRef.current;
        let result;
        try {
            result = chess.move({
                from: sourceSquare,
                to: targetSquare,
                promotion: "q",
            });
        } catch {
            return false; // illegal locally — snap back
        }
        if (!result) return false;

        pendingMoveRef.current = result.san;
        setFen(chess.fen());
        sendMessage({
            msg_type: "move_send",
            game_id: gameId,
            move: result.san,
        });
        return true;
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
                    setMessages((messages) => [...messages, m]);
                }}
            />
            <BoardPanel fen={fen} color={color} onDrop={handleDrop} />
            <MovesPanel game={game} />
        </div>
    );
}

interface ChatPanelProps {
    messages: string[];
    sendMessage: (m: string) => void;
}
function ChatPanel({ messages, sendMessage }: ChatPanelProps) {
    const [inputValue, setInputValue] = useState("");

    function handleChatSubmit() {
        if (inputValue.trim()) {
            console.log("Sending chat message: ", inputValue);
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
            {messages.map((m, i) => (
                <div key={i}>{m}</div>
            ))}
            <Input
                placeholder="Please be nice in the chat!"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
            />
        </div>
    );
}

interface BoardPanelProps {
    fen: string;
    color: "white" | "black";
    onDrop: (args: PieceDropHandlerArgs) => boolean;
}
function BoardPanel({ fen, color, onDrop }: BoardPanelProps) {
    return (
        <div className="board-panel">
            <Chessboard
                options={{
                    position: fen,
                    boardOrientation: color,
                    onPieceDrop: onDrop,
                }}
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
                    return "Insufficient material · Draw";
                case "repetition":
                    return "Threefold repetition · Draw";
            }
    }

    const winner = result.winner === "white" ? "White" : "Black";
    const loser = result.winner === "white" ? "Black" : "White";

    switch (result.result_type) {
        case "clock_flag":
            return `${loser} time out · ${winner} is victorious`;
        case "mate":
            return `Checkmate · ${winner} is victorious`;
        case "resign":
            return `${loser} resigned · ${winner} is victorious`;
    }
}

interface MovePanelProps {
    game: Game;
}

const MovesPanel = ({ game }: MovePanelProps) => {
    return (
        <div className="move-panel">
            {game.result && (
                <div className="results-panel">
                    <b>{resultShorthand(game.result)}</b>
                    <em>{resultLonghand(game.result)}</em>
                </div>
            )}
            <ActionButtons />
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
