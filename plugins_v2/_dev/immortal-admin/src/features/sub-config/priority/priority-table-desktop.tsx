import { Pencil, Star, Trash2 } from 'lucide-react'
import type { Priority } from '@/api/priority.ts'
import { Button } from '@/components/ui/button.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table.tsx'
import { ConfirmButton } from '@/components/confirm-button.tsx'

export function PriorityTableDesktop({
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
    <div className='rounded-lg border'>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>名称</TableHead>
            <TableHead>分辨率</TableHead>
            <TableHead>字幕</TableHead>
            <TableHead>马赛克</TableHead>
            <TableHead>排序维度</TableHead>
            <TableHead>默认</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading && (
            <TableRow>
              <TableCell colSpan={8} className='text-center'>
                加载中...
              </TableCell>
            </TableRow>
          )}
          {!isLoading && data?.length === 0 && (
            <TableRow>
              <TableCell colSpan={8} className='text-center'>
                暂无数据
              </TableCell>
            </TableRow>
          )}
          {data?.map((item) => (
            <TableRow key={item.id}>
              <TableCell>{item.id}</TableCell>
              <TableCell className='font-medium'>{item.priority_name}</TableCell>
              <TableCell>
                <div className='flex flex-wrap gap-1'>
                  {item.resolutions.length
                    ? item.resolutions.map((r,i) => (
                      <Badge key={r} variant='outline' className='text-xs'>{i + 1}.{r}</Badge>
                    ))
                    : '—'}
                </div>
              </TableCell>
              <TableCell>
                <div className='flex flex-wrap gap-1'>
                  {item.subtitles.length
                    ? item.subtitles.map((s,i) => (
                      <Badge key={s} variant='outline' className='text-xs'>{i + 1}.{s}</Badge>
                    ))
                    : '—'}
                </div>
              </TableCell>
              <TableCell>
                <div className='flex flex-wrap gap-1'>
                  {item.mosaic.length
                    ? item.mosaic.map((m,i) => (
                      <Badge key={m} variant='outline' className='text-xs'>{i + 1}.{m}</Badge>
                    ))
                    : '—'}
                </div>
              </TableCell>
              <TableCell>
                <div className='flex flex-wrap gap-1'>
                  {item.priority_sort.length
                    ? item.priority_sort.map((s, i) => (
                      <Badge key={s} variant='outline' className='text-xs'>
                        {i + 1}. {s}
                      </Badge>
                    ))
                    : '—'}
                </div>
              </TableCell>
              <TableCell>
                {item.is_default && (
                  <Star className='h-4 w-4 fill-amber-400 text-amber-400' />
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
                  title='删除优先级'
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