import { createFileRoute } from '@tanstack/react-router'
import { SubConfigPriority } from '@/features/sub-config/priority'

export const Route = createFileRoute('/_authenticated/sub-config/priority')({
  component: SubConfigPriority,
})
