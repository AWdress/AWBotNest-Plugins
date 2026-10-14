import { createFileRoute } from '@tanstack/react-router'
import { Articles } from '@/features/articles/index.tsx'

export const Route = createFileRoute('/_authenticated/articles/')({
  component: Articles,
})
