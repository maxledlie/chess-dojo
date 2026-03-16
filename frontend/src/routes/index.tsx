import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useWebSocket } from "../components/WebSocketProvider";
import { Chessboard } from "react-chessboard";
import "./index.css";

export const Route = createFileRoute("/")({
    component: Index,
});

interface GameBeginData {
    msg_type: "game_begin";
    you_are_white: boolean;
    game_id: string;
}

const STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

function Index() {
    const [isWaiting, setIsWaiting] = useState<boolean>(false);
    const navigate = useNavigate({ from: "/" });

    const { sendMessage, lastMessage, pingMillis, playerCount, gameCount } =
        useWebSocket();

    const { data: dailyPosition } = useQuery({
        queryKey: ["position", "today"],
        queryFn: async () => {
            const res = await fetch("/api/position/today");
            if (!res.ok) return null;
            return res.json() as Promise<{ date: string; fen: string; summary: string }>;
        },
    });

    useEffect(() => {
        if (!lastMessage) {
            return;
        }

        const msg = JSON.parse(lastMessage.data).data;
        switch (msg.msg_type) {
            case "game_begin": {
                const data: GameBeginData = msg;
                sessionStorage.setItem(
                    `cress:game-color:${data.game_id}`,
                    String(data.you_are_white),
                );
                navigate({
                    to: "/$gameId",
                    params: { gameId: data.game_id },
                });
                break;
            }
        }
    }, [lastMessage]);

    function requestGame(timeControl: string) {
        sendMessage({ msg_type: "game_request", time_control: timeControl });
        setIsWaiting(true);
    }

    return (
        <div className="home-layout">
            <div className="home-content">
                <h1 className="home-headline">Practise chess middlegames. </h1>
                <h2 className="home-headline home-subheadline">
                    Start from a new, interesting position each day.
                </h2>

                <div className="home-board-wrapper">
                    <Chessboard
                        options={{
                            position: dailyPosition?.fen ?? STARTING_FEN,
                            canDragPiece: () => false,
                        }}
                    />
                    {dailyPosition?.summary && (
                        <p className="home-board-caption">{dailyPosition.summary}</p>
                    )}
                </div>

                <div className="home-actions">
                    {isWaiting ? (
                        <p className="home-waiting">
                            Waiting for a game&hellip;
                        </p>
                    ) : (
                        <>
                            <button
                                className="home-btn home-btn--primary"
                                onClick={() => requestGame("blitz_5p0")}
                            >
                                Blitz
                                <span className="home-btn-sub">5+0</span>
                            </button>
                            <button
                                className="home-btn home-btn--secondary"
                                onClick={() => requestGame("rapid_10p0")}
                            >
                                Rapid
                                <span className="home-btn-sub">10+0</span>
                            </button>
                        </>
                    )}
                </div>
            </div>

            <div className="server-stats">
                <span>{`${playerCount} online`}</span>
                <span>{`${gameCount} games`}</span>
                <span>{`ping: ${pingMillis}ms`}</span>
            </div>
        </div>
    );
}
