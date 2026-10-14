import { createFileRoute } from '@tanstack/react-router'
import { SubConfigPreference } from '@/features/sub-config/preference'

export const Route = createFileRoute('/_authenticated/sub-config/preference')({
  component: SubConfigPreference,
})
