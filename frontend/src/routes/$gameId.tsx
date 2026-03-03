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
    const { data: game, isPending } = useGetGame(gameId);

    const [messages, setMessages] = useState<string[]>([]);

    const chessRef = useRef(new Chess());
    const [fen, setFen] = useState(chessRef.current.fen());
    // Tracks the SAN of a move we sent and are awaiting confirmation for.
    const pendingMoveRef = useRef<string | null>(null);

    const { sendMessage, lastMessage } = useWebSocket();

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
                        try { chessRef.current.move(data.move); } catch {}
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

    function handleDrop({ sourceSquare, targetSquare }: PieceDropHandlerArgs): boolean {
        if (!targetSquare) return false;
        const chess = chessRef.current;
        let result;
        try {
            result = chess.move({ from: sourceSquare, to: targetSquare, promotion: "q" });
        } catch {
            return false;  // illegal locally — snap back
        }
        if (!result) return false;

        pendingMoveRef.current = result.san;
        setFen(chess.fen());
        sendMessage({ msg_type: "move_send", game_id: gameId, move: result.san });
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
            <MovesPanel />
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

const MovesPanel = ({}) => {
    return (
        <div className="move-panel">
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
