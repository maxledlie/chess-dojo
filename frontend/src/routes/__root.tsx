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
                        chess dojo
                    </Link>{" "}
                </nav>
            </header>
            <WebSocketProvider
                url={`${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws`}
            >
                <div className="app-body">
                    <main className="app-main">
                        <Outlet />
                    </main>
                    {false && (
                        <DebugPanel
                            isOpen={isDebugOpen}
                            onToggle={() => setIsDebugOpen((o) => !o)}
                        />
                    )}
                </div>
            </WebSocketProvider>
            <TanStackRouterDevtools />
        </>
    );
};

export const Route = createRootRoute({ component: RootLayout });
