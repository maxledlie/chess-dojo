import { createRootRoute, Link, Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";
import "./root.css";
import { useEffect } from "react";
import WebSocketProvider from "../components/WebSocketProvider";

const RootLayout = () => {
    // Establish guest identity and websocket connection on page load
    useEffect(() => {
        async function init() {
            const sessionUrl = "/api/session";
            console.log(`Fetching from ${sessionUrl}`);
            await fetch(sessionUrl, { credentials: "include" });
        }
        init();
    }, []);

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
            <WebSocketProvider url={"ws://localhost:8000/ws"}>
                <Outlet />
            </WebSocketProvider>
            <TanStackRouterDevtools />
        </>
    );
};

export const Route = createRootRoute({ component: RootLayout });
