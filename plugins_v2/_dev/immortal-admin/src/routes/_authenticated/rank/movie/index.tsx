import { createFileRoute } from '@tanstack/react-router'
import { RankMovie } from '@/features/rank/movie'

export const Route = createFileRoute('/_authenticated/rank/movie/')({
  component: RankMovie,
})
