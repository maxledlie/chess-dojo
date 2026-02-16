import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/analysis')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/analysis"!</div>
}
