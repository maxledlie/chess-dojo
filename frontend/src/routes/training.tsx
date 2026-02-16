import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/training')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/training"!</div>
}
