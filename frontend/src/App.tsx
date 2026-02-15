import { useState, useEffect } from "react";
import "./App.css";

type State = "idle" | "lobby" | "playing";

interface GameBeginData {
    you_are_white: boolean;
}

function App() {
    const [ws, setWs] = useState<WebSocket | null>(null);
    const [state, setState] = useState<State>("idle");
    const [isWhite, setIsWhite] = useState<boolean>(false);

    useEffect(() => {
        const scheme = window.location.protocol === "https:" ? "wss" : "ws";
        const wsUrl = `${scheme}://${window.location.host}/ws`;
        const ws = new WebSocket(wsUrl);
        ws.onmessage = handleMessageReceived;
        setWs(ws);
    }, []);

    function handleMessageReceived(ev: MessageEvent<any>) {
        console.log("Message received", ev, ev.data);
        const msg = JSON.parse(ev.data);
        switch (msg.type) {
            case "game_begin": {
                const data: GameBeginData = msg.data;
                setState("playing");
                setIsWhite(data.you_are_white);
            }
        }
    }

    function sendMessage(msg: any) {
        if (!ws) {
            console.error("Web socket not established!");
            return;
        }
        ws.send(JSON.stringify(msg));
    }

    return (
        <>
            <h1>Minimalist Chess</h1>
            {state === "playing" && (
                <>
                    <p>You are {isWhite ? "white" : "black"}</p>
                    <button
                        onClick={() => sendMessage({ type: "game_resign" })}
                    >
                        Resign
                    </button>
                </>
            )}
            {state === "lobby" && <p>Waiting for a game...</p>}
            {state === "idle" && (
                <button
                    onClick={() => {
                        sendMessage({ type: "game_request" });
                        setState("lobby");
                    }}
                >
                    Play!
                </button>
            )}
        </>
    );
}

export default App;
