import * as z from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Check,
  Filter,
  ArrowUpDown,
  Star,
  Tag,
  Maximize2,
  Film,
  SlidersHorizontal,
} from 'lucide-react'
import { toast } from 'sonner'

import { listFilter } from '@/api/filter.ts'
import { listPriority } from '@/api/priority.ts'
import { subscribe, updateSubscribe } from '@/api/subscribe.ts'
import { cn } from '@/lib/utils.ts'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Checkbox } from '@/components/ui/checkbox.tsx'
import { Field, FieldContent, FieldDescription, FieldLabel, FieldTitle } from '@/components/ui/field.tsx'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogOverlay,
} from '@/components/ui/dialog.tsx'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.tsx'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import { useEffect } from 'react'
import { MOVIE_SUBSCRIPTION_QUERY_KEYS } from '@/lib/subscription-query-keys.ts'

const formSchema = z.object({
  filter_id: z.number().nullable().optional(),
  priority_id: z.number().nullable().optional(),
  pre_download_enabled: z.boolean(),
})

type FormValues = z.infer<typeof formSchema>

const defaultValues: FormValues = {
  filter_id: null,
  priority_id: null,
  pre_download_enabled: false,
}

interface SubscribeDialogProps {
  movieIdList: number[]
  open: boolean
  onOpenChange: (open: boolean) => void
  mode?: 'create' | 'edit'
  subscribeId?: number
  initialFilterId?: number | null
  initialPriorityId?: number | null
  initialPreDownloadEnabled?: boolean
}

// 格式化文件大小
function formatSize(bytes?: number) {
  if (!bytes) return null
  return `${(bytes / 1024).toFixed(0)}GB`
}

export function SubscribeDialog({
  open,
  onOpenChange,
  movieIdList,
  mode = 'create',
  subscribeId,
  initialFilterId,
  initialPriorityId,
  initialPreDownloadEnabled = false,
}: SubscribeDialogProps) {
  const queryClient = useQueryClient()
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues,
  })

  const { data: filters } = useQuery({
    queryKey: ['filters'],
    queryFn: async () => {
      const res = await listFilter()
      return res.data
    },
  })

  const { data: priorities } = useQuery({
    queryKey: ['priorities'],
    queryFn: async () => {
      const res = await listPriority()
      return res.data
    },
  })

  useEffect(() => {
    if (!open) return
    const defaultFilterId = filters?.find((f) => f.is_default)?.id
    const defaultPriorityId = priorities?.find((p) => p.is_default)?.id
    const nextFilterId = mode === 'edit'
      ? (initialFilterId == null ? null : initialFilterId)
      : (defaultFilterId ?? null)
    const nextPriorityId = mode === 'edit'
      ? (initialPriorityId == null ? null : initialPriorityId)
      : (defaultPriorityId ?? null)
    form.reset({
      filter_id: nextFilterId,
      priority_id: nextPriorityId,
      pre_download_enabled: mode === 'edit' ? Boolean(initialPreDownloadEnabled) : false,
    })
  }, [open, filters, priorities, form, mode, initialFilterId, initialPriorityId, initialPreDownloadEnabled])


  const submitMutation = useMutation({
    mutationFn: async (values: FormValues) => {
      const payload = {
        filter_id: values.filter_id ?? undefined,
        priority_id: values.priority_id ?? undefined,
        pre_download_enabled: values.pre_download_enabled,
      }
      if (mode === 'edit') {
        if (!subscribeId) {
          throw new Error('Missing subscribe id')
        }
        return await updateSubscribe({
          subscribe_id: subscribeId,
          ...payload,
        })
      }
      return await subscribe({
        movie_id: movieIdList[0],
        ...payload,
      })
    },
    onSuccess: (res) => {
      if (res.code === 0) {
        toast.success(res.message)
        onOpenChange(false)
        for (const queryKey of MOVIE_SUBSCRIPTION_QUERY_KEYS) {
          queryClient.invalidateQueries({ queryKey, exact: false })
        }
      }
    },
    onError: (err: Error) => {
      toast.error(`提交失败，请重试：${err}`)
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogOverlay className='bg-background/20 backdrop-blur-lg' />
      <DialogContent className='bg-background/40 backdrop-blur-lg' onOpenAutoFocus={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle>{mode === 'edit' ? '编辑订阅规则' : '订阅设置'}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((values) =>
              submitMutation.mutate(values)
            )}
            className='flex flex-col gap-6'
          >
            <FormField
              control={form.control}
              name='filter_id'
              render={({ field }) => (
                <FormItem>
                  <FormLabel className='flex items-center gap-2 text-base font-semibold'>
                    <Filter className='h-4 w-4' />
                    过滤器
                  </FormLabel>
                  <FormControl>
                    <ScrollArea className='h-50 rounded-lg border bg-background/50 p-2'>
                      <div className='grid grid-cols-1 gap-2 sm:grid-cols-2'>
                        <button
                          type='button'
                          onClick={() => field.onChange(null)}
                          className={cn(
                            'relative flex items-start gap-3 rounded-lg border p-3 text-left transition-all',
                            field.value == null
                              ? 'border-primary bg-primary/10 shadow-sm'
                              : 'border-border hover:border-primary/50 hover:bg-muted/50'
                          )}
                        >
                          <div className='min-w-0 flex-1'>
                            <div className='font-medium'>不使用过滤器</div>
                            <div className='text-xs text-muted-foreground'>
                              默认过滤
                            </div>
                          </div>
                          {field.value == null && (
                            <Check className='mt-0.5 h-4 w-4 shrink-0 text-primary' />
                          )}
                        </button>

                        {/* 过滤器列表 */}
                        {filters?.map((filter) => (
                          <button
                            key={filter.id}
                            type='button'
                            onClick={() => field.onChange(filter.id)}
                            className={cn(
                              'relative flex items-start gap-3 rounded-lg border p-3 text-left transition-all',
                              field.value === filter.id
                                ? 'border-primary bg-primary/10 shadow-sm'
                                : 'border-border hover:border-primary/50 hover:bg-muted/50'
                            )}
                          >
                            <div className='min-w-0 flex-1'>
                              <div className='mb-1.5 flex items-center gap-1.5'>
                                <span className='truncate font-medium'>
                                  {filter.filter_name}
                                </span>
                                {filter.is_default && (
                                  <Badge
                                    variant='secondary'
                                    className='h-4 shrink-0 px-1 py-0 text-[10px]'
                                  >
                                    默认
                                  </Badge>
                                )}
                              </div>

                              {/* 关键字*/}
                              {filter.keyword && (
                                <div className='mb-1 flex items-center gap-1 text-xs text-muted-foreground'>
                                  <Tag className='h-3 w-3 shrink-0' />
                                  <span className='truncate'>
                                    {filter.keyword}
                                  </span>
                                </div>
                              )}

                              <div className='mt-1 flex flex-wrap gap-1'>
                                {/* 分辨率*/}
                                {filter.resolutions &&
                                  filter.resolutions.length > 0 && (
                                    <div className='flex items-center gap-0.5'>
                                      <Maximize2 className='h-3 w-3 text-muted-foreground' />
                                      <span className='text-[10px] text-muted-foreground'>
                                        {filter.resolutions
                                          .slice(0, 2)
                                          .join('/')}
                                        {filter.resolutions.length > 2 &&
                                          `+${filter.resolutions.length - 2}`}
                                      </span>
                                    </div>
                                  )}

                                {/* 字幕 */}
                                {filter.subtitles &&
                                  filter.subtitles.length > 0 && (
                                    <div className='flex items-center gap-0.5'>
                                      <Film className='h-3 w-3 text-muted-foreground' />
                                      <span className='text-[10px] text-muted-foreground'>
                                        {filter.subtitles.slice(0, 2).join('/')}
                                        {filter.subtitles.length > 2 &&
                                          `+${filter.subtitles.length - 2}`}
                                      </span>
                                    </div>
                                  )}

                                {/* 文件大小 */}
                                {(filter.min_size || filter.max_size) && (
                                  <span className='text-[10px] text-muted-foreground'>
                                    {formatSize(filter.min_size) ?? '0'}
                                    {' ~ '}
                                    {formatSize(filter.max_size) ?? '∞'}
                                  </span>
                                )}

                                {filter.skip_in_library_check && (
                                  <Badge
                                    variant='outline'
                                    className='h-4 border-amber-500/40 px-1 py-0 text-[10px] text-amber-600'
                                  >
                                    跳过入库检测
                                  </Badge>
                                )}
                              </div>
                            </div>
                            {field.value === filter.id && (
                              <Check className='mt-0.5 h-4 w-4 shrink-0 text-primary' />
                            )}
                          </button>
                        ))}
                      </div>
                    </ScrollArea>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 选择排序器 */}
            <FormField
              control={form.control}
              name='priority_id'
              render={({ field }) => (
                <FormItem>
                  <FormLabel className='flex items-center gap-2 text-base font-semibold'>
                    <ArrowUpDown className='h-4 w-4' />
                    选择排序器
                  </FormLabel>
                  <FormControl>
                    <ScrollArea className='h-50 rounded-lg border bg-background/50 p-2'>
                      <div className='grid grid-cols-1 gap-2 sm:grid-cols-2'>
                        {/* 无排序器选项 */}
                        <button
                          type='button'
                          onClick={() => field.onChange(null)}
                          className={cn(
                            'relative flex items-start gap-3 rounded-lg border p-3 text-left transition-all',
                            field.value == null
                              ? 'border-primary bg-primary/10 shadow-sm'
                              : 'border-border hover:border-primary/50 hover:bg-muted/50'
                          )}
                        >
                          <div className='min-w-0 flex-1'>
                            <div className='font-medium'>不使用排序器</div>
                            <div className='text-xs text-muted-foreground'>
                              默认排序
                            </div>
                          </div>
                          {field.value == null && (
                            <Check className='mt-0.5 h-4 w-4 shrink-0 text-primary' />
                          )}
                        </button>

                        {/* 排序器列表 */}
                        {priorities?.map((priority) => (
                          <button
                            key={priority.id}
                            type='button'
                            onClick={() => field.onChange(priority.id)}
                            className={cn(
                              'relative flex items-start gap-3 rounded-lg border p-3 text-left transition-all',
                              field.value === priority.id
                                ? 'border-primary bg-primary/10 shadow-sm'
                                : 'border-border hover:border-primary/50 hover:bg-muted/50'
                            )}
                          >
                            <div className='min-w-0 flex-1'>
                              <div className='mb-1.5 flex items-center gap-1.5'>
                                <span className='truncate font-medium'>
                                  {priority.priority_name}
                                </span>
                                {priority.is_default && (
                                  <Badge
                                    variant='secondary'
                                    className='h-4 shrink-0 px-1 py-0 text-[10px]'
                                  >
                                    默认
                                  </Badge>
                                )}
                              </div>

                              <div className='flex flex-wrap gap-1'>
                                {/* 分辨率优先级 */}
                                {priority.resolutions &&
                                  priority.resolutions.length > 0 && (
                                    <div className='flex items-center gap-0.5'>
                                      <Maximize2 className='h-3 w-3 text-muted-foreground' />
                                      <span className='text-[10px] text-muted-foreground'>
                                        {priority.resolutions
                                          .slice(0, 2)
                                          .join('>')}
                                        {priority.resolutions.length > 2 && `+${priority.resolutions.length - 2}`}
                                      </span>
                                    </div>
                                  )}

                                {/* 字幕优先级 */}
                                {priority.subtitles &&
                                  priority.subtitles.length > 0 && (
                                    <div className='flex items-center gap-0.5'>
                                      <Film className='h-3 w-3 text-muted-foreground' />
                                      <span className='text-[10px] text-muted-foreground'>
                                        {priority.subtitles
                                          .slice(0, 2)
                                          .join('>')}
                                        {priority.subtitles.length > 2 && `+${priority.subtitles.length - 2}`}
                                      </span>
                                    </div>
                                  )}

                                {/* 排序字段 */}
                                {priority.priority_sort &&
                                  priority.priority_sort.length > 0 && (
                                    <div className='flex items-center gap-0.5'>
                                      <SlidersHorizontal className='h-3 w-3 text-muted-foreground' />
                                      <span className='text-[10px] text-muted-foreground'>
                                        {priority.priority_sort
                                          .slice(0, 2)
                                          .join(', ')}
                                        {priority.priority_sort.length > 2 &&
                                          `+${priority.priority_sort.length - 2}`}
                                      </span>
                                    </div>
                                  )}

                                {/* 马赛克过滤*/}
                                {priority.mosaic &&
                                  priority.mosaic.length > 0 && (
                                    <div className='flex items-center gap-0.5'>
                                      <Star className='h-3 w-3 text-muted-foreground' />
                                      <span className='text-[10px] text-muted-foreground'>
                                        {priority.mosaic.slice(0, 2).join('/')}
                                      </span>
                                    </div>
                                  )}
                              </div>
                            </div>
                            {field.value === priority.id && (
                              <Check className='mt-0.5 h-4 w-4 shrink-0 text-primary' />
                            )}
                          </button>
                        ))}
                      </div>
                    </ScrollArea>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name='pre_download_enabled'
              render={({ field }) => (
                <FormItem>
                  <FieldLabel>
                    <Field orientation='horizontal'>
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                      <FieldContent>
                        <FieldTitle>开启预下载</FieldTitle>
                        <FieldDescription>
                          仅影响当前这条影片订阅。未命中过滤器时会按排序器优先级预下载一次，触发后会自动关闭，订阅状态仍保持激活。
                        </FieldDescription>
                      </FieldContent>
                    </Field>
                  </FieldLabel>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 提交按钮 */}
            <div className='flex gap-2 pt-2'>
              <Button type='submit' className='flex-1'>
                {mode === 'edit' ? '保存规则' : '确认订阅'}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
