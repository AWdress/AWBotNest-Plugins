import { createFileRoute } from '@tanstack/react-router'
import { SettingsDownloader } from '@/features/settings/downloader'


export const Route = createFileRoute('/_authenticated/settings/downloader')({
  component: SettingsDownloader,
})
