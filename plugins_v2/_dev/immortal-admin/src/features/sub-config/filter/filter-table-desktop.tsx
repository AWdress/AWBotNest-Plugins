import { Pencil, Star, Trash2 } from 'lucide-react'
import type { Filter } from '@/api/filter.ts'
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

export function FilterTableDesktop({
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
    <div className='rounded-lg border'>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>名称</TableHead>
            <TableHead>关键词</TableHead>
            <TableHead>正则</TableHead>
            <TableHead>分辨率</TableHead>
            <TableHead>字幕</TableHead>
            <TableHead>马赛克</TableHead>
            <TableHead>体积 (MB)</TableHead>
            <TableHead>默认</TableHead>
            <TableHead>跳过在库检测</TableHead>
            <TableHead>预下载</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading && (
            <TableRow>
              <TableCell colSpan={12} className='text-center'>
                加载中...
              </TableCell>
            </TableRow>
          )}
          {!isLoading && data?.length === 0 && (
            <TableRow>
              <TableCell colSpan={12} className='text-center'>
                暂无数据
              </TableCell>
            </TableRow>
          )}
          {data?.map((item) => (
            <TableRow key={item.id}>
              <TableCell>{item.id}</TableCell>
              <TableCell className='font-medium'>{item.filter_name}</TableCell>
              <TableCell className='text-muted-foreground'>
                {item.keyword || '—'}
              </TableCell>
              <TableCell className='max-w-52 break-all text-muted-foreground'>
                {item.regex || '—'}
              </TableCell>
              <TableCell>
                <div className='flex flex-wrap gap-1'>
                  {item.resolutions?.length
                    ? item.resolutions.map((r) => (
                        <Badge key={r} variant='secondary' className='text-xs'>
                          {r}
                        </Badge>
                      ))
                    : '—'}
                </div>
              </TableCell>
              <TableCell>
                <div className='flex flex-wrap gap-1'>
                  {item.subtitles?.length
                    ? item.subtitles.map((s) => (
                        <Badge key={s} variant='secondary' className='text-xs'>
                          {s}
                        </Badge>
                      ))
                    : '—'}
                </div>
              </TableCell>
              <TableCell>
                <div className='flex flex-wrap gap-1'>
                  {item.mosaic?.length
                    ? item.mosaic.map((m) => (
                        <Badge key={m} variant='secondary' className='text-xs'>
                          {m}
                        </Badge>
                      ))
                    : '—'}
                </div>
              </TableCell>
              <TableCell className='text-muted-foreground'>
                {item.min_size !== undefined || item.max_size !== undefined
                  ? `${item.min_size ?? 0} – ${item.max_size ?? '∞'}`
                  : '—'}
              </TableCell>
              <TableCell>
                {item.is_default && (
                  <Star className='h-4 w-4 fill-amber-400 text-amber-400' />
                )}
              </TableCell>
              <TableCell>
                {item.skip_in_library_check ? (
                  <Badge variant='outline' className='text-xs'>
                    已跳过
                  </Badge>
                ) : (
                  '—'
                )}
              </TableCell>
              <TableCell>
                {item.enable_pre_download ? (
                  <Badge variant='outline' className='text-xs'>
                    已开启
                  </Badge>
                ) : (
                  '—'
                )}
              </TableCell>
              <TableCell>
                <Button
                  variant='outline'
                  size='icon'
                  className='mr-2'
                  onClick={() => onEdit(item)}
                >
                  <Pencil className='h-4 w-4' />
                </Button>
                <ConfirmButton
                  variant='destructive'
                  title='删除过滤器'
                  description='删除后数据将无法恢复，是否确认？'
                  triggerText={<Trash2 className='h-4 w-4' />}
                  onConfirm={() => onDelete(item.id!)}
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
