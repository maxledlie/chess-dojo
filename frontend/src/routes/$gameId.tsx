import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/$gameId")({
    component: GamePage,
});

function GamePage() {
    const { gameId } = Route.useParams();

    return <div>Game ID: {gameId}</div>;
}
