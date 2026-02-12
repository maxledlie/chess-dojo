import { useState, useEffect, type SubmitEvent, type ChangeEvent } from "react";
import "./App.css";

function App() {
    const [history, setHistory] = useState<string[]>([]);
    const [message, setMessage] = useState("");
    const [ws, setWs] = useState<WebSocket | null>(null);

    useEffect(() => {
        const scheme = window.location.protocol === "https:" ? "wss" : "ws";
        const wsUrl = `${scheme}://${window.location.host}/ws`;
        const ws = new WebSocket(wsUrl);
        ws.onmessage = handleMessageReceived;
        setWs(ws);
    }, []);

    function handleMessageReceived(ev: MessageEvent<any>) {
        setHistory((last) => [...last, ev.data]);
    }

    function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        if (!ws) {
            console.error("Web socket not established!");
            return;
        }

        ws.send(message);
        setMessage("");
        event.preventDefault();
    }

    function handleChange(event: ChangeEvent<HTMLInputElement>) {
        setMessage(event.target.value);
    }

    return (
        <>
            <h1>Websocket Demo</h1>
            <form action={""} onSubmit={handleSubmit}>
                <input
                    type="text"
                    value={message}
                    onChange={handleChange}
                    placeholder="Send a message..."
                />
                <button type="submit">Submit</button>
            </form>
            <ul>
                {history.map((m) => (
                    <p>{m}</p>
                ))}
            </ul>
        </>
    );
}

export default App;
