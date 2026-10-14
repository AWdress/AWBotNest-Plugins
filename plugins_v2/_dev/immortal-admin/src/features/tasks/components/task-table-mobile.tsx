import { LoaderCircle, Pencil, Play, Trash2 } from 'lucide-react'
import type { Task } from '@/api/task.ts'
import { cn } from '@/lib/utils.ts'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card.tsx'
import { ConfirmButton } from '@/components/confirm-button.tsx'
import { Loading } from '@/components/loading.tsx'
import { EmptyState } from '@/components/empty.tsx'

export function TaskTableMobile({
  data,
  onEdit,
  onDelete,
  onRun,
  isLoading,
  runningTaskIds,
}: {
  data?: Task[]
  onEdit: (task: Task) => void
  onDelete: (id: number) => void
  onRun: (id: number) => void | Promise<void>
  isLoading: boolean
  runningTaskIds: number[]
}) {
  return (
    <div className='space-y-2'>
      {isLoading && <Loading />}
      {data?.length === 0 && <EmptyState />}
      {data?.map((task) => {
        const isRunning = runningTaskIds.includes(task.id)

        return (
          <Card className='w-full' key={task.id}>
            <CardHeader>
              <CardTitle>
                <div className='flex items-center gap-3 pl-2'>
                  <div
                    className={cn(
                      'h-2 w-2 rounded-full',
                      task.enable
                        ? 'animate-pulse bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]'
                        : 'bg-slate-400 shadow-none'
                    )}
                  />
                  <span className='text-base font-bold'>{task.task_name}</span>
                </div>
              </CardTitle>
            </CardHeader>

            <CardContent>
              <dl className='space-y-3'>
                <div className='flex justify-between'>
                  <dt className='shrink-0 text-sm text-muted-foreground'>任务核心</dt>
                  <dd className='min-w-0 break-all text-right text-sm'>{task.task_func}</dd>
                </div>
                <div className='flex justify-between'>
                  <dt className='shrink-0 text-sm text-muted-foreground'>任务参数</dt>
                  <dd className='min-w-0 break-all text-right text-sm'>{task.task_args}</dd>
                </div>
                <div className='flex justify-between'>
                  <dt className='shrink-0 text-sm text-muted-foreground'>运行周期</dt>
                  <dd className='min-w-0 break-all text-right text-sm'>{task.task_cron}</dd>
                </div>
                <div className='flex items-center justify-between'>
                  <dt className='shrink-0 text-sm text-muted-foreground'>推送</dt>
                  <dd className='min-w-0 text-right text-sm'>
                    <div className='flex flex-col items-end gap-1'>
                      <Badge variant={task.push_enable ? 'default' : 'secondary'}>
                        {task.push_enable ? '开启' : '关闭'}
                      </Badge>
                      {task.push_enable && (
                        <Badge variant={task.push_title_template || task.push_message_template ? 'outline' : 'secondary'}>
                          {task.push_title_template || task.push_message_template ? '自定义模板' : '默认模板'}
                        </Badge>
                      )}
                    </div>
                  </dd>
                </div>
              </dl>
            </CardContent>

            <CardFooter className='flex justify-end gap-2'>
              <ConfirmButton
                variant='outline'
                title='确认执行任务'
                description={isRunning ? '任务正在后台执行，请等待当前执行完成。' : '任务将在后台执行，请勿频繁重复触发。'}
                confirmText='开始执行'
                pendingText='执行中...'
                triggerText={isRunning ? <LoaderCircle className='h-4 w-4 animate-spin' /> : <Play className='h-4 w-4' />}
                className={cn('text-emerald-700', isRunning && 'text-amber-600')}
                disabled={isRunning}
                confirmDisabled={isRunning}
                onConfirm={() => onRun(task.id)}
              />
              <Button variant='outline' size='icon' onClick={() => onEdit(task)}>
                <Pencil className='h-4 w-4' />
              </Button>
              <ConfirmButton
                variant='outline'
                className='text-destructive'
                title='删除任务'
                description='删除后数据将无法恢复，是否确认？'
                triggerText={<Trash2 className='h-4 w-4' />}
                onConfirm={() => onDelete(task.id)}
              />
            </CardFooter>
          </Card>
        )
      })}
    </div>
  )
}
