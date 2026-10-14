import { Pencil, Star, Trash2 } from 'lucide-react'
import type { Filter } from '@/api/filter.ts'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardFooter } from '@/components/ui/card.tsx'
import { ConfirmButton } from '@/components/confirm-button.tsx'
import { EmptyState } from '@/components/empty.tsx'
import { Loading } from '@/components/loading.tsx'

export function FilterTableMobile({
  data,
  onEdit,
  onDelete,
  isLoading,
}: {
  data?: Filter[]
  onEdit: (filter: Filter) => void
  onDelete: (id: number) => void
  isLoading: boolean
}) {
  return (
    <div className='space-y-2'>
      {isLoading && <Loading />}
      {!isLoading && data?.length === 0 && <EmptyState />}
      {data?.map((filter: Filter) => (
        <Card className='w-full' key={filter.id}>
          <CardContent>
            <dl className='space-y-3'>
              <div className='flex justify-between'>
                <dt className='shrink-0 text-sm text-muted-foreground'>ID</dt>
                <dd className='min-w-0 text-right text-sm break-all'>
                  {filter.id}
                </dd>
              </div>
              <div className='flex justify-between'>
                <dt className='shrink-0 text-sm text-muted-foreground'>名称</dt>
                <dd className='min-w-0 text-right text-sm font-medium break-all'>
                  {filter.filter_name}
                </dd>
              </div>
              {filter.keyword && (
                <div className='flex justify-between'>
                  <dt className='shrink-0 text-sm text-muted-foreground'>
                    关键词
                  </dt>
                  <dd className='min-w-0 text-right text-sm break-all'>
                    {filter.keyword}
                  </dd>
                </div>
              )}
              {filter.regex && (
                <div className='flex justify-between gap-2'>
                  <dt className='shrink-0 text-sm text-muted-foreground'>
                    正则
                  </dt>
                  <dd className='min-w-0 text-right text-sm break-all'>
                    {filter.regex}
                  </dd>
                </div>
              )}
              {!!filter.resolutions?.length && (
                <div className='flex items-start justify-between gap-2'>
                  <dt className='shrink-0 text-sm text-muted-foreground'>
                    分辨率
                  </dt>
                  <dd className='flex flex-wrap justify-end gap-1'>
                    {filter.resolutions.map((r) => (
                      <Badge key={r} variant='secondary' className='text-xs'>
                        {r}
                      </Badge>
                    ))}
                  </dd>
                </div>
              )}
              {!!filter.subtitles?.length && (
                <div className='flex items-start justify-between gap-2'>
                  <dt className='shrink-0 text-sm text-muted-foreground'>
                    字幕
                  </dt>
                  <dd className='flex flex-wrap justify-end gap-1'>
                    {filter.subtitles.map((s) => (
                      <Badge key={s} variant='secondary' className='text-xs'>
                        {s}
                      </Badge>
                    ))}
                  </dd>
                </div>
              )}
              {!!filter.mosaic?.length && (
                <div className='flex items-start justify-between gap-2'>
                  <dt className='shrink-0 text-sm text-muted-foreground'>
                    马赛克
                  </dt>
                  <dd className='flex flex-wrap justify-end gap-1'>
                    {filter.mosaic.map((m) => (
                      <Badge key={m} variant='secondary' className='text-xs'>
                        {m}
                      </Badge>
                    ))}
                  </dd>
                </div>
              )}
              {(filter.min_size !== undefined ||
                filter.max_size !== undefined) && (
                <div className='flex justify-between'>
                  <dt className='shrink-0 text-sm text-muted-foreground'>
                    体积 (MB)
                  </dt>
                  <dd className='min-w-0 text-right text-sm break-all'>
                    {filter.min_size ?? 0} – {filter.max_size ?? '∞'}
                  </dd>
                </div>
              )}
              <div className='flex justify-between'>
                <dt className='shrink-0 text-sm text-muted-foreground'>默认</dt>
                <dd className='min-w-0 text-right text-sm'>
                  {filter.is_default ? (
                    <Star className='inline h-4 w-4 fill-amber-400 text-amber-400' />
                  ) : (
                    '—'
                  )}
                </dd>
              </div>
              <div className='flex justify-between'>
                <dt className='shrink-0 text-sm text-muted-foreground'>
                  跳过在库检测
                </dt>
                <dd className='min-w-0 text-right text-sm'>
                  {filter.skip_in_library_check ? (
                    <Badge variant='outline' className='text-xs'>
                      已跳过
                    </Badge>
                  ) : (
                    '—'
                  )}
                </dd>
              </div>
              <div className='flex justify-between'>
                <dt className='shrink-0 text-sm text-muted-foreground'>
                  预下载
                </dt>
                <dd className='min-w-0 text-right text-sm'>
                  {filter.enable_pre_download ? (
                    <Badge variant='outline' className='text-xs'>
                      已开启
                    </Badge>
                  ) : (
                    '—'
                  )}
                </dd>
              </div>
            </dl>
          </CardContent>
          <CardFooter className='flex justify-end gap-2'>
            <Button
              variant='outline'
              size='icon'
              onClick={() => onEdit(filter)}
            >
              <Pencil className='h-4 w-4' />
            </Button>
            <ConfirmButton
              variant='outline'
              className='text-destructive'
              title='删除过滤器'
              description='删除后数据将无法恢复，是否确认？'
              triggerText={<Trash2 className='h-4 w-4' />}
              onConfirm={() => onDelete(filter.id!)}
            />
          </CardFooter>
        </Card>
      ))}
    </div>
  )
}
