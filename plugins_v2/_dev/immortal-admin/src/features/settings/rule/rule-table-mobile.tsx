import { Pencil, Trash2 } from 'lucide-react'
import type { Rule } from '@/api/rule.ts'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardFooter } from '@/components/ui/card.tsx'
import { ConfirmButton } from '@/components/confirm-button.tsx'
import { EmptyState } from '@/components/empty.tsx'
import { Loading } from '@/components/loading.tsx'

function renderValues(values: string[]) {
  return (
    <div className='flex flex-wrap justify-end gap-1'>
      {values.map((value) => (
        <Badge key={value} variant='secondary' className='text-xs'>
          {value === 'ALL' ? '不限' : value}
        </Badge>
      ))}
    </div>
  )
}

export function RuleTableMobile({
  data,
  onEdit,
  onDelete,
  isLoading,
}: {
  data?: Rule[]
  onEdit: (rule: Rule) => void
  onDelete: (id: number) => void
  isLoading: boolean
}) {
  return (
    <div className='space-y-2'>
      {isLoading && <Loading />}
      {data?.length === 0 && <EmptyState />}
      {data?.map((rule: Rule) => (
        <Card className='w-full' key={rule.id}>
          <CardContent>
            <dl className='space-y-3'>
              <div className='flex justify-between gap-4'>
                <dt className='shrink-0 text-sm text-muted-foreground'>
                  秩序ID
                </dt>
                <dd className='text-right text-sm'>{rule.id}</dd>
              </div>
              <div className='flex justify-between gap-4'>
                <dt className='shrink-0 text-sm text-muted-foreground'>站点</dt>
                <dd className='min-w-0'>{renderValues(rule.website)}</dd>
              </div>
              <div className='flex justify-between gap-4'>
                <dt className='shrink-0 text-sm text-muted-foreground'>板块</dt>
                <dd className='min-w-0'>{renderValues(rule.section)}</dd>
              </div>
              <div className='flex justify-between gap-4'>
                <dt className='shrink-0 text-sm text-muted-foreground'>分类</dt>
                <dd className='min-w-0'>{renderValues(rule.category)}</dd>
              </div>
              <div className='flex justify-between gap-4'>
                <dt className='shrink-0 text-sm text-muted-foreground'>正则</dt>
                <dd className='min-w-0 text-right font-mono text-xs break-all'>
                  {rule.regex || '-'}
                </dd>
              </div>
              <div className='flex justify-between gap-4'>
                <dt className='shrink-0 text-sm text-muted-foreground'>
                  下载器
                </dt>
                <dd className='min-w-0 text-right text-sm break-all'>
                  {rule.downloader}
                </dd>
              </div>
              <div className='flex justify-between gap-4'>
                <dt className='shrink-0 text-sm text-muted-foreground'>
                  保存路径
                </dt>
                <dd className='min-w-0 text-right text-sm break-all'>
                  {rule.save_path}
                </dd>
              </div>
            </dl>
          </CardContent>
          <CardFooter className='flex justify-end gap-2'>
            <Button variant='outline' size='icon' onClick={() => onEdit(rule)}>
              <Pencil className='h-4 w-4' />
            </Button>
            <ConfirmButton
              variant='outline'
              className='text-destructive'
              title='删除秩序'
              description='删除后数据将无法恢复，是否确认？'
              triggerText={<Trash2 className='h-4 w-4' />}
              onConfirm={() => onDelete(rule.id)}
            />
          </CardFooter>
        </Card>
      ))}
    </div>
  )
}
