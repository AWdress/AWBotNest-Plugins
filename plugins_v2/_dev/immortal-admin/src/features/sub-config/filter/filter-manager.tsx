import { useEffect, useState } from 'react'
import * as z from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { SlidersHorizontal } from 'lucide-react'
import { toast } from 'sonner'
import {
  listFilter,
  addFilter,
  updateFilter,
  deleteFilter,
  type Filter,
} from '@/api/filter.ts'
import { useIsMobile } from '@/hooks/use-mobile.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Checkbox } from '@/components/ui/checkbox.tsx'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogOverlay,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog.tsx'
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldLabel,
  FieldTitle,
} from '@/components/ui/field.tsx'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.tsx'
import { Input } from '@/components/ui/input.tsx'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group.tsx'
import { FilterTableDesktop } from '@/features/sub-config/filter/filter-table-desktop.tsx'
import { FilterTableMobile } from '@/features/sub-config/filter/filter-table-mobile.tsx'

// ── Constants ──────────────────────────────────────────────────────────────────
const RESOLUTION_OPTIONS = ['1080p', '4K', '8K']
const SUBTITLE_OPTIONS = ['中文']
const MOSAIC_OPTIONS = ['有码', '无码流出', '新模型','无码破解']

// ── Schema ─────────────────────────────────────────────────────────────────────
const formSchema = z.object({
  id: z.number().optional(),
  filter_name: z.string().min(1, '请输入过滤器名称'),
  keyword: z.string().optional(),
  regex: z.string().optional(),
  resolutions: z.array(z.string()).optional(),
  subtitles: z.array(z.string()).optional(),
  mosaic: z.array(z.string()).optional(),
  min_size: z.number().nullable().optional(),
  max_size: z.number().nullable().optional(),
  skip_in_library_check: z.boolean(),
  enable_pre_download: z.boolean(),
  is_default: z.boolean(),
})

type FormValues = z.infer<typeof formSchema>

const defaultValues: FormValues = {
  filter_name: '',
  keyword: '',
  regex: '',
  resolutions: [],
  subtitles: [],
  mosaic: [],
  min_size: undefined,
  max_size: undefined,
  skip_in_library_check: false,
  enable_pre_download: false,
  is_default: false,
}

// ── Component ──────────────────────────────────────────────────────────────────
export function FilterManager() {
  const [editFilter, setEditFilter] = useState<Filter | null>(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const isMobile = useIsMobile()
  const queryClient = useQueryClient()

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['filters'],
    queryFn: async () => {
      const res = await listFilter()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (editFilter) {
      form.reset({
        ...defaultValues,
        ...editFilter,
        skip_in_library_check: Boolean(editFilter.skip_in_library_check),
        enable_pre_download: Boolean(editFilter.enable_pre_download),
      })
    } else if (isFormOpen) {
      form.reset(defaultValues)
    }
  }, [editFilter, form, isFormOpen])

  const handleDelete = async (id: number) => {
    const res = await deleteFilter(id)
    if (res.code === 0) {
      toast.success(res.message)
      queryClient.invalidateQueries({ queryKey: ['filters'] })
    }
  }

  const handleSubmit = async (values: FormValues) => {
    if (editFilter) {
      const res = await updateFilter(values as Filter)
      if (res.code === 0) {
        toast.success(res.message)
        queryClient.invalidateQueries({ queryKey: ['filters'] })
        setIsFormOpen(false)
      }
    } else {
      const res = await addFilter(values as Filter)
      if (res.code === 0) {
        toast.success(res.message)
        queryClient.invalidateQueries({ queryKey: ['filters'] })
        setIsFormOpen(false)
      }
    }
  }

  return (
    <>
      <Dialog open={isFormOpen} onOpenChange={setIsFormOpen}>
        <DialogOverlay className='bg-background/20 backdrop-blur-lg' />
        <DialogTrigger asChild>
          <Button onClick={() => setEditFilter(null)} variant='outline'>
            <SlidersHorizontal />
            新建过滤器
          </Button>
        </DialogTrigger>
        <DialogContent
          className='bg-background/40 backdrop-blur-lg'
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>
              {editFilter ? '编辑过滤器' : '新建过滤器'}
            </DialogTitle>
          </DialogHeader>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(handleSubmit)}
              className='space-y-4'
            >
              {/* 名称 */}
              <FormField
                control={form.control}
                name='filter_name'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>名称</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder='过滤器名称' />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 关键词 */}
              <FormField
                control={form.control}
                name='keyword'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>关键词（可选）</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder='标题包含关键词' />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name='regex'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>正则（可选）</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        placeholder='匹配 section / category / title / website'
                      />
                    </FormControl>
                    <FieldDescription>
                      后端会对资源的分区、分类、标题和网站执行正则匹配。
                    </FieldDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 分辨率 */}
              <FormField
                control={form.control}
                name='resolutions'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>分辨率</FormLabel>
                    <FormControl>
                      <ToggleGroup
                        type='multiple'
                        variant='outline'
                        spacing={2}
                        value={field.value ?? []}
                        onValueChange={field.onChange}
                      >
                        {RESOLUTION_OPTIONS.map((r) => (
                          <ToggleGroupItem
                            key={r}
                            value={r}
                            className='h-8 px-3 text-xs'
                          >
                            {r}
                          </ToggleGroupItem>
                        ))}
                      </ToggleGroup>
                    </FormControl>
                  </FormItem>
                )}
              />

              {/* 字幕 */}
              <FormField
                control={form.control}
                name='subtitles'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>字幕</FormLabel>
                    <FormControl>
                      <ToggleGroup
                        type='multiple'
                        variant='outline'
                        spacing={2}
                        value={field.value ?? []}
                        onValueChange={field.onChange}
                      >
                        {SUBTITLE_OPTIONS.map((s) => (
                          <ToggleGroupItem
                            key={s}
                            value={s}
                            className='h-8 px-3 text-xs'
                          >
                            {s}
                          </ToggleGroupItem>
                        ))}
                      </ToggleGroup>
                    </FormControl>
                  </FormItem>
                )}
              />

              {/* 类型 */}
              <FormField
                control={form.control}
                name='mosaic'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>马赛克</FormLabel>
                    <FormControl>
                      <ToggleGroup
                        type='multiple'
                        variant='outline'
                        spacing={2}
                        value={field.value ?? []}
                        onValueChange={field.onChange}
                      >
                        {MOSAIC_OPTIONS.map((m) => (
                          <ToggleGroupItem
                            key={m}
                            value={m}
                            className='h-8 px-3 text-xs'
                          >
                            {m}
                          </ToggleGroupItem>
                        ))}
                      </ToggleGroup>
                    </FormControl>
                  </FormItem>
                )}
              />

              {/* 体积范围 */}
              <div className='grid grid-cols-2 gap-3'>
                <FormField
                  control={form.control}
                  name='min_size'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>最小体积 (MB)</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type='number'
                          min={0}
                          placeholder='不限'
                          value={field.value ?? ''}
                          onChange={(e) =>
                            field.onChange(
                              e.target.value === ''
                                ? undefined
                                : Number(e.target.value)
                            )
                          }
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='max_size'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>最大体积 (MB)</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type='number'
                          min={0}
                          placeholder='不限'
                          value={field.value ?? ''}
                          onChange={(e) =>
                            field.onChange(
                              e.target.value === ''
                                ? undefined
                                : Number(e.target.value)
                            )
                          }
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* 默认 */}
              <FormField
                control={form.control}
                name='enable_pre_download'
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
                            仅影响榜单订阅、演员订阅和 TG/Discord
                            等自动订阅；不会自动同步到手动新建或编辑的影片订阅。
                          </FieldDescription>
                        </FieldContent>
                      </Field>
                    </FieldLabel>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name='skip_in_library_check'
                render={({ field }) => (
                  <FormItem className='flex items-center gap-2 space-y-0'>
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormLabel className='cursor-pointer font-normal'>
                      跳过在库检测
                    </FormLabel>
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name='is_default'
                render={({ field }) => (
                  <FormItem className='flex items-center gap-2 space-y-0'>
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormLabel className='cursor-pointer font-normal'>
                      设为默认过滤器
                    </FormLabel>
                  </FormItem>
                )}
              />

              <Button type='submit' className='w-full'>
                提交
              </Button>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {isMobile ? (
        <FilterTableMobile
          data={data}
          onEdit={(item) => {
            setEditFilter(item)
            setIsFormOpen(true)
          }}
          onDelete={(id) => handleDelete(id)}
          isLoading={isLoading}
        />
      ) : (
        <FilterTableDesktop
          data={data}
          onEdit={(item) => {
            setEditFilter(item)
            setIsFormOpen(true)
          }}
          onDelete={(id) => handleDelete(id)}
          isLoading={isLoading}
        />
      )}
    </>
  )
}
