import { createRootRoute, Link, Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";
import "./root.css";

const RootLayout = () => (
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
        <Outlet />
        <TanStackRouterDevtools />
    </>
);

export const Route = createRootRoute({ component: RootLayout });
