import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
    type ReactNode,
} from "react";

type WSStatus = "idle" | "connecting" | "open" | "closed" | "error";

export type WsLogEntry = {
    direction: "sent" | "received";
    timestamp: Date;
    raw: string;
};

type WebSocketContextValue = {
    status: WSStatus;
    sendMessage: (data: any) => void;
    lastMessage: MessageEvent | null;
    messages: WsLogEntry[];
};

export const WebSocketContext = createContext<WebSocketContextValue | null>(
    null,
);

export interface WebSocketProviderProps {
    url: string;
    children: ReactNode;
}
export default function WebSocketProvider({
    url,
    children,
}: WebSocketProviderProps) {
    // Reference to websocket connection.
    // Note that we use a ref, not React state, so that reconnecting to the websocket will not
    // cause a rerender of the entire tree.
    const wsRef = useRef<WebSocket | null>(null);

    // When disconnected, we try to reconnect after some delay.
    const reconnectTimerRef = useRef<number | null>(null);

    // Store messages in an in-memory queue until socket is open
    const sendQueueRef = useRef<string[]>([]);

    // Track time of last send ping message
    const lastPingTime = useRef<number>(-1);

    const [status, setStatus] = useState<WSStatus>("idle");
    const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);
    const [messages, setMessages] = useState<WsLogEntry[]>([]);
    const [pingMillis, setPingMillis] = useState<number>(0);
    const [playerCount, setPlayerCount] = useState<number>(0);
    const [gameCount, setGameCount] = useState<number>(0);

    const logMessage = useCallback((entry: WsLogEntry) => {
        setMessages((prev) => {
            const next = [...prev, entry];
            return next.length > 200 ? next.slice(next.length - 200) : next;
        });
    }, []);

    function cancelReconnect() {
        if (reconnectTimerRef.current != null) {
            window.clearTimeout(reconnectTimerRef.current);
            reconnectTimerRef.current = null;
        }
    }

    const connect = useCallback(() => {
        // Prevent creation of duplicate web socket connections.
        // For example, without this check, React Strict Mode will create two connections,
        // one for each invocation of the below `useEffect` hook.
        const existing = wsRef.current;
        if (
            existing &&
            (existing.readyState === WebSocket.CONNECTING ||
                existing.readyState === WebSocket.OPEN)
        ) {
            return;
        }

        cancelReconnect(); // Since this function call is taking care of it.
        setStatus("connecting");

        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
            setStatus("open");
            // Flush queued messages
            const q = sendQueueRef.current;
            sendQueueRef.current = [];
            for (const msg of q) {
                ws.send(msg);
            }
        };
        ws.onmessage = (evt) => {
            const payload = JSON.parse(evt.data).data;
            if (payload.msg_type === "pong") {
                const payload = evt.data.data;
                const recvTime = Date.now();
                if (lastPingTime.current > 0) {
                    setPingMillis(recvTime - lastPingTime.current);
                }
                setPlayerCount(payload.player_count);
                setGameCount(payload.game_count);
            } else {
                setLastMessage(evt);
                logMessage({
                    direction: "received",
                    timestamp: new Date(),
                    raw: evt.data,
                });
            }
        };
        ws.onerror = () => setStatus("error");

        ws.onclose = () => {
            setStatus("closed");
            if (wsRef.current === ws) {
                wsRef.current = null;
            }
            // Automatically attempt to reconnect
            setTimeout(() => connect(), 1000);
        };
    }, [url, logMessage]);

    // Initialise websocket connection on page load.
    useEffect(() => {
        connect();

        // Close the connection when app unloads or provider unmounts
        wsRef.current?.close(1000, "Provider unmounted");
        wsRef.current = null;

        // Periodically send `ping` messages to the server
        const pingIntervalId = window.setInterval(() => {
            const sendTime = sendMessage({ msg_type: "ping" });
            lastPingTime.current = sendTime;
        }, 2500);

        return () => {
            window.clearInterval(pingIntervalId);
        };
    }, [connect]);

    /**
     * Sends a provided message to the server over the active websocket, or appends to a local queue
     * if websocket not yet established. Returns the timestamp at which the message was sent or enqueued.
     * @param message The message to send to the server, as a JSON object.
     */
    const sendMessage = useCallback(
        (message: any) => {
            const ws = wsRef.current;

            if (!ws || ws.readyState !== WebSocket.OPEN) {
                const raw = JSON.stringify({ data: message });
                logMessage({ direction: "sent", timestamp: new Date(), raw });
                sendQueueRef.current.push(raw);
                connect();
                return Date.now();
            }

            const raw = JSON.stringify({ data: message });
            logMessage({ direction: "sent", timestamp: new Date(), raw });
            const sendTime = Date.now();
            ws.send(raw);
            return sendTime;
        },
        [connect, logMessage],
    );

    const value = useMemo(
        () => ({
            status,
            sendMessage,
            lastMessage,
            messages,
            pingMillis,
            playerCount,
            gameCount,
        }),
        [
            status,
            sendMessage,
            lastMessage,
            messages,
            pingMillis,
            playerCount,
            gameCount,
        ],
    );

    return (
        <WebSocketContext.Provider value={value}>
            {children}
        </WebSocketContext.Provider>
    );
}

export function useWebSocket() {
    const ctx = useContext(WebSocketContext);
    if (!ctx) {
        throw new Error("useWebSocket must be used within WebSocketProvider");
    }
    return ctx;
}
