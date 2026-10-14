import { useEffect, useState } from 'react'
import * as z from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpDown } from 'lucide-react'
import { toast } from 'sonner'
import {
  listPriority,
  addPriority,
  updatePriority,
  deletePriority,
  type Priority,
} from '@/api/priority.ts'
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
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.tsx'
import { Input } from '@/components/ui/input.tsx'
import { DraggableTagSelector } from '@/components/draggable-tag-selector.tsx'
import { PriorityTableDesktop } from '@/features/sub-config/priority/priority-table-desktop.tsx'
import { PriorityTableMobile } from '@/features/sub-config/priority/priority-table-mobile.tsx'

// ── Constants ──────────────────────────────────────────────────────────────────
const RESOLUTION_OPTIONS = ['1080p', '4K', '8K']
const SUBTITLE_OPTIONS = ['中文']
const MOSAIC_OPTIONS = ['有码', '无码流出', '新模型', '无码破解']
const SORT_OPTIONS = ['字幕', '马赛克', '分辨率']

// ── Schema ─────────────────────────────────────────────────────────────────────
const formSchema = z.object({
  id: z.number().optional(),
  priority_name: z.string().min(1, '请输入优先级名称'),
  resolutions: z.array(z.string()),
  subtitles: z.array(z.string()),
  mosaic: z.array(z.string()),
  priority_sort: z.array(z.string()),
  is_default: z.boolean(),
})

type FormValues = z.infer<typeof formSchema>

const defaultValues: FormValues = {
  priority_name: '',
  resolutions: [],
  subtitles: [],
  mosaic: [],
  priority_sort: [],
  is_default: false,
}

// ── Component ──────────────────────────────────────────────────────────────────
export default function PriorityManager() {
  const [editPriority, setEditPriority] = useState<Priority | null>(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const isMobile = useIsMobile()
  const queryClient = useQueryClient()

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['priorities'],
    queryFn: async () => {
      const res = await listPriority()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (editPriority) {
      form.reset(editPriority)
    } else if (isFormOpen) {
      form.reset(defaultValues)
    }
  }, [editPriority, form, isFormOpen])

  const handleDelete = async (id: number) => {
    const res = await deletePriority(id)
    if (res.code === 0) {
      toast.success(res.message)
      queryClient.invalidateQueries({ queryKey: ['priorities'] })
    }
  }

  const handleSubmit = async (values: FormValues) => {
    if (editPriority) {
      const res = await updatePriority(values as Priority)
      if (res.code === 0) {
        toast.success(res.message)
        queryClient.invalidateQueries({ queryKey: ['priorities'] })
        setIsFormOpen(false)
      }
    } else {
      const res = await addPriority(values as Priority)
      if (res.code === 0) {
        toast.success(res.message)
        queryClient.invalidateQueries({ queryKey: ['priorities'] })
        setIsFormOpen(false)
      }
    }
  }

  return (
    <>
      <Dialog open={isFormOpen} onOpenChange={setIsFormOpen}>
        <DialogOverlay className='bg-background/20 backdrop-blur-lg' />
        <DialogTrigger asChild>
          <Button onClick={() => setEditPriority(null)} variant='outline'>
            <ArrowUpDown />
            新建优先级
          </Button>
        </DialogTrigger>
        <DialogContent
          className='bg-background/40 backdrop-blur-lg'
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>
              {editPriority ? '编辑优先级' : '新建优先级'}
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
                name='priority_name'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>名称</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder='优先级名称' />
                    </FormControl>
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
                      <DraggableTagSelector
                        options={RESOLUTION_OPTIONS}
                        value={field.value}
                        onChange={field.onChange}
                        placeholder='暂未选择分辨率'
                        addLabel='添加'
                      />
                    </FormControl>
                    <FormMessage />
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
                      <DraggableTagSelector
                        options={SUBTITLE_OPTIONS}
                        value={field.value}
                        onChange={field.onChange}
                        placeholder='暂未选择字幕'
                        addLabel='添加'
                      />
                    </FormControl>
                    <FormMessage />
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
                      <DraggableTagSelector
                        options={MOSAIC_OPTIONS}
                        value={field.value}
                        onChange={field.onChange}
                        placeholder='暂未选择马赛克'
                        addLabel='添加'
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 排序维度 */}
              <FormField
                control={form.control}
                name='priority_sort'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>排序维度</FormLabel>
                    <FormControl>
                      <DraggableTagSelector
                        options={SORT_OPTIONS}
                        value={field.value}
                        onChange={field.onChange}
                        placeholder='暂未设置排序维度'
                        addLabel='添加维度'
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 默认 */}
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
                      设为默认优先级
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
        <PriorityTableMobile
          data={data}
          onEdit={(item) => {
            setEditPriority(item)
            setIsFormOpen(true)
          }}
          onDelete={(id) => handleDelete(id)}
          isLoading={isLoading}
        />
      ) : (
        <PriorityTableDesktop
          data={data}
          onEdit={(item) => {
            setEditPriority(item)
            setIsFormOpen(true)
          }}
          onDelete={(id) => handleDelete(id)}
          isLoading={isLoading}
        />
      )}
    </>
  )
}
