import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import { SubscribeSearchPage } from '@/features/subscribes/search-page.tsx'

const searchSchema = z.object({
  entity: z.enum(['movie', 'cast']).optional(),
  keyword: z.string().optional(),
})

export const Route = createFileRoute('/_authenticated/subscribes/search')({
  component: SubscribeSearchPage,
  validateSearch: searchSchema,
})
