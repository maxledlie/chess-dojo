import { useEffect, useState, useCallback, useRef } from "react";

interface UseWebSocketOptions {
    onMessage?: (event: MessageEvent) => void;
}

export default function useWebSocket(options?: UseWebSocketOptions) {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${scheme}://${window.location.host}/ws`;

    const [ws, setWs] = useState<WebSocket | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const onMessageRef = useRef(options?.onMessage);

    // Update ref when onMessage changes
    useEffect(() => {
        onMessageRef.current = options?.onMessage;
    }, [options?.onMessage]);

    useEffect(() => {
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            setIsConnected(true);
        };

        ws.onmessage = (event) => {
            if (onMessageRef.current) {
                onMessageRef.current(event);
            }
        };

        ws.onclose = () => {
            setIsConnected(false);
        };

        ws.onerror = (error) => {
            console.error("WebSocket error:", error);
            setIsConnected(false);
        };

        setWs(ws);

        return () => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.close();
            }
        };
    }, []);

    const sendMessage = useCallback(
        (message: any) => {
            if (!ws) {
                console.error("WebSocket not established!");
                return;
            }
            if (ws.readyState !== WebSocket.OPEN) {
                console.error("WebSocket is not open!");
                return;
            }
            ws.send(JSON.stringify({ data: message }));
        },
        [ws],
    );

    return { ws, isConnected, sendMessage };
}
