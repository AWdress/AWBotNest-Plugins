import { createFileRoute } from '@tanstack/react-router'
import { SubConfigFilter } from '@/features/sub-config/filter'

export const Route = createFileRoute('/_authenticated/sub-config/')({
  component: SubConfigFilter,
})
