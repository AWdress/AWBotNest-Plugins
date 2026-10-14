import { createFileRoute } from '@tanstack/react-router'

import { SettingsMediaServer } from '@/features/settings/media-server'

export const Route = createFileRoute('/_authenticated/settings/media-server')({
  component: SettingsMediaServer,
})
