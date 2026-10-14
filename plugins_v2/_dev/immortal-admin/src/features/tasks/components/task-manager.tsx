import { useEffect, useMemo, useState } from 'react'
import * as z from 'zod'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Brush, Clock, HelpCircle, Zap } from 'lucide-react'
import { toast } from 'sonner'
import {
  addTask,
  deleteTask,
  fetchFuncList,
  getRunningTasks,
  getTasks,
  runTask,
  type ArgRule,
  type Task,
  updateTask,
} from '@/api/task.ts'
import { cn } from '@/lib/utils.ts'
import { useIsMobile } from '@/hooks/use-mobile.tsx'
import { Button } from '@/components/ui/button'
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
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch.tsx'
import { Textarea } from '@/components/ui/textarea.tsx'
import { DirectoryPicker } from '@/features/tasks/components/directory-picker.tsx'
import { TaskTableDesktop } from '@/features/tasks/components/task-table-desktop.tsx'
import { TaskTableMobile } from '@/features/tasks/components/task-table-mobile.tsx'

const taskSchema = z.object({
  task_name: z.string().min(2, '任务名称至少 2 个字符'),
  task_func: z.string().min(1, '请选择执行函数'),
  task_args: z.string(),
  task_cron: z.string().min(5, '请输入有效的 Cron 表达式'),
  enable: z.boolean(),
  push_enable: z.boolean(),
  push_title_template: z.string(),
  push_message_template: z.string(),
})

type TaskValues = z.infer<typeof taskSchema>

const defaultValues: TaskValues = {
  task_name: '',
  task_func: '',
  task_args: '',
  task_cron: '0 * * * *',
  enable: false,
  push_enable: false,
  push_title_template: '',
  push_message_template: '',
}

const pushTemplateVariables = [
  { key: '{{ task_name }}', description: '任务名称' },
  { key: '{{ task_func }}', description: '任务函数名' },
  { key: '{{ task_label }}', description: '任务函数展示名' },
  { key: '{{ task_cron }}', description: 'Cron 表达式' },
  { key: '{{ status }}', description: '执行状态标记：success / failed / empty' },
  { key: '{{ status_text }}', description: '执行状态文本：成功 / 失败' },
  { key: '{{ duration_seconds }}', description: '执行耗时，单位秒' },
  { key: '{{ start_time }}', description: '开始时间，格式化文本' },
  { key: '{{ end_time }}', description: '结束时间，格式化文本' },
  { key: '{{ error_last_line }}', description: '异常最后一行' },
  { key: '{{ summary_text }}', description: '默认摘要文本' },
  { key: '{{ result_json }}', description: '执行结果 JSON 字符串' },
  { key: '{{ task_args_json }}', description: '任务参数 JSON 字符串' },
  { key: '{{ args.xxx }} / {{ task_args.xxx }}', description: '任务参数对象访问方式' },
  { key: '{{ arg_xxx }}', description: '任务参数会额外注入 arg_ 前缀字段' },
  { key: '{{ result.xxx }}', description: '结果对象访问方式' },
  { key: '{{ count }} / {{ message }}', description: '结果为 dict 时，顶层字段会尽量直接展开' },
  { key: '{{ result_xxx }}', description: '结果对象会额外注入 result_ 前缀字段' },
  { key: '{{ target_dir }}', description: '清理任务中的目标目录' },
  { key: '{{ arg_min_age_hours }} / {{ arg_max_age_hours }}', description: '清理任务的文件年龄范围参数（单位小时）' },
  { key: '{{ scanned_count }} / {{ matched_count }} / {{ selected_count }}', description: '扫描、匹配、最终处理数量' },
  { key: '{{ deleted_count }} / {{ freed_bytes }}', description: '实际删除数量与释放字节数' },
]

const isRuleRequired = (rule: ArgRule) => rule.required ?? rule.require ?? false

const defaultPushMessageTemplate = `任务: {{ task_name }}
状态: {{ status_text }}
耗时: {{ duration_seconds }}s

{% if count is defined %}数量: {{ count }}
{% endif %}{% if saved_count is defined %}保存数: {{ saved_count }}
{% endif %}{% if completed is defined %}完成数: {{ completed }}
{% endif %}{% if failed is defined %}失败数: {{ failed }}
{% endif %}{% if success_count is defined %}成功数: {{ success_count }}
{% endif %}{% if fail_count is defined %}失败数: {{ fail_count }}
{% endif %}{% if total is defined %}总数: {{ total }}
{% endif %}{% if message is defined and message %}说明: {{ message }}
{% endif %}{% if error_last_line %}错误: {{ error_last_line }}
{% endif %}`

export default function TaskManager() {
  const [editingTask, setEditingTask] = useState<Task | null>(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [isTemplateHelpOpen, setIsTemplateHelpOpen] = useState(false)
  const [dynamicArgs, setDynamicArgs] = useState<Record<string, string | string[] | boolean>>({})
  const [submittingTaskIds, setSubmittingTaskIds] = useState<number[]>([])
  const queryClient = useQueryClient()
  const isMobile = useIsMobile()

  const { data: tasks, isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: async () => {
      const res = await getTasks()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const { data: taskFunctions } = useQuery({
    queryKey: ['taskFunc'],
    queryFn: async () => {
      const res = await fetchFuncList()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const { data: runningTaskData } = useQuery({
    queryKey: ['task-running'],
    queryFn: async () => {
      const res = await getRunningTasks()
      return res.data
    },
    refetchInterval: 2000,
    staleTime: 0,
  })

  const saveTaskMutation = useMutation({
    mutationFn: async (values: TaskValues) => {
      if (editingTask) {
        return updateTask({ ...values, id: editingTask.id })
      }
      return addTask({ ...values, id: 0 })
    },
    onSuccess: (res) => {
      if (res.code !== 0) return
      toast.success(res.message)
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      setIsFormOpen(false)
      setEditingTask(null)
    },
  })

  const deleteTaskMutation = useMutation({
    mutationFn: deleteTask,
    onSuccess: (res) => {
      toast.success(res.message)
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const form = useForm<TaskValues>({
    resolver: zodResolver(taskSchema),
    defaultValues,
  })

  const selectedFunc = useWatch({
    control: form.control,
    name: 'task_func',
  })
  const pushEnabled = useWatch({
    control: form.control,
    name: 'push_enable',
  })

  useEffect(() => {
    if (!isFormOpen || !pushEnabled) {
      setIsTemplateHelpOpen(false)
    }
  }, [isFormOpen, pushEnabled])

  const selectedTaskFunc = useMemo(
    () => taskFunctions?.find((item) => item.func_name === selectedFunc),
    [selectedFunc, taskFunctions]
  )
  const funcArgRules = useMemo(
    () => selectedTaskFunc?.func_args_rule ?? [],
    [selectedTaskFunc]
  )
  const hasCoreArgs = Boolean(selectedTaskFunc?.func_args?.length || funcArgRules.length)

  const runningTaskIds = useMemo(() => {
    const ids = new Set<number>(runningTaskData?.task_ids ?? [])
    submittingTaskIds.forEach((id) => ids.add(id))
    return Array.from(ids)
  }, [runningTaskData?.task_ids, submittingTaskIds])

  useEffect(() => {
    if (!funcArgRules.length) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDynamicArgs((prev) => (Object.keys(prev).length === 0 ? prev : {}))
      return
    }

    let existing: Record<string, unknown> = {}
    try {
      existing = JSON.parse(form.getValues('task_args') || '{}')
    } catch {
      existing = {}
    }

    const initial: Record<string, string | string[] | boolean> = {}
    funcArgRules.forEach((rule) => {
      if (rule.type === 'multi-select') {
        const values = (existing[rule.key] as string[]) ?? []
        initial[rule.key] = values.filter((v) => rule.options?.some((opt) => opt.value === v))
        return
      }
      if (rule.type === 'select') {
        const rawValue = existing[rule.key]
        if (Array.isArray(rawValue)) {
          initial[rule.key] = String(rawValue[0] ?? '')
          return
        }
        initial[rule.key] = String(rawValue ?? '')
        return
      }
      if (rule.type === 'boolean') {
        const rawValue = existing[rule.key]
        initial[rule.key] = rawValue === true || rawValue === 'true' || rawValue === 1 || rawValue === '1'
        return
      }
      initial[rule.key] = String(existing[rule.key] ?? '')
    })
    setDynamicArgs(initial)
  }, [form, funcArgRules, selectedFunc])

  useEffect(() => {
    if (!hasCoreArgs) {
      form.setValue('task_args', '')
      return
    }
    if (!funcArgRules.length) return
    form.setValue('task_args', JSON.stringify(dynamicArgs))
  }, [dynamicArgs, form, funcArgRules.length, hasCoreArgs])

  useEffect(() => {
    if (editingTask) {
      form.reset({
        ...defaultValues,
        ...editingTask,
        push_title_template: editingTask.push_title_template ?? '',
        push_message_template: editingTask.push_message_template ?? '',
      })
      return
    }
    if (isFormOpen) {
      form.reset(defaultValues)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDynamicArgs({})
    }
  }, [editingTask, form, isFormOpen])

  const handleDelete = (id: number) => {
    deleteTaskMutation.mutate(id)
  }

  const handleRunTask = async (taskId: number) => {
    if (runningTaskIds.includes(taskId)) return

    setSubmittingTaskIds((prev) => (prev.includes(taskId) ? prev : [...prev, taskId]))
    try {
      const res = await runTask(taskId)
      if (res.code === 0) {
        toast.success(res.message)
        await queryClient.refetchQueries({ queryKey: ['task-running'] })
        return
      }
      toast.error(res.message || '任务执行失败')
    } catch (error) {
      const message = error instanceof Error ? error.message : '任务执行失败'
      toast.error(message)
    } finally {
      setSubmittingTaskIds((prev) => prev.filter((id) => id !== taskId))
    }
  }

  return (
    <div className='flex h-full flex-col space-y-2 overflow-hidden'>
      <div className='shrink-0'>
        <div className='flex items-center justify-between rounded-2xl border p-4 shadow-sm'>
          <div className='space-y-1'>
            <p className='flex items-center gap-1 text-xs text-muted-foreground'>
              <Zap className='h-3 w-3 fill-amber-500 text-amber-500' />
              当前激活任务：{tasks?.filter((item) => item.enable).length || 0}
            </p>
          </div>

          <Dialog open={isFormOpen} onOpenChange={setIsFormOpen}>
            <DialogOverlay className='bg-background/20 backdrop-blur-lg' />
            <DialogTrigger asChild>
              <Button variant='outline' onClick={() => setEditingTask(null)}>
                <Brush />
                铭刻阵纹
              </Button>
            </DialogTrigger>
            <DialogContent
              onOpenAutoFocus={(event) => event.preventDefault()}
              className='scrollbar-hide overflow-auto bg-background/40 backdrop-blur-lg'
            >
              <DialogHeader>
                <DialogTitle>{editingTask ? '编辑阵纹' : '创建阵纹'}</DialogTitle>
              </DialogHeader>

              <Form {...form}>
                <form
                  onSubmit={form.handleSubmit((values) => saveTaskMutation.mutate(values))}
                  className='space-y-4'
                >
                  <FormField
                    control={form.control}
                    name='task_name'
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>任务名称</FormLabel>
                        <FormControl>
                          <Input placeholder='输入任务名称' {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name='task_func'
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>任务核心</FormLabel>
                        <FormControl>
                          <Select onValueChange={field.onChange} value={field.value}>
                            <SelectTrigger className='w-full'>
                              <SelectValue placeholder='选择任务核心' />
                            </SelectTrigger>
                            <SelectContent className='w-full bg-background/20 backdrop-blur-md'>
                              {taskFunctions?.map((item) => (
                                <SelectItem key={item.func_name} value={item.func_name}>
                                  {item.func_label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {hasCoreArgs && (
                    <FormField
                      control={form.control}
                      name='task_args'
                      render={() => (
                        <FormItem>
                          <FormLabel>核心参数</FormLabel>
                          {funcArgRules.length ? (
                            <div className='space-y-3 rounded-md border p-3'>
                              {funcArgRules.map((rule) => (
                                <div key={rule.key} className='space-y-1'>
                                  <div className='flex items-center gap-1 text-sm'>
                                    <span>{rule.label}</span>
                                    {isRuleRequired(rule) && <span className='text-destructive'>*</span>}
                                  </div>

                                  {rule.type === 'string' && (
                                    <Input
                                      value={(dynamicArgs[rule.key] as string) ?? ''}
                                      onChange={(event) =>
                                        setDynamicArgs((prev) => ({ ...prev, [rule.key]: event.target.value }))
                                      }
                                      placeholder={rule.placeholder ?? `请输入${rule.label}`}
                                    />
                                  )}

                                  {rule.type === 'directory' && (
                                    <DirectoryPicker
                                      value={String(dynamicArgs[rule.key] ?? '')}
                                      onChange={(value) =>
                                        setDynamicArgs((prev) => ({ ...prev, [rule.key]: value }))
                                      }
                                      placeholder={rule.placeholder ?? `请选择${rule.label}`}
                                    />
                                  )}

                                  {rule.type === 'number' && (
                                    <Input
                                      type='number'
                                      value={(dynamicArgs[rule.key] as string) ?? ''}
                                      onChange={(event) =>
                                        setDynamicArgs((prev) => ({ ...prev, [rule.key]: event.target.value }))
                                      }
                                      placeholder={rule.placeholder ?? `请输入${rule.label}`}
                                    />
                                  )}

                                  {rule.type === 'select' && (
                                    <Select
                                      value={String(dynamicArgs[rule.key] ?? '')}
                                      onValueChange={(value) =>
                                        setDynamicArgs((prev) => ({ ...prev, [rule.key]: value }))
                                      }
                                    >
                                      <SelectTrigger className='w-full'>
                                        <SelectValue placeholder={rule.placeholder ?? `请选择${rule.label}`} />
                                      </SelectTrigger>
                                      <SelectContent className='w-full bg-background/20 backdrop-blur-md'>
                                        {rule.options?.map((opt) => (
                                          <SelectItem key={opt.value} value={opt.value}>
                                            {opt.label}
                                          </SelectItem>
                                        ))}
                                      </SelectContent>
                                    </Select>
                                  )}

                                  {rule.type === 'boolean' && (
                                    <div className='flex justify-end'>
                                      <Switch
                                        checked={Boolean(dynamicArgs[rule.key])}
                                        onCheckedChange={(checked) =>
                                          setDynamicArgs((prev) => ({ ...prev, [rule.key]: checked }))
                                        }
                                      />
                                    </div>
                                  )}

                                  {rule.type === 'multi-select' && (
                                    <div className='flex flex-wrap gap-2'>
                                      {rule.options?.map((opt) => {
                                        const selected = ((dynamicArgs[rule.key] as string[]) ?? []).includes(opt.value)
                                        return (
                                          <Button
                                            key={opt.value}
                                            type='button'
                                            size='sm'
                                            variant={selected ? 'default' : 'outline'}
                                            className={cn(
                                              'transition-all duration-150 active:scale-95',
                                              selected
                                                ? 'scale-105 shadow-sm'
                                                : 'border-dashed opacity-60 hover:opacity-90'
                                            )}
                                            onClick={() => {
                                              setDynamicArgs((prev) => {
                                                const current = (prev[rule.key] as string[]) ?? []
                                                return {
                                                  ...prev,
                                                  [rule.key]: selected
                                                    ? current.filter((value) => value !== opt.value)
                                                    : [...current, opt.value],
                                                }
                                              })
                                            }}
                                          >
                                            {opt.label}
                                          </Button>
                                        )
                                      })}
                                    </div>
                                  )}

                                  {rule.description && (
                                    <p className='text-xs text-muted-foreground'>{rule.description}</p>
                                  )}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <FormControl>
                              <Textarea {...form.register('task_args')} placeholder='{"arg_name":"arg_value"}' />
                            </FormControl>
                          )}
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}

                  <FormField
                    control={form.control}
                    name='task_cron'
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>运行周期</FormLabel>
                        <FormControl>
                          <div className='relative'>
                            <Input {...field} />
                            <Clock className='absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
                          </div>
                        </FormControl>
                        <FormDescription>
                          <span className='rounded bg-muted px-1.5 py-0.5 italic'>*/5 * * * *（每 5 分钟）</span>
                          <span className='ml-2 rounded bg-muted px-1.5 py-0.5 italic'>0 0 * * *（每天）</span>
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name='enable'
                    render={({ field }) => (
                      <FormItem className='flex items-center justify-between'>
                        <FormLabel>启用任务</FormLabel>
                        <FormControl>
                          <Switch checked={field.value} onCheckedChange={field.onChange} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name='push_enable'
                    render={({ field }) => (
                      <FormItem className='flex items-center justify-between'>
                        <div className='space-y-1'>
                          <FormLabel>启用推送</FormLabel>
                          <FormDescription>任务执行后可作为是否推送的配置开关。</FormDescription>
                        </div>
                        <FormControl>
                          <Switch checked={field.value} onCheckedChange={field.onChange} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {pushEnabled && (
                    <div className='space-y-4 rounded-lg border p-4'>
                      <div className='space-y-3 rounded-md border bg-muted/20 p-3'>
                        <div className='flex items-start justify-between gap-3'>
                          <div className='space-y-1'>
                            <p className='text-sm font-medium'>推送模板</p>
                            <p className='text-xs text-muted-foreground'>
                              支持使用 Jinja 变量，留空时会回退到系统默认模板。
                            </p>
                          </div>
                          <Button
                            type='button'
                            variant='outline'
                            size='sm'
                            className='shrink-0'
                            onClick={() => setIsTemplateHelpOpen((prev) => !prev)}
                          >
                            <HelpCircle className='h-4 w-4' />
                            可用字段
                          </Button>
                        </div>

                        {isTemplateHelpOpen && (
                          <div className='max-h-96 space-y-4 overflow-y-auto overscroll-contain rounded-md border bg-background/95 p-4 text-sm shadow-sm touch-pan-y'>
                            <div className='space-y-1'>
                              <p className='font-medium'>可用字段说明</p>
                              <p className='text-xs text-muted-foreground'>
                                下面这些变量可以直接写进标题或正文模板，系统会在任务执行后自动替换成真实内容。
                              </p>
                            </div>

                            <div className='grid gap-2 rounded-md border bg-muted/30 p-3 text-xs'>
                              {pushTemplateVariables.map((item) => (
                                <div key={item.key} className='grid gap-1 md:grid-cols-[220px_1fr]'>
                                  <code className='break-all text-[11px]'>{item.key}</code>
                                  <span className='text-muted-foreground'>{item.description}</span>
                                </div>
                              ))}
                            </div>

                            <div className='space-y-3'>
                              <div className='space-y-2'>
                                <p className='text-xs font-medium'>正文默认模板</p>
                                <pre className='rounded-md border bg-muted/30 p-3 text-[11px] whitespace-pre-wrap'>
                                  {defaultPushMessageTemplate}
                                </pre>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>


                      <FormField
                        control={form.control}
                        name='push_message_template'
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>推送正文模板</FormLabel>
                            <FormControl>
                              <Textarea
                                {...field}
                                rows={8}
                                placeholder={defaultPushMessageTemplate}
                              />
                            </FormControl>
                            <FormDescription>留空时使用默认正文模板。</FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  )}

                  <Button type='submit' disabled={saveTaskMutation.isPending} className='w-full'>
                    {saveTaskMutation.isPending ? '保存中...' : '保存配置'}
                  </Button>
                </form>
              </Form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className='scrollbar-hide flex-1 overflow-auto' data-main-scroll-container>
        {isMobile ? (
          <TaskTableMobile
            data={tasks}
            isLoading={isLoading}
            onRun={handleRunTask}
            runningTaskIds={runningTaskIds}
            onDelete={handleDelete}
            onEdit={(task) => {
              setEditingTask(task)
              setIsFormOpen(true)
            }}
          />
        ) : (
          <TaskTableDesktop
            data={tasks}
            isLoading={isLoading}
            onRun={handleRunTask}
            runningTaskIds={runningTaskIds}
            onDelete={handleDelete}
            onEdit={(task) => {
              setEditingTask(task)
              setIsFormOpen(true)
            }}
          />
        )}
      </div>
    </div>
  )
}
