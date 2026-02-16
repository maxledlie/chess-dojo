import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/broadcast')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/broadcast"!</div>
}
