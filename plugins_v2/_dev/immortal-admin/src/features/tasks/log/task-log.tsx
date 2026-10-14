import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getTasks, pageTaskLog } from '@/api/task.ts'
import { formatDateTime } from '@/lib/utils.ts'
import { Badge } from '@/components/ui/badge.tsx'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover.tsx'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.tsx'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table.tsx'
import { CommonPagination } from '@/components/pagination.tsx'

const PAGE_SIZE = 20

export function TaskLogTable() {
  const [filter, setFilter] = useState({
    task_func: '',
    page: 1,
    pageSize: 20,
  })
  const { data, isLoading } = useQuery({
    queryKey: ['task-log', filter],
    queryFn: async () => {
      const res = await pageTaskLog(filter)
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const { data: tasks } = useQuery({
    queryKey: ['tasks'],
    queryFn: async () => {
      const res = await getTasks()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })
  return (
    <div className='flex h-full flex-col overflow-hidden space-y-2'>
      <div className='shrink-0'>
        <Select
          value={filter.task_func}
          onValueChange={(v) =>
            setFilter((prev) => ({ ...prev, task_func: v === 'all' ? '' : v }))
          }
        >
          <SelectTrigger className='w-full max-w-48'>
            <SelectValue placeholder='选择一个阵法' />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value='all'>全部阵法</SelectItem>
              {tasks?.map((item, index) => (
                <SelectItem value={item.task_func} key={index}>
                  {item.task_name}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>
      <div className='flex-1 overflow-auto border' data-main-scroll-container>
        <Table>
          <TableHeader >
            <TableRow>
              <TableHead>阵法名称</TableHead>
              <TableHead>阵法核心</TableHead>
              <TableHead>开始时间</TableHead>
              <TableHead>结束时间</TableHead>
              <TableHead>执行耗时</TableHead>
              <TableHead className='max-w-[300px]'>输出信息</TableHead>
              <TableHead>执行结果</TableHead>
              <TableHead>异常信息</TableHead>
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
            {data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={9} className='text-center'>
                  暂无数据
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((log) => (
              <TableRow key={log.id}>
                <TableCell>{log.task_name}</TableCell>
                <TableCell>{log.task_func}</TableCell>
                <TableCell>{formatDateTime(log.start_time)}</TableCell>
                <TableCell>{formatDateTime(log.end_time)}</TableCell>
                <TableCell>{log.execute_seconds}秒</TableCell>
                <TableCell className='max-w-[300px] overflow-hidden'>
                  <Popover>
                    <PopoverTrigger asChild>
                      <span className='cursor-pointer truncate'>
                        {log.execute_result}
                      </span>
                    </PopoverTrigger>
                    <PopoverContent
                      className='max-h-[400px] max-w-[600px] overflow-auto bg-background/20 backdrop-blur-lg'
                      align="start"
                    >
                      <pre className='text-xs whitespace-pre-wrap'>
                        {JSON.stringify(
                          JSON.parse(log.execute_result),
                          null,
                          2
                        )}
                      </pre>
                    </PopoverContent>
                  </Popover>
                </TableCell>
                <TableCell>
                  <Badge
                    className={
                      log.success
                        ? 'bg-green-500 hover:bg-green-500'
                        : 'bg-red-500 hover:bg-red-500'
                    }
                  >
                    {log.success ? '成功' : '失败'}
                  </Badge>
                </TableCell>
                <TableCell className='max-w-[300px] overflow-hidden'>
                  <Popover>
                    <PopoverTrigger asChild>
                      <span className='cursor-pointer truncate'>
                        {log.error}
                      </span>
                    </PopoverTrigger>
                    <PopoverContent
                      className='max-h-[400px] max-w-[600px] overflow-auto bg-background/20 backdrop-blur-lg' align="start"
                    >
                      <pre className='text-xs whitespace-pre-wrap'>
                        {log.error}
                      </pre>
                    </PopoverContent>
                  </Popover>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className='shrink-0'>
        <CommonPagination
          page={filter.page}
          total={data?.total || 0}
          pageSize={PAGE_SIZE}
          onChange={(v) => setFilter((prev) => ({ ...prev, page: v }))}
        />
      </div>
    </div>
  )
}
