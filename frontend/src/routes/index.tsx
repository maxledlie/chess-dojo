import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

export const Route = createFileRoute("/")({
    component: Index,
});

type State = "idle" | "lobby" | "playing";

interface GameBeginData {
    msg_type: "game_begin";
    you_are_white: boolean;
    game_id: string;
}

interface GameCompleteData {
    msg_type: "game_complete";
    game_id: string;
    result: GameResult;
}

type GameResult = "white" | "black" | "draw" | null;

function Index() {
    const [ws, setWs] = useState<WebSocket | null>(null);
    const [state, setState] = useState<State>("idle");
    const [isWhite, setIsWhite] = useState<boolean>(false);
    const [result, setResult] = useState<GameResult>(null);
    const [gameId, setGameId] = useState<string | null>(null);

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
                console.log("game_begin received", data);
                setState("playing");
                setIsWhite(data.you_are_white);
                setGameId(data.game_id);
                break;
            }
            case "game_complete": {
                const data: GameCompleteData = msg;
                setResult(data.result);
                setState("idle");
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

    let resultMessage = "";
    if (result === "white") {
        resultMessage = isWhite ? "You win!" : "You lose!";
    } else if (result === "black") {
        resultMessage = isWhite ? "You lose!" : "You win!";
    } else if (result === "draw") {
        resultMessage = "It's a draw.";
    }

    return (
        <>
            {state === "playing" && (
                <>
                    <p>You have the {isWhite ? "white" : "black"} pieces.</p>
                    <button
                        onClick={() =>
                            sendMessage({
                                msg_type: "game_resign",
                                game_id: gameId,
                            })
                        }
                    >
                        Resign
                    </button>
                </>
            )}
            {state === "lobby" && <p>Waiting for a game...</p>}
            {state === "idle" && (
                <>
                    {resultMessage}
                    <button
                        onClick={() => {
                            sendMessage({ msg_type: "game_request" });
                            setState("lobby");
                        }}
                    >
                        Play!
                    </button>
                </>
            )}
        </>
    );
}
