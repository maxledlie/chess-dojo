import { createFileRoute } from "@tanstack/react-router";
import { Input } from "@base-ui/react/input";
import { Chessboard } from "react-chessboard";
import "./$gameId.css";
import { useEffect, useState } from "react";
import { Button } from "@base-ui/react/button";
import { Flag, Undo, X } from "lucide-react";
import { useGetGame } from "../queries/games";
import { useWebSocket } from "../components/WebSocketProvider";

export const Route = createFileRoute("/$gameId")({
    component: GamePage,
});

interface ChatReceiveData {
    msg_type: "chat_receive";
    game_id: string;
    message: string;
}

interface GameResult {
    winner: "black" | "white" | "draw";
    termination:
        | "abandonment"
        | "resignation"
        | "checkmate"
        | "timeout"
        | "stalemate"
        | "agreement"
        | "repetition";
}

function GamePage() {
    const { gameId } = Route.useParams();
    const { data: game, isPending } = useGetGame(gameId);

    const [messages, setMessages] = useState<string[]>([]);

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
            }
        }
    }, [lastMessage]);

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
            <BoardPanel />
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

function BoardPanel() {
    return (
        <div className="board-panel">
            <Chessboard />
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
