import { createRootRoute, Link, Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";
import "./root.css";
import { useEffect, useState } from "react";
import WebSocketProvider from "../components/WebSocketProvider";
import DebugPanel from "../components/DebugPanel";

const RootLayout = () => {
    // Establish guest identity and websocket connection on page load
    useEffect(() => {
        async function init() {
            const sessionUrl = "/api/session";
            console.log(`Fetching from ${sessionUrl}`);
            const res = await fetch(sessionUrl, { credentials: "include" });
            const data = await res.json();
            sessionStorage.setItem("cress:session-id", data.session_id);
        }
        init();
    }, []);

    const [isDebugOpen, setIsDebugOpen] = useState(false);

    return (
        <>
            <header>
                <nav>
                    <Link to="/" className="navlink navlink-title">
                        cress.io
                    </Link>{" "}
                    <Link to="/" className="navlink">
                        PLAY
                    </Link>
                    <Link to="/training" className="navlink">
                        PUZZLES
                    </Link>
                    <Link to="/learn" className="navlink">
                        LEARN
                    </Link>
                    <Link to="/broadcast" className="navlink">
                        WATCH
                    </Link>
                    <Link to="/player" className="navlink">
                        COMMUNITY
                    </Link>
                    <Link to="/analysis" className="navlink">
                        TOOLS
                    </Link>
                </nav>
            </header>
            <WebSocketProvider url={`${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws`}>
                <div className="app-body">
                    <main className="app-main">
                        <Outlet />
                    </main>
                    <DebugPanel isOpen={isDebugOpen} onToggle={() => setIsDebugOpen((o) => !o)} />
                </div>
            </WebSocketProvider>
            <TanStackRouterDevtools />
        </>
    );
};

export const Route = createRootRoute({ component: RootLayout });
