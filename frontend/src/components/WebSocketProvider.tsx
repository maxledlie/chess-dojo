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

type WebSocketContextValue = {
    status: WSStatus;
    sendMessage: (data: any) => void;
    lastMessage: MessageEvent | null;
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
    const sendQueueRef = useRef<any[]>([]);

    const [status, setStatus] = useState<WSStatus>("idle");
    const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);

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
        }
        ws.onmessage = (evt) => setLastMessage(evt);
        ws.onerror = () => setStatus("error");

        ws.onclose = () => {
            setStatus("closed");
            if (wsRef.current === ws) {
                wsRef.current = null;
            }
            // Automatically attempt to reconnect
            setTimeout(() => connect(), 1000);
        };
    }, [url]);

    // Initialise websocket connection on page load.
    useEffect(() => {
        connect();

        // Close the connection when app unloads or provider unmounts
        wsRef.current?.close(1000, "Provider unmounted");
        wsRef.current = null;
    }, [connect]);

    const sendMessage = useCallback(
        (message: any) => {
            const ws = wsRef.current;

            if (!ws || ws.readyState !== WebSocket.OPEN) {
                sendQueueRef.current.push(message);
                connect();
                return;
            }

            ws.send(JSON.stringify({ data: message }));
        },
        [connect],
    );

    const value = useMemo(
        () => ({ status, sendMessage, lastMessage }),
        [status, sendMessage, lastMessage],
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
