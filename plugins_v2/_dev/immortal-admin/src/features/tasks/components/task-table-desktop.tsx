import { LoaderCircle, Pencil, Play, Trash2 } from 'lucide-react'
import type { Task } from '@/api/task.ts'
import { cn } from '@/lib/utils.ts'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table.tsx'
import { ConfirmButton } from '@/components/confirm-button.tsx'

export function TaskTableDesktop({
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
    <div className='rounded-lg border'>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>任务名称</TableHead>
            <TableHead>运行周期</TableHead>
            <TableHead>推送</TableHead>
            <TableHead>任务核心</TableHead>
            <TableHead className='sticky right-0 z-20 bg-background shadow-[-1px_0_0_0_hsl(var(--border))]'>
              操作
            </TableHead>
          </TableRow>
        </TableHeader>

        <TableBody>
          {isLoading && (
            <TableRow>
              <TableCell colSpan={9} className='text-center'>
                加载中...
              </TableCell>
            </TableRow>
          )}

          {data?.length === 0 && (
            <TableRow>
              <TableCell colSpan={9} className='text-center'>
                暂无数据
              </TableCell>
            </TableRow>
          )}

          {data?.map((task) => {
            const isRunning = runningTaskIds.includes(task.id)

            return (
              <TableRow key={task.id}>
                <TableCell>
                  <div className='flex items-center gap-3 pl-2'>
                    <div
                      className={cn(
                        'h-2 w-2 rounded-full',
                        task.enable
                          ? 'animate-pulse bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]'
                          : 'bg-slate-400 shadow-none'
                      )}
                    />
                    <span className='text-base font-bold'>
                      {task.task_name}
                    </span>
                  </div>
                </TableCell>

                <TableCell>
                  <span className='font-mono text-sm text-muted-foreground'>
                    {task.task_cron}
                  </span>
                </TableCell>

                <TableCell>
                  <div className='flex flex-col gap-1'>
                    <Badge variant={task.push_enable ? 'default' : 'secondary'}>
                      {task.push_enable ? '开启' : '关闭'}
                    </Badge>
                    {task.push_enable && (
                      <Badge
                        variant={
                          task.push_title_template || task.push_message_template
                            ? 'outline'
                            : 'secondary'
                        }
                      >
                        {task.push_title_template || task.push_message_template
                          ? '自定义模板'
                          : '默认模板'}
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <div className='flex flex-row items-end gap-2'>
                    <Badge variant='outline' className='font-mono'>
                      {task.task_func}
                    </Badge>
                    <div className='flex items-center gap-2'>
                      <span className='hidden text-xs text-muted-foreground md:inline'>
                        →
                      </span>
                      <span className='max-w-50 truncate text-xs text-slate-600 md:max-w-none'>
                        {task.task_args}
                      </span>
                    </div>
                  </div>
                </TableCell>

                <TableCell className='sticky right-0 z-10 bg-background shadow-[-1px_0_0_0_hsl(var(--border))]'>
                  <ConfirmButton
                    variant='outline'
                    title='确认执行任务'
                    description={
                      isRunning
                        ? '任务正在后台执行，请等待当前执行完成。'
                        : '任务将在后台执行，请勿频繁重复触发。'
                    }
                    confirmText='开始执行'
                    pendingText='执行中...'
                    triggerText={
                      isRunning ? (
                        <LoaderCircle className='h-4 w-4 animate-spin' />
                      ) : (
                        <Play className='h-4 w-4' />
                      )
                    }
                    className={cn(
                      'mr-2 text-emerald-700',
                      isRunning && 'text-amber-600'
                    )}
                    disabled={isRunning}
                    confirmDisabled={isRunning}
                    onConfirm={() => onRun(task.id)}
                  />
                  <Button
                    variant='outline'
                    size='icon'
                    className='mr-2'
                    onClick={() => onEdit(task)}
                  >
                    <Pencil className='h-4 w-4' />
                  </Button>
                  <ConfirmButton
                    variant='outline'
                    className='mr-2 text-destructive'
                    title='删除任务'
                    description='删除后数据将无法恢复，是否确认？'
                    triggerText={<Trash2 className='h-4 w-4' />}
                    onConfirm={() => onDelete(task.id)}
                  />
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
