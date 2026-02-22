import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useWebSocket } from "../components/WebSocketProvider";
import { Button } from "@base-ui/react/button";
import "./index.css";

export const Route = createFileRoute("/")({
    component: Index,
});

interface GameBeginData {
    msg_type: "game_begin";
    you_are_white: boolean;
    game_id: string;
}

function Index() {
    const [isWaiting, setIsWaiting] = useState<boolean>(false);
    const navigate = useNavigate({ from: "/" });

    const { status, sendMessage, lastMessage } = useWebSocket();

    useEffect(() => {
        if (!lastMessage) {
            return;
        }

        console.log("Message received", lastMessage.data);
        const msg = JSON.parse(lastMessage.data).data;
        switch (msg.msg_type) {
            case "game_begin": {
                const data: GameBeginData = msg;
                navigate({ to: "/$gameId", params: { gameId: data.game_id } });
                break;
            }
        }
    }, [lastMessage]);

    return (
        <div className="home-layout">
            {isWaiting ? (
                <p>Waiting for a game...</p>
            ) : (
                <Button
                    onClick={() => {
                        sendMessage({ msg_type: "game_request" });
                        setIsWaiting(true);
                    }}
                >
                    Play!
                </Button>
            )}
        </div>
    );
}
