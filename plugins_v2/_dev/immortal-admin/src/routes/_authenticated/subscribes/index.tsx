import { createFileRoute } from '@tanstack/react-router'
import { Subscribes } from '@/features/subscribes'

export const Route = createFileRoute('/_authenticated/subscribes/')({
  component: Subscribes,
})