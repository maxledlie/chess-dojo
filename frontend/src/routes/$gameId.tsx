import { createFileRoute } from "@tanstack/react-router";
import { Input } from "@base-ui/react/input";
import { Chessboard } from "react-chessboard";
import "./$gameId.css";
import { useState } from "react";
import useWebSocket from "../hooks/useWebSocket";
import { Button } from "@base-ui/react/button";
import { Flag, Undo, X } from "lucide-react";

export const Route = createFileRoute("/$gameId")({
    component: GamePage,
});

interface ChatReceiveData {
    msg_type: "chat_receive";
    game_id: string;
    message: string;
}

function GamePage() {
    const { gameId } = Route.useParams();
    const [messages, setMessages] = useState<string[]>([]);

    const handleMessageReceived = (ev: MessageEvent<any>) => {
        console.log("Message received", ev, ev.data);
        const msg = JSON.parse(ev.data).data;
        switch (msg.msg_type) {
            case "chat_receive": {
                const data: ChatReceiveData = msg;
                setMessages((messages) => [...messages, data.message]);
            }
        }
    };

    const { sendMessage } = useWebSocket({
        onMessage: handleMessageReceived,
    });

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

function MovesPanel() {
    const [resignPending, setResignPending] = useState(false);

    const { gameId } = Route.useParams();
    const { sendMessage } = useWebSocket();

    function resignFirstClick() {
        setResignPending(true);
        setTimeout(() => {
            setResignPending(false);
        }, 3000);
    }

    return (
        <div className="move-panel">
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
        </div>
    );
}
