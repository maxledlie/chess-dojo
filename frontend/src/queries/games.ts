import { useQuery } from "@tanstack/react-query";
import { getGame } from "../client";

function isNotFound(err: unknown): boolean {
    return (
        typeof err === "object" &&
        err !== null &&
        ("status" in err ? (err as any).status === 404 : false)
    );
}

export function useGetGame(gameId: string) {
    return useQuery({
        queryKey: ["game", gameId],
        queryFn: async () => {
            try {
                return (await getGame({ path: { game_id: gameId } })).data;
            } catch (err) {
                if (isNotFound(err)) {
                    return null;
                }
                throw err;
            }
        },
    });
}
