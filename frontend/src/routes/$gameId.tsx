import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/$gameId')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/$gameId"!</div>
}
