import { createFileRoute } from "@tanstack/react-router";
import { Input } from "@base-ui/react/input";
import { Chessboard } from "react-chessboard";
import "./$gameId.css";
import { useEffect, useState } from "react";

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
    const [ws, setWs] = useState<WebSocket | null>(null);
    const [messages, setMessages] = useState<string[]>([]);

    useEffect(() => {
        const scheme = window.location.protocol === "https:" ? "wss" : "ws";
        const wsUrl = `${scheme}://${window.location.host}/ws`;
        const ws = new WebSocket(wsUrl);
        ws.onmessage = handleMessageReceived;
        setWs(ws);
    }, []);

    function handleMessageReceived(ev: MessageEvent<any>) {
        console.log("Message received", ev, ev.data);
        const msg = JSON.parse(ev.data).data;
        switch (msg.msg_type) {
            case "chat_receive": {
                const data: ChatReceiveData = msg;
                setMessages((messages) => [...messages, data.message]);
            }
        }
    }

    function sendMessage(msg: any) {
        if (!ws) {
            console.error("Web socket not established!");
            return;
        }
        ws.send(JSON.stringify({ data: msg }));
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
                placeholder="Please be nice!"
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
    return <div className="move-panel"></div>;
}
