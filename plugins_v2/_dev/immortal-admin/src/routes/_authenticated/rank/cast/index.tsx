import { createFileRoute } from '@tanstack/react-router'
import { RankCast } from '@/features/rank/cast'

export const Route = createFileRoute('/_authenticated/rank/cast/')({
  component: RankCast,
})
