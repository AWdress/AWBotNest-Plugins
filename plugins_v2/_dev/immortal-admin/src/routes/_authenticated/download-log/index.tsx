import { createFileRoute } from '@tanstack/react-router'
import { DownloadLog } from '@/features/download-log'


export const Route = createFileRoute('/_authenticated/download-log/')({
  component: DownloadLog,
})
