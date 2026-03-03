import { useEffect, useRef } from "react";
import { useWebSocket, type WsLogEntry } from "./WebSocketProvider";

interface DebugPanelProps {
    isOpen: boolean;
    onToggle: () => void;
}

function formatTime(d: Date): string {
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");
    const ms = String(d.getMilliseconds()).padStart(3, "0");
    return `${hh}:${mm}:${ss}.${ms}`;
}

function formatRaw(raw: string): string {
    try {
        return JSON.stringify(JSON.parse(raw), null, 2);
    } catch {
        return raw;
    }
}

function MessageEntry({ entry }: { entry: WsLogEntry }) {
    const isSent = entry.direction === "sent";
    return (
        <div className={`debug-panel__entry debug-panel__entry--${entry.direction}`}>
            <span className="debug-panel__arrow">{isSent ? "↑" : "↓"}</span>
            <span className="debug-panel__time">{formatTime(entry.timestamp)}</span>
            <pre className="debug-panel__raw">{formatRaw(entry.raw)}</pre>
        </div>
    );
}

export default function DebugPanel({ isOpen, onToggle }: DebugPanelProps) {
    const { messages } = useWebSocket();
    const listRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (isOpen && listRef.current) {
            listRef.current.scrollTop = listRef.current.scrollHeight;
        }
    }, [messages, isOpen]);

    if (!isOpen) {
        return (
            <div className="debug-panel debug-panel--closed">
                <button className="debug-panel__toggle" onClick={onToggle} title="Open debug panel">
                    WS
                </button>
            </div>
        );
    }

    return (
        <div className="debug-panel debug-panel--open">
            <div className="debug-panel__header">
                <span className="debug-panel__title">WS Debug</span>
                <span className="debug-panel__count">{messages.length} messages</span>
                <button className="debug-panel__close" onClick={onToggle} title="Close debug panel">
                    ✕
                </button>
            </div>
            <div className="debug-panel__list" ref={listRef}>
                {messages.length === 0 ? (
                    <div className="debug-panel__empty">No messages yet.</div>
                ) : (
                    messages.map((entry, i) => <MessageEntry key={i} entry={entry} />)
                )}
            </div>
        </div>
    );
}
