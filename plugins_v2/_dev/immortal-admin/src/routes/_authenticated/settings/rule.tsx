import { createFileRoute } from '@tanstack/react-router'
import { SettingsRule } from '@/features/settings/rule'

export const Route = createFileRoute('/_authenticated/settings/rule')({
  component: SettingsRule,
})
