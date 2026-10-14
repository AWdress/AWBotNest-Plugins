import { type WheelEvent, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Check,
  ChevronDown,
  CircleX,
  Loader2,
  MoreVertical,
  Pause,
  Pencil,
  Plus,
  StepForward,
} from 'lucide-react'
import { toast } from 'sonner'
import { listFilter } from '@/api/filter.ts'
import { listPriority } from '@/api/priority.ts'
import {
  DEFAULT_SUBSCRIBE_PREFERENCE_CONFIG,
  getSubscribePreferenceConfig,
  SUBSCRIBE_PREFERENCE_CONFIG_QUERY_KEY,
} from '@/api/subscribe-preference.ts'
import {
  cancelGeneralSubscribe,
  fetchGeneralSubscribeOptions,
  fetchGeneralSubscribesPage,
  pauseGeneralSubscribe,
  resumeGeneralSubscribe,
  subscribeGeneral,
  updateGeneralSubscribe,
  type GeneralSubscribeItem,
} from '@/api/subscribe.ts'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card } from '@/components/ui/card.tsx'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogTitle,
} from '@/components/ui/dialog.tsx'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu.tsx'
import { Input } from '@/components/ui/input.tsx'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.tsx'
import { Switch } from '@/components/ui/switch.tsx'
import { EmptyState } from '@/components/empty.tsx'

type GeneralSubscribeFormState = {
  numberPrefix: string
  publisher: string
  series: string
  producer: string
  genresText: string
  maxCoactors: string
  earliestReleaseDate: string
  excludeVr: boolean
  filterId: string
  priorityId: string
}

type GeneralSubscribeAction = 'pause' | 'resume' | 'cancel'
type GeneralSubscribeDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  subscribeItem?: GeneralSubscribeItem | null
  filters: Awaited<ReturnType<typeof listFilter>>['data'] | undefined
  priorities: Awaited<ReturnType<typeof listPriority>>['data'] | undefined
  defaultFilterId?: number
  defaultPriorityId?: number
}

const STATUS_LABEL_MAP: Record<GeneralSubscribeItem['status'], string> = {
  active: '订阅中',
  paused: '已暂停',
  canceled: '已取消',
}

const STATUS_CLASS_MAP: Record<GeneralSubscribeItem['status'], string> = {
  active: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600',
  paused: 'border-amber-500/30 bg-amber-500/10 text-amber-600',
  canceled: 'border-border bg-muted text-muted-foreground',
}

function normalizeGenresInput(value: string) {
  const seen = new Set<string>()
  return value
    .split(/[，,]/)
    .map((item) => item.trim())
    .filter((item) => {
      if (!item) return false
      const key = item.toLocaleLowerCase()
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
}

function createInitialState(
  item?: GeneralSubscribeItem | null,
  defaultFilterId?: number,
  defaultPriorityId?: number
): GeneralSubscribeFormState {
  return {
    numberPrefix: item?.number_prefix || '',
    publisher: item?.publisher || '',
    series: item?.series || '',
    producer: item?.producer || '',
    genresText: item?.genres?.join(', ') || '',
    maxCoactors:
      item?.max_coactors === null || item?.max_coactors === undefined
        ? ''
        : String(item.max_coactors),
    earliestReleaseDate: item?.earliest_release_date || '',
    excludeVr: item?.exclude_vr || false,
    filterId:
      item?.filter_id !== null && item?.filter_id !== undefined
        ? String(item.filter_id)
        : defaultFilterId
          ? String(defaultFilterId)
          : 'none',
    priorityId:
      item?.priority_id !== null && item?.priority_id !== undefined
        ? String(item.priority_id)
        : defaultPriorityId
          ? String(defaultPriorityId)
          : 'none',
  }
}

type SearchableSingleSelectProps = {
  value: string
  options: string[]
  placeholder: string
  searchPlaceholder: string
  emptyText: string
  onChange: (value: string) => void
}

function SearchableSingleSelect({
  value,
  options,
  placeholder,
  searchPlaceholder,
  emptyText,
  onChange,
}: SearchableSingleSelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const listRef = useRef<HTMLDivElement | null>(null)

  const normalizedOptions = useMemo(() => {
    const seen = new Set<string>()
    return [value, ...options]
      .map((item) => item.trim())
      .filter((item) => {
        if (!item) return false
        const key = item.toLocaleLowerCase()
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
  }, [options, value])

  const trimmedQuery = query.trim()

  const filteredOptions = useMemo(() => {
    const keyword = trimmedQuery.toLocaleLowerCase()
    if (!keyword) {
      return normalizedOptions
    }
    return normalizedOptions.filter((item) =>
      item.toLocaleLowerCase().includes(keyword)
    )
  }, [normalizedOptions, trimmedQuery])

  const canUseCustomValue =
    trimmedQuery.length > 0 &&
    !normalizedOptions.some(
      (item) => item.toLocaleLowerCase() === trimmedQuery.toLocaleLowerCase()
    )

  const handleListWheel = (event: WheelEvent<HTMLDivElement>) => {
    const element = event.currentTarget
    if (element.scrollHeight <= element.clientHeight) {
      return
    }
    event.stopPropagation()
  }

  const panel = (
    <div className='absolute top-full left-0 z-50 mt-2 w-full min-w-0 max-w-full overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md'>
      <div className='border-b p-2'>
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={searchPlaceholder}
          className='h-9'
        />
      </div>
      <div
        ref={listRef}
        onWheel={handleListWheel}
        className='max-h-[min(60vh,18rem)] w-full min-w-0 max-w-full overflow-x-hidden overflow-y-auto overscroll-contain p-1'
      >
        {canUseCustomValue ? (
          <button
            type='button'
            onClick={() => {
              onChange(trimmedQuery)
              setOpen(false)
              setQuery('')
            }}
            className='hover:bg-accent hover:text-accent-foreground flex w-full min-w-0 max-w-full overflow-hidden rounded-sm px-2 py-1.5 text-left text-sm'
          >
            <span className='min-w-0 flex-1 truncate'>使用 “{trimmedQuery}”</span>
          </button>
        ) : null}
        {filteredOptions.length === 0 && !canUseCustomValue ? (
          <div className='py-6 text-center text-sm text-muted-foreground'>
            {emptyText}
          </div>
        ) : null}
        {filteredOptions.map((option) => (
          <button
            key={option}
            type='button'
            onClick={() => {
              onChange(option)
              setOpen(false)
              setQuery('')
            }}
            className='hover:bg-accent hover:text-accent-foreground flex w-full min-w-0 max-w-full overflow-hidden rounded-sm px-2 py-1.5 text-left text-sm'
          >
            <span className='min-w-0 flex-1 truncate'>{option}</span>
          </button>
        ))}
      </div>
    </div>
  )

  return (
    <div className='relative w-full min-w-0 max-w-full space-y-2'>
      <div className='flex w-full min-w-0 max-w-full gap-1'>
        <Button
          type='button'
          variant='outline'
          onClick={() => setOpen((prev) => !prev)}
          className='flex min-w-0 flex-1 justify-between overflow-hidden font-normal'
        >
          <span className='block min-w-0 flex-1 overflow-hidden text-left text-ellipsis whitespace-nowrap'>
            {value || placeholder}
          </span>
          <ChevronDown className='ml-2 h-4 w-4 shrink-0 opacity-60' />
        </Button>
        {value ? (
          <Button
            type='button'
            variant='outline'
            size='icon'
            onClick={() => onChange('')}
            className='shrink-0'
          >
            <CircleX className='h-4 w-4' />
          </Button>
        ) : null}
      </div>
      {open ? panel : null}
    </div>
  )
}

type SearchableMultiSelectProps = {
  values: string[]
  options: string[]
  placeholder: string
  searchPlaceholder: string
  emptyText: string
  onChange: (values: string[]) => void
}

function SearchableMultiSelect({
  values,
  options,
  placeholder,
  searchPlaceholder,
  emptyText,
  onChange,
}: SearchableMultiSelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const listRef = useRef<HTMLDivElement | null>(null)

  const normalizedOptions = useMemo(() => {
    const seen = new Set<string>()
    return [...values, ...options]
      .map((item) => item.trim())
      .filter((item) => {
        if (!item) return false
        const key = item.toLocaleLowerCase()
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
  }, [options, values])

  const canUseCustomValue =
    query.trim().length > 0 &&
    !normalizedOptions.some(
      (item) => item.toLocaleLowerCase() === query.trim().toLocaleLowerCase()
    )

  const toggleValue = (nextValue: string) => {
    const exists = values.some(
      (item) => item.toLocaleLowerCase() === nextValue.toLocaleLowerCase()
    )
    if (exists) {
      onChange(
        values.filter(
          (item) => item.toLocaleLowerCase() !== nextValue.toLocaleLowerCase()
        )
      )
      return
    }
    onChange([...values, nextValue])
  }

  const handleListWheel = (event: WheelEvent<HTMLDivElement>) => {
    const element = event.currentTarget
    if (element.scrollHeight <= element.clientHeight) {
      return
    }
    event.stopPropagation()
  }

  const panel = (
    <div className='absolute top-full left-0 z-50 mt-2 w-full min-w-0 max-w-full overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md'>
      <div className='border-b p-2'>
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={searchPlaceholder}
          className='h-9'
        />
      </div>
      <div
        ref={listRef}
        onWheel={handleListWheel}
        className='max-h-[min(60vh,18rem)] w-full min-w-0 max-w-full overflow-x-hidden overflow-y-auto overscroll-contain p-1'
      >
        {values.length > 0 ? (
          <button
            type='button'
            onClick={() => {
              onChange([])
              setOpen(false)
              setQuery('')
            }}
            className='hover:bg-accent hover:text-accent-foreground flex w-full min-w-0 max-w-full items-center gap-2 overflow-hidden rounded-sm px-2 py-1.5 text-left text-sm'
          >
            <span className='block min-w-0 flex-1 truncate'>清空全部</span>
          </button>
        ) : null}
        {canUseCustomValue ? (
          <button
            type='button'
            onClick={() => {
              toggleValue(query.trim())
              setQuery('')
            }}
            className='hover:bg-accent hover:text-accent-foreground flex w-full min-w-0 max-w-full items-center gap-2 overflow-hidden rounded-sm px-2 py-1.5 text-left text-sm'
          >
            <span className='block min-w-0 flex-1 truncate'>添加 “{query.trim()}”</span>
          </button>
        ) : null}
        {normalizedOptions.length === 0 ? (
          <div className='py-6 text-center text-sm text-muted-foreground'>
            {emptyText}
          </div>
        ) : null}
        {normalizedOptions.map((option) => {
          const selected = values.some(
            (item) => item.toLocaleLowerCase() === option.toLocaleLowerCase()
          )
          return (
            <button
              key={option}
              type='button'
              onClick={() => toggleValue(option)}
              className='hover:bg-accent hover:text-accent-foreground flex w-full min-w-0 max-w-full items-center gap-2 overflow-hidden rounded-sm px-2 py-1.5 text-left text-sm'
            >
              <Check
                className={`mr-2 h-4 w-4 shrink-0 ${selected ? 'opacity-100' : 'opacity-0'}`}
              />
              <span className='min-w-0 flex-1 truncate'>{option}</span>
            </button>
          )
        })}
      </div>
    </div>
  )

  return (
    <div className='relative w-full min-w-0 max-w-full space-y-2'>
      <Button
        type='button'
        variant='outline'
        onClick={() => setOpen((prev) => !prev)}
        className='flex w-full min-w-0 max-w-full justify-between overflow-hidden font-normal'
      >
        <span className='block min-w-0 flex-1 overflow-hidden text-left text-ellipsis whitespace-nowrap'>
          {values.length > 0 ? values.join(' / ') : placeholder}
        </span>
        <ChevronDown className='ml-2 h-4 w-4 shrink-0 opacity-60' />
      </Button>
      {open ? panel : null}

      {values.length > 0 ? (
        <div className='flex min-w-0 max-w-full flex-wrap gap-2 overflow-hidden'>
          {values.map((value) => (
            <Badge key={value} variant='secondary' className='flex min-w-0 max-w-full items-center gap-1 overflow-hidden pr-1'>
              <span className='min-w-0 flex-1 truncate'>{value}</span>
              <button
                type='button'
                className='shrink-0 rounded-full p-0.5 text-muted-foreground transition hover:text-foreground'
                onClick={() =>
                  onChange(
                    values.filter(
                      (item) =>
                        item.toLocaleLowerCase() !== value.toLocaleLowerCase()
                    )
                  )
                }
              >
                <CircleX className='h-3 w-3' />
              </button>
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function getGeneralSubscribeTitle(item: GeneralSubscribeItem) {
  const parts = [
    item.number_prefix ? `番号前缀：${item.number_prefix}` : null,
    item.publisher ? `发行商：${item.publisher}` : null,
    item.series ? `系列：${item.series}` : null,
    item.producer ? `制作商：${item.producer}` : null,
  ].filter(Boolean)

  return parts.length > 0 ? parts.join(' / ') : '未命名综合订阅'
}

function GeneralSubscribeDialogForm({
  subscribeItem,
  filters,
  priorities,
  defaultFilterId,
  defaultPriorityId,
  onOpenChange,
}: Omit<GeneralSubscribeDialogProps, 'open'>) {
  const queryClient = useQueryClient()
  const isEditMode = Boolean(subscribeItem)
  const [formState, setFormState] = useState<GeneralSubscribeFormState>(() =>
    createInitialState(subscribeItem, defaultFilterId, defaultPriorityId)
  )
  const selectedGenres = useMemo(
    () => normalizeGenresInput(formState.genresText),
    [formState.genresText]
  )

  const { data: publisherOptionsData } = useQuery({
    queryKey: [
      'general-subscribe-options',
      'publisher',
      formState.series,
      formState.producer,
      selectedGenres,
    ],
    queryFn: async () => {
      const res = await fetchGeneralSubscribeOptions({
        series: formState.series.trim() || undefined,
        producer: formState.producer.trim() || undefined,
        genres: selectedGenres.length > 0 ? selectedGenres : undefined,
      })
      return res.data
    },
    staleTime: 60 * 1000,
  })

  const { data: seriesOptionsData } = useQuery({
    queryKey: [
      'general-subscribe-options',
      'series',
      formState.publisher,
      formState.producer,
      selectedGenres,
    ],
    queryFn: async () => {
      const res = await fetchGeneralSubscribeOptions({
        publisher: formState.publisher.trim() || undefined,
        producer: formState.producer.trim() || undefined,
        genres: selectedGenres.length > 0 ? selectedGenres : undefined,
      })
      return res.data
    },
    staleTime: 60 * 1000,
  })

  const { data: producerOptionsData } = useQuery({
    queryKey: [
      'general-subscribe-options',
      'producer',
      formState.publisher,
      formState.series,
      selectedGenres,
    ],
    queryFn: async () => {
      const res = await fetchGeneralSubscribeOptions({
        publisher: formState.publisher.trim() || undefined,
        series: formState.series.trim() || undefined,
        genres: selectedGenres.length > 0 ? selectedGenres : undefined,
      })
      return res.data
    },
    staleTime: 60 * 1000,
  })

  const { data: genreOptionsData } = useQuery({
    queryKey: [
      'general-subscribe-options',
      'genres',
      formState.publisher,
      formState.series,
      formState.producer,
    ],
    queryFn: async () => {
      const res = await fetchGeneralSubscribeOptions({
        publisher: formState.publisher.trim() || undefined,
        series: formState.series.trim() || undefined,
        producer: formState.producer.trim() || undefined,
      })
      return res.data
    },
    staleTime: 60 * 1000,
  })

  const generalSubscribeOptions = {
    publishers: publisherOptionsData?.publishers || [],
    series: seriesOptionsData?.series || [],
    producers: producerOptionsData?.producers || [],
    genres: genreOptionsData?.genres || [],
  }

  const { data: preferenceConfig, isLoading: isPreferenceConfigLoading } =
    useQuery({
      queryKey: SUBSCRIBE_PREFERENCE_CONFIG_QUERY_KEY,
      queryFn: async () => {
        const res = await getSubscribePreferenceConfig()
        return res.data || DEFAULT_SUBSCRIBE_PREFERENCE_CONFIG
      },
      staleTime: 5 * 60 * 1000,
    })

  const handleApplyPreferenceConfig = () => {
    const nextPreferenceConfig =
      preferenceConfig || DEFAULT_SUBSCRIBE_PREFERENCE_CONFIG
    setFormState((prev) => ({
      ...prev,
      earliestReleaseDate: nextPreferenceConfig.earliest_release_date || '',
      excludeVr: Boolean(nextPreferenceConfig.exclude_vr),
      maxCoactors:
        nextPreferenceConfig.max_coactors == null
          ? ''
          : String(nextPreferenceConfig.max_coactors),
    }))
    toast.success('已应用喜好配置')
  }

  const mutation = useMutation({
    mutationFn: async () => {
      const numberPrefix = formState.numberPrefix.trim().toUpperCase()
      const publisher = formState.publisher.trim()
      const series = formState.series.trim()
      const producer = formState.producer.trim()
      const genres = selectedGenres

      if (
        !numberPrefix &&
        !publisher &&
        !series &&
        !producer &&
        genres.length === 0
      ) {
        throw new Error('番号前缀、发行商、系列、制作商、类型至少填写一项')
      }

      const normalizedMaxCoactors = formState.maxCoactors.trim()
      const maxCoactors =
        normalizedMaxCoactors === '' ? undefined : Number(normalizedMaxCoactors)
      if (
        maxCoactors !== undefined &&
        (!Number.isInteger(maxCoactors) || maxCoactors < 0)
      ) {
        throw new Error('最大共演人数必须是大于等于 0 的整数')
      }

      const payload = {
        number_prefix: numberPrefix || undefined,
        publisher: publisher || undefined,
        series: series || undefined,
        producer: producer || undefined,
        genres: genres.length > 0 ? genres : undefined,
        max_coactors: maxCoactors,
        earliest_release_date: formState.earliestReleaseDate || undefined,
        exclude_vr: formState.excludeVr,
        filter_id:
          formState.filterId === 'none'
            ? undefined
            : Number(formState.filterId),
        priority_id:
          formState.priorityId === 'none'
            ? undefined
            : Number(formState.priorityId),
      }

      if (subscribeItem) {
        return updateGeneralSubscribe({
          general_subscribe_id: subscribeItem.id,
          ...payload,
        })
      }

      return subscribeGeneral(payload)
    },
    onSuccess: (res) => {
      toast.success(
        res.message || (isEditMode ? '综合订阅已更新' : '综合订阅已创建')
      )
      queryClient.invalidateQueries({ queryKey: ['general-subscribes'] })
      onOpenChange(false)
    },
    onError: (error: Error) => {
      toast.error(
        error.message || (isEditMode ? '综合订阅更新失败' : '综合订阅创建失败')
      )
    },
  })

  return (
    <>
      <DialogHeader>
        <DialogTitle>
          {isEditMode ? '编辑综合订阅' : '创建综合订阅'}
        </DialogTitle>
        <DialogDescription>
          至少填写一个匹配条件。执行任务时会按番号前缀、发行商、系列等匹配影片，再应用日期、排除
          VR、最大共演、过滤器和排序器配置。可通过“应用喜好配置”快速填入通用偏好字段。
        </DialogDescription>
      </DialogHeader>

      <div className='space-y-4'>
        <div className='grid gap-4 md:grid-cols-2'>
          <div className='space-y-2'>
            <div className='text-sm font-medium'>番号前缀</div>
            <Input
              value={formState.numberPrefix}
              placeholder='例如 IPX、SSIS、MIDV'
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  numberPrefix: event.target.value,
                }))
              }
            />
          </div>

          <div className='space-y-2'>
            <div className='text-sm font-medium'>发行商名称</div>
            <SearchableSingleSelect
              value={formState.publisher}
              options={generalSubscribeOptions?.publishers || []}
              placeholder='选择发行商'
              searchPlaceholder='搜索发行商'
              emptyText='没有匹配的发行商'
              onChange={(value) =>
                setFormState((prev) => ({
                  ...prev,
                  publisher: value,
                }))
              }
            />
          </div>

          <div className='space-y-2'>
            <div className='text-sm font-medium'>系列名称</div>
            <SearchableSingleSelect
              value={formState.series}
              options={generalSubscribeOptions?.series || []}
              placeholder='选择系列'
              searchPlaceholder='搜索系列'
              emptyText='没有匹配的系列'
              onChange={(value) =>
                setFormState((prev) => ({
                  ...prev,
                  series: value,
                }))
              }
            />
          </div>

          <div className='space-y-2'>
            <div className='text-sm font-medium'>制作商</div>
            <SearchableSingleSelect
              value={formState.producer}
              options={generalSubscribeOptions?.producers || []}
              placeholder='选择制作商'
              searchPlaceholder='搜索制作商'
              emptyText='没有匹配的制作商'
              onChange={(value) =>
                setFormState((prev) => ({
                  ...prev,
                  producer: value,
                }))
              }
            />
          </div>

          <div className='space-y-2'>
            <div className='text-sm font-medium'>类型</div>
            <SearchableMultiSelect
              values={selectedGenres}
              options={generalSubscribeOptions?.genres || []}
              placeholder='选择或输入类型'
              searchPlaceholder='搜索类型'
              emptyText='没有匹配的类型'
              onChange={(values) =>
                setFormState((prev) => ({
                  ...prev,
                  genresText: values.join(', '),
                }))
              }
            />
          </div>

          <div className='space-y-2'>
            <div className='text-sm font-medium'>最早发行日期</div>
            <Input
              type='date'
              value={formState.earliestReleaseDate}
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  earliestReleaseDate: event.target.value,
                }))
              }
            />
          </div>

          <div className='space-y-2'>
            <div className='text-sm font-medium'>最大共演人数</div>
            <Input
              inputMode='numeric'
              value={formState.maxCoactors}
              placeholder='留空表示不限'
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  maxCoactors: event.target.value,
                }))
              }
            />
          </div>

          <div className='flex items-center justify-between rounded-lg border px-3 py-2'>
            <div className='space-y-1'>
              <div className='text-sm font-medium'>排除 VR</div>
              <div className='text-xs text-muted-foreground'>
                开启后会过滤 VR 影片
              </div>
            </div>
            <Switch
              checked={formState.excludeVr}
              onCheckedChange={(checked) =>
                setFormState((prev) => ({
                  ...prev,
                  excludeVr: checked,
                }))
              }
            />
          </div>

          <div className='space-y-2'>
            <div className='text-sm font-medium'>过滤器</div>
            <Select
              value={formState.filterId}
              onValueChange={(value) =>
                setFormState((prev) => ({ ...prev, filterId: value }))
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder='选择过滤器' />
              </SelectTrigger>
              <SelectContent className="w-full">
                <SelectItem value='none'>默认过滤器</SelectItem>
                {(filters || []).map((item) => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    {item.filter_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className='space-y-2'>
            <div className='text-sm font-medium'>排序器</div>
            <Select
              value={formState.priorityId}
              onValueChange={(value) =>
                setFormState((prev) => ({ ...prev, priorityId: value }))
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder='选择排序器' />
              </SelectTrigger>
              <SelectContent className="w-full">
                <SelectItem value='none'>默认排序器</SelectItem>
                {(priorities || []).map((item) => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    {item.priority_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button
          type='button'
          variant='outline'
          disabled={isPreferenceConfigLoading}
          onClick={handleApplyPreferenceConfig}
        >
          {isPreferenceConfigLoading ? (
            <Loader2 className='mr-2 h-4 w-4 animate-spin' />
          ) : null}
          应用喜好配置
        </Button>
        <Button
          type='button'
          variant='outline'
          onClick={() => onOpenChange(false)}
        >
          取消
        </Button>
        <Button
          type='button'
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? (
            <Loader2 className='mr-2 h-4 w-4 animate-spin' />
          ) : null}
          {isEditMode ? '保存修改' : '创建综合订阅'}
        </Button>
      </DialogFooter>
    </>
  )
}

function GeneralSubscribeDialog({
  open,
  onOpenChange,
  subscribeItem,
  filters,
  priorities,
  defaultFilterId,
  defaultPriorityId,
}: GeneralSubscribeDialogProps) {
  const dialogKey = [
    subscribeItem?.id ?? 'new',
    defaultFilterId ?? 'none',
    defaultPriorityId ?? 'none',
  ].join(':')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogOverlay className='bg-background/20 backdrop-blur-lg' />
      <DialogContent className='w-[calc(100vw-2rem)] max-w-[calc(100vw-2rem)] bg-background/40 backdrop-blur-lg sm:max-w-2xl'>
        {open ? (
          <GeneralSubscribeDialogForm
            key={dialogKey}
            subscribeItem={subscribeItem}
            filters={filters}
            priorities={priorities}
            defaultFilterId={defaultFilterId}
            defaultPriorityId={defaultPriorityId}
            onOpenChange={onOpenChange}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

interface GeneralSubscribeCardProps {
  item: GeneralSubscribeItem
  filterLabel: string
  priorityLabel: string
  actionLoading: boolean
  onEdit: (item: GeneralSubscribeItem) => void
  onAction: (item: GeneralSubscribeItem, action: GeneralSubscribeAction) => void
}

function GeneralSubscribeCard({
  item,
  filterLabel,
  priorityLabel,
  actionLoading,
  onEdit,
  onAction,
}: GeneralSubscribeCardProps) {
  return (
    <Card className='gap-0 p-4'>
      <div className='space-y-3'>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div className='min-w-0 flex-1 space-y-1'>
            <div className='truncate text-base font-semibold'>
              {getGeneralSubscribeTitle(item)}
            </div>
            <div className='text-xs text-muted-foreground'>
              创建时间：{item.create_time || '-'}
            </div>
          </div>

          <div className='flex items-center gap-2'>
            <Badge variant='outline' className={STATUS_CLASS_MAP[item.status]}>
              {STATUS_LABEL_MAP[item.status]}
            </Badge>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type='button'
                  className='rounded-full p-2 text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-50'
                  disabled={actionLoading}
                >
                  <MoreVertical className='h-4 w-4' />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align='end'>
                <DropdownMenuItem onClick={() => onEdit(item)}>
                  <Pencil className='mr-2 h-4 w-4' />
                  编辑订阅
                </DropdownMenuItem>
                {item.status === 'active' ? (
                  <DropdownMenuItem onClick={() => onAction(item, 'pause')}>
                    <Pause className='mr-2 h-4 w-4' />
                    暂停订阅
                  </DropdownMenuItem>
                ) : null}
                {item.status === 'paused' ? (
                  <DropdownMenuItem onClick={() => onAction(item, 'resume')}>
                    <StepForward className='mr-2 h-4 w-4' />
                    恢复订阅
                  </DropdownMenuItem>
                ) : null}
                {item.status !== 'canceled' ? (
                  <DropdownMenuItem
                    variant='destructive'
                    onClick={() => onAction(item, 'cancel')}
                  >
                    <CircleX className='mr-2 h-4 w-4' />
                    取消订阅
                  </DropdownMenuItem>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <div className='flex min-w-0 flex-wrap gap-2 text-xs text-muted-foreground'>
          <span className='max-w-full truncate rounded-full bg-muted px-2 py-1'>
            制作商：{item.producer || '不限'}
          </span>
          <span className='max-w-full truncate rounded-full bg-muted px-2 py-1'>
            类型：{item.genres?.length ? item.genres.join(' / ') : '不限'}
          </span>
          <span className='max-w-full truncate rounded-full bg-muted px-2 py-1'>
            最早发行日期：{item.earliest_release_date || '不限'}
          </span>
          <span className='max-w-full truncate rounded-full bg-muted px-2 py-1'>
            最大共演人数：{item.max_coactors ?? '不限'}
          </span>
          <span className='max-w-full truncate rounded-full bg-muted px-2 py-1'>
            排除 VR：{item.exclude_vr ? '是' : '否'}
          </span>
          <span className='max-w-full truncate rounded-full bg-muted px-2 py-1'>
            过滤器：{filterLabel}
          </span>
          <span className='max-w-full truncate rounded-full bg-muted px-2 py-1'>
            排序器：{priorityLabel}
          </span>
        </div>
      </div>
    </Card>
  )
}

export function GeneralSubscribePanel({
  status,
  keyword,
  onTotalChange,
}: {
  status: GeneralSubscribeItem['status']
  keyword?: string
  onTotalChange?: (total: number) => void
}) {
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<GeneralSubscribeItem | null>(
    null
  )

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

  const { data: generalSubscribes, isLoading: isGeneralSubscribesLoading } =
    useQuery({
      queryKey: ['general-subscribes', status, keyword || ''],
      queryFn: async () => {
        const res = await fetchGeneralSubscribesPage({
          page: 1,
          pageSize: 100,
          keyword,
          status,
        })
        return res.data
      },
      staleTime: 60 * 1000,
    })

  useEffect(() => {
    onTotalChange?.(generalSubscribes?.total ?? 0)
  }, [generalSubscribes?.total, onTotalChange])

  const defaultFilterId = useMemo(
    () => filters?.find((item) => item.is_default)?.id,
    [filters]
  )
  const defaultPriorityId = useMemo(
    () => priorities?.find((item) => item.is_default)?.id,
    [priorities]
  )

  const filterLabelMap = useMemo(
    () =>
      new Map(
        (filters || []).map((item) => [String(item.id), item.filter_name])
      ),
    [filters]
  )
  const priorityLabelMap = useMemo(
    () =>
      new Map(
        (priorities || []).map((item) => [String(item.id), item.priority_name])
      ),
    [priorities]
  )

  const statusMutation = useMutation({
    mutationFn: async ({
      id,
      action,
    }: {
      id: number
      action: GeneralSubscribeAction
    }) => {
      switch (action) {
        case 'pause':
          return pauseGeneralSubscribe(id)
        case 'resume':
          return resumeGeneralSubscribe(id)
        case 'cancel':
          return cancelGeneralSubscribe(id)
      }
    },
    onSuccess: (res, variables) => {
      const messageMap: Record<GeneralSubscribeAction, string> = {
        pause: '已暂停综合订阅',
        resume: '已恢复综合订阅',
        cancel: '已取消综合订阅',
      }
      toast.success(res.message || messageMap[variables.action])
      queryClient.invalidateQueries({ queryKey: ['general-subscribes'] })
    },
    onError: (error: Error) => {
      toast.error(error.message || '综合订阅状态更新失败')
    },
  })

  const handleOpenCreate = () => {
    setEditingItem(null)
    setDialogOpen(true)
  }

  const handleEdit = (item: GeneralSubscribeItem) => {
    setEditingItem(item)
    setDialogOpen(true)
  }

  const handleStatusAction = (
    item: GeneralSubscribeItem,
    action: GeneralSubscribeAction
  ) => {
    statusMutation.mutate({ id: item.id, action })
  }

  return (
    <div className='mx-4 space-y-4 pb-4'>
      <Card className='gap-0 p-4'>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div className='space-y-1'>
            <div className='text-base font-semibold'>综合订阅</div>
            <div className='text-sm text-muted-foreground'>
              按番号前缀、发行商、制作商、系列、类型建立订阅规则
            </div>
          </div>
          <Button onClick={handleOpenCreate}>
            <Plus className='h-4 w-4' />
            创建订阅
          </Button>
        </div>
      </Card>

      <GeneralSubscribeDialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open)
          if (!open) {
            setEditingItem(null)
          }
        }}
        subscribeItem={editingItem}
        filters={filters}
        priorities={priorities}
        defaultFilterId={defaultFilterId}
        defaultPriorityId={defaultPriorityId}
      />

      <div>
        {isGeneralSubscribesLoading ? (
          <div className='flex items-center justify-center rounded-lg border border-dashed py-12 text-sm text-muted-foreground'>
            <Loader2 className='mr-2 h-4 w-4 animate-spin' />
            正在加载综合订阅...
          </div>
        ) : generalSubscribes?.items.length ? (
          <div className='grid gap-3'>
            {generalSubscribes.items.map((item) => {
              const filterLabel =
                item.filter_id === null || item.filter_id === undefined
                  ? '默认过滤器'
                  : (filterLabelMap.get(String(item.filter_id)) ??
                    `ID ${item.filter_id}`)
              const priorityLabel =
                item.priority_id === null || item.priority_id === undefined
                  ? '默认排序器'
                  : (priorityLabelMap.get(String(item.priority_id)) ??
                    `ID ${item.priority_id}`)

              return (
                <GeneralSubscribeCard
                  key={item.id}
                  item={item}
                  filterLabel={filterLabel}
                  priorityLabel={priorityLabel}
                  actionLoading={statusMutation.isPending}
                  onEdit={handleEdit}
                  onAction={handleStatusAction}
                />
              )
            })}
          </div>
        ) : (
          <div className='rounded-lg border border-dashed'>
            <EmptyState
              title='暂无综合订阅'
              description='当前筛选条件下没有综合订阅'
            />
          </div>
        )}
      </div>
    </div>
  )
}
