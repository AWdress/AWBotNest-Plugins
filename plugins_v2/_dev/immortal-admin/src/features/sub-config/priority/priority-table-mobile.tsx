import { Pencil, Star, Trash2 } from 'lucide-react'
import type { Priority } from '@/api/priority.ts'
import { Button } from '@/components/ui/button.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Card, CardContent, CardFooter } from '@/components/ui/card.tsx'
import { ConfirmButton } from '@/components/confirm-button.tsx'
import { EmptyState } from '@/components/empty.tsx'
import { Loading } from '@/components/loading.tsx'

export function PriorityTableMobile({
                                      data,
                                      onEdit,
                                      onDelete,
                                      isLoading,
                                    }: {
  data?: Priority[]
  onEdit: (priority: Priority) => void
  onDelete: (id: number) => void
  isLoading: boolean
}) {
  return (
    <div className='space-y-2'>
      {isLoading && <Loading />}
      {!isLoading && data?.length === 0 && <EmptyState />}
      {data?.map((priority: Priority) => (
        <Card className='w-full' key={priority.id}>
          <CardContent>
            <dl className='space-y-3'>
              <div className='flex justify-between'>
                <dt className='text-sm text-muted-foreground shrink-0'>ID</dt>
                <dd className='text-sm min-w-0 break-all text-right'>{priority.id}</dd>
              </div>
              <div className='flex justify-between'>
                <dt className='text-sm text-muted-foreground shrink-0'>名称</dt>
                <dd className='text-sm min-w-0 break-all text-right font-medium'>
                  {priority.priority_name}
                </dd>
              </div>
              {!!priority.resolutions.length && (
                <div className='flex justify-between items-start gap-2'>
                  <dt className='text-sm text-muted-foreground shrink-0'>分辨率</dt>
                  <dd className='flex flex-wrap justify-end gap-1'>
                    {priority.resolutions.map((r,i) => (
                      <Badge key={r} variant='outline' className='text-xs'> {i + 1}. {r}</Badge>
                    ))}
                  </dd>
                </div>
              )}
              {!!priority.subtitles.length && (
                <div className='flex justify-between items-start gap-2'>
                  <dt className='text-sm text-muted-foreground shrink-0'>字幕</dt>
                  <dd className='flex flex-wrap justify-end gap-1'>
                    {priority.subtitles.map((s,i) => (
                      <Badge key={s} variant='outline' className='text-xs'> {i + 1}. {s}</Badge>
                    ))}
                  </dd>
                </div>
              )}
              {!!priority.mosaic.length && (
                <div className='flex justify-between items-start gap-2'>
                  <dt className='text-sm text-muted-foreground shrink-0'>马赛克</dt>
                  <dd className='flex flex-wrap justify-end gap-1'>
                    {priority.mosaic.map((m,i) => (
                      <Badge key={m} variant='outline' className='text-xs'> {i + 1}. {m}</Badge>
                    ))}
                  </dd>
                </div>
              )}
              {!!priority.priority_sort.length && (
                <div className='flex justify-between items-start gap-2'>
                  <dt className='text-sm text-muted-foreground shrink-0'>排序维度</dt>
                  <dd className='flex flex-wrap justify-end gap-1'>
                    {priority.priority_sort.map((s, i) => (
                      <Badge key={s} variant='outline' className='text-xs'>
                        {i + 1}. {s}
                      </Badge>
                    ))}
                  </dd>
                </div>
              )}
              <div className='flex justify-between'>
                <dt className='text-sm text-muted-foreground shrink-0'>默认</dt>
                <dd className='text-sm min-w-0 text-right'>
                  {priority.is_default ? (
                    <Star className='h-4 w-4 fill-amber-400 text-amber-400 inline' />
                  ) : (
                    '—'
                  )}
                </dd>
              </div>
            </dl>
          </CardContent>
          <CardFooter className='flex justify-end gap-2'>
            <Button variant='outline' size='icon' onClick={() => onEdit(priority)}>
              <Pencil className='h-4 w-4' />
            </Button>
            <ConfirmButton
              variant='outline'
              className='text-destructive'
              title='删除优先级'
              description='删除后数据将无法恢复，是否确认？'
              triggerText={<Trash2 className='h-4 w-4' />}
              onConfirm={() => onDelete(priority.id!)}
            />
          </CardFooter>
        </Card>
      ))}
    </div>
  )
}