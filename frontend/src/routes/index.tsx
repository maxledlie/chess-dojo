import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useWebSocket } from "../components/WebSocketProvider";

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

    const { sendMessage, lastMessage } = useWebSocket();

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
        <>
            {isWaiting ? (
                <p>Waiting for a game...</p>
            ) : (
                <button
                    onClick={() => {
                        sendMessage({ msg_type: "game_request" });
                        setIsWaiting(true);
                    }}
                >
                    Play!
                </button>
            )}
        </>
    );
}
