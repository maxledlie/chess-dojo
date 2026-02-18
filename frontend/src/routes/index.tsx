import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";

export const Route = createFileRoute("/")({
    component: Index,
});

interface GameBeginData {
    msg_type: "game_begin";
    you_are_white: boolean;
    game_id: string;
}

type GameResult = "white" | "black" | "draw" | null;

function Index() {
    const [ws, setWs] = useState<WebSocket | null>(null);
    const [isWaiting, setIsWaiting] = useState<boolean>(false);

    const navigate = useNavigate({ from: "/" });

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
            case "game_begin": {
                const data: GameBeginData = msg;
                navigate({ to: "/$gameId", params: { gameId: data.game_id } });
                break;
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
