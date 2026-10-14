import { createFileRoute } from '@tanstack/react-router'
import { TaskLog } from '@/features/tasks/log'



export const Route = createFileRoute('/_authenticated/tasks/log')({
  component: TaskLog,
})
