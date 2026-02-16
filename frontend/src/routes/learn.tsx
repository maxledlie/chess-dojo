import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/learn')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/learn"!</div>
}
