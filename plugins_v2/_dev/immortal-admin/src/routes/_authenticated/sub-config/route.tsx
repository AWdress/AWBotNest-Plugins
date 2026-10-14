import { createFileRoute } from '@tanstack/react-router'
import { SubConfig } from '@/features/sub-config'

export const Route = createFileRoute('/_authenticated/sub-config')({
  component: SubConfig,
})
