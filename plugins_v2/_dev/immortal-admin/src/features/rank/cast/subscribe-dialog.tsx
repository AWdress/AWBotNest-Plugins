import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import type { Cast, CastSubscribeSummary } from '@/api/cast.ts'
import { listFilter } from '@/api/filter.ts'
import { listPriority } from '@/api/priority.ts'
import {
  DEFAULT_SUBSCRIBE_PREFERENCE_CONFIG,
  getSubscribePreferenceConfig,
  SUBSCRIBE_PREFERENCE_CONFIG_QUERY_KEY,
} from '@/api/subscribe-preference.ts'
import {
  subscribeCast,
  updateCastSubscribe,
} from '@/api/subscribe.ts'
import { Button } from '@/components/ui/button.tsx'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogTitle,
} from '@/components/ui/dialog.tsx'
import { Input } from '@/components/ui/input.tsx'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.tsx'
import { Switch } from '@/components/ui/switch.tsx'
import { CAST_SUBSCRIPTION_QUERY_KEYS } from '@/lib/subscription-query-keys.ts'

interface CastSubscribeDialogProps {
  cast: Cast | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

type CastSubscribeFormState = {
  maxCoactors: string
  maxPage: string
  replaceMaxPage: string
  isSingle: boolean
  earliestReleaseDate: string
  excludeVr: boolean
  filterId: string
  priorityId: string
}

function buildInitialFormState(
  subscribeItem: CastSubscribeSummary | null | undefined,
  defaultFilterId?: number,
  defaultPriorityId?: number
): CastSubscribeFormState {
  if (subscribeItem) {
    return {
      maxCoactors:
        subscribeItem.max_coactors == null
          ? ''
          : String(subscribeItem.max_coactors),
      maxPage:
        subscribeItem.max_page == null ? '' : String(subscribeItem.max_page),
      replaceMaxPage:
        subscribeItem.replace_max_page == null
          ? ''
          : String(subscribeItem.replace_max_page),
      isSingle: Boolean(subscribeItem.is_single),
      earliestReleaseDate: subscribeItem.earliest_release_date || '',
      excludeVr: Boolean(subscribeItem.exclude_vr),
      filterId:
        subscribeItem.filter_id == null
          ? 'none'
          : String(subscribeItem.filter_id),
      priorityId:
        subscribeItem.priority_id == null
          ? 'none'
          : String(subscribeItem.priority_id),
    }
  }

  return {
    maxCoactors: '',
    maxPage: '',
    replaceMaxPage: '1',
    isSingle: false,
    earliestReleaseDate: '',
    excludeVr: false,
    filterId: defaultFilterId ? String(defaultFilterId) : 'none',
    priorityId: defaultPriorityId ? String(defaultPriorityId) : 'none',
  }
}

function CastSubscribeDialogForm({
  cast,
  defaultFilterId,
  defaultPriorityId,
  filters,
  priorities,
  onOpenChange,
}: {
  cast: Cast
  defaultFilterId?: number
  defaultPriorityId?: number
  filters: Awaited<ReturnType<typeof listFilter>>['data'] | undefined
  priorities: Awaited<ReturnType<typeof listPriority>>['data'] | undefined
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const subscribeItem = cast.subscribe
  const isEditMode = Boolean(subscribeItem) && subscribeItem?.status !== 'canceled'
  const [formState, setFormState] = useState<CastSubscribeFormState>(() =>
    buildInitialFormState(subscribeItem, defaultFilterId, defaultPriorityId)
  )
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
      maxCoactors:
        nextPreferenceConfig.max_coactors == null
          ? ''
          : String(nextPreferenceConfig.max_coactors),
      maxPage:
        nextPreferenceConfig.max_page == null
          ? ''
          : String(nextPreferenceConfig.max_page),
      replaceMaxPage:
        nextPreferenceConfig.replace_max_page == null
          ? ''
          : String(nextPreferenceConfig.replace_max_page),
      isSingle: Boolean(nextPreferenceConfig.is_single),
      earliestReleaseDate: nextPreferenceConfig.earliest_release_date || '',
      excludeVr: Boolean(nextPreferenceConfig.exclude_vr),
    }))
    toast.success('已应用喜好配置')
  }

  const mutation = useMutation({
    mutationFn: async () => {
      const normalizedMaxCoactors = formState.maxCoactors.trim()
      const maxCoactorsValue =
        normalizedMaxCoactors === '' ? undefined : Number(normalizedMaxCoactors)
      if (
        maxCoactorsValue !== undefined &&
        (!Number.isInteger(maxCoactorsValue) || maxCoactorsValue < 0)
      ) {
        throw new Error('最大共演人数必须是大于等于 0 的整数')
      }

      const normalizedMaxPage = formState.maxPage.trim()
      const maxPageValue =
        normalizedMaxPage === '' ? undefined : Number(normalizedMaxPage)
      if (
        maxPageValue !== undefined &&
        (!Number.isInteger(maxPageValue) || maxPageValue < 1)
      ) {
        throw new Error('最大页数必须是大于等于 1 的整数')
      }

      const normalizedReplaceMaxPage = formState.replaceMaxPage.trim()
      const replaceMaxPageValue =
        normalizedReplaceMaxPage === ''
          ? undefined
          : Number(normalizedReplaceMaxPage)
      if (
        replaceMaxPageValue !== undefined &&
        (!Number.isInteger(replaceMaxPageValue) || replaceMaxPageValue < 1)
      ) {
        throw new Error('替换最大页数必须是大于等于 1 的整数')
      }

      const payload = {
        max_coactors: maxCoactorsValue,
        max_page: maxPageValue,
        replace_max_page: replaceMaxPageValue,
        is_single: formState.isSingle,
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

      if (subscribeItem && subscribeItem.status !== 'canceled') {
        return updateCastSubscribe({
          cast_subscribe_id: subscribeItem.id,
          ...payload,
        })
      }

      return subscribeCast({
        cast_id: cast.id,
        ...payload,
      })
    },
    onSuccess: (res) => {
      if (res.code !== 0) return
      toast.success(
        res.message || (isEditMode ? '演员订阅已更新' : '演员订阅成功')
      )
      for (const queryKey of CAST_SUBSCRIPTION_QUERY_KEYS) {
        queryClient.invalidateQueries({ queryKey, exact: false })
      }
      onOpenChange(false)
    },
    onError: (error: Error) => {
      toast.error(
        error.message || (isEditMode ? '演员订阅更新失败' : '演员订阅失败')
      )
    },
  })

  const displayName = cast.cn_name || cast.name

  return (
    <>
      <DialogHeader>
        <DialogTitle>{isEditMode ? '编辑演员订阅' : '订阅演员'}</DialogTitle>
        <DialogDescription>
          {displayName
            ? `为 ${displayName} 设置自动订阅规则，可通过“应用喜好配置”快速填入默认偏好。`
            : '设置自动订阅规则，可通过“应用喜好配置”快速填入默认偏好。'}
        </DialogDescription>
      </DialogHeader>

      <div className='space-y-4'>
        <div className='grid gap-4 sm:grid-cols-2'>
          <div className='space-y-2'>
            <div className='text-sm font-medium'>最大共演人数</div>
            <Input
              type='number'
              min={0}
              placeholder='留空表示不限'
              value={formState.maxCoactors}
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  maxCoactors: event.target.value,
                }))
              }
            />
          </div>

          <div className='flex items-center justify-between rounded-lg border p-3'>
            <div className='space-y-1'>
              <div className='text-sm font-medium'>排除 VR 影片</div>
              <div className='text-xs text-muted-foreground'>
                开启后会跳过 VR 标签
              </div>
            </div>
            <Switch
              checked={formState.excludeVr}
              onCheckedChange={(checked) =>
                setFormState((prev) => ({ ...prev, excludeVr: checked }))
              }
            />
          </div>
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
        <div className='grid gap-4 sm:grid-cols-2'>
          <div className='space-y-2'>
            <div className='text-sm font-medium'>过滤器</div>
            <Select
              value={formState.filterId}
              onValueChange={(value) =>
                setFormState((prev) => ({ ...prev, filterId: value }))
              }
            >
              <SelectTrigger className='w-full'>
                <SelectValue placeholder='选择过滤器' />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='none'>默认</SelectItem>
                {(filters || []).map((item) => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    {item.filter_name}
                    {item.is_default ? '（默认）' : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className='space-y-2'>
            <div className='text-sm font-medium'>优先级</div>
            <Select
              value={formState.priorityId}
              onValueChange={(value) =>
                setFormState((prev) => ({ ...prev, priorityId: value }))
              }
            >
              <SelectTrigger className='w-full'>
                <SelectValue placeholder='选择优先级' />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='none'>默认</SelectItem>
                {(priorities || []).map((item) => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    {item.priority_name}
                    {item.is_default ? '（默认）' : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className='text-xs font-medium'>
          以下配置仅用于爬取数据，不用于过滤订阅
        </div>
        <div className='grid gap-3 sm:grid-cols-3'>
          <div className='space-y-2'>
            <div className='text-sm font-medium'>最大页数</div>
            <div className='text-xs text-muted-foreground'>
              用于抓取AVbase中该演员的影片资源,不会立即用于订阅
            </div>
            <Input
              type='number'
              min={1}
              placeholder='留空表示不限'
              value={formState.maxPage}
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  maxPage: event.target.value,
                }))
              }
            />
          </div>

          <div className='space-y-2 rounded-lg border p-3'>
            <div className='space-y-1'>
              <div className='text-sm font-medium'>替换最大页数</div>
              <div className='text-xs text-muted-foreground'>
                留空表示不替换，填写后用该页数覆盖默认值(建议1)
              </div>
            </div>
            <Input
              type='number'
              min={1}
              placeholder='留空表示不替换'
              value={formState.replaceMaxPage}
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  replaceMaxPage: event.target.value,
                }))
              }
            />
          </div>

          <div className='flex items-center justify-between rounded-lg border p-3'>
            <div className='space-y-1'>
              <div className='text-sm font-medium'>仅单体</div>
              <div className='text-xs text-muted-foreground'>
                仅抓取单体作品
              </div>
            </div>
            <Switch
              checked={formState.isSingle}
              onCheckedChange={(checked) =>
                setFormState((prev) => ({ ...prev, isSingle: checked }))
              }
            />
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
          {mutation.isPending && (
            <Loader2 className='mr-2 h-4 w-4 animate-spin' />
          )}
          {isEditMode ? '保存修改' : '确认订阅'}
        </Button>
      </DialogFooter>
    </>
  )
}

export function CastSubscribeDialog({
  cast,
  open,
  onOpenChange,
}: CastSubscribeDialogProps) {
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

  const defaultFilterId = useMemo(
    () => filters?.find((item) => item.is_default)?.id,
    [filters]
  )
  const defaultPriorityId = useMemo(
    () => priorities?.find((item) => item.is_default)?.id,
    [priorities]
  )

  const dialogKey = [
    cast?.id ?? 'none',
    cast?.subscribe?.id ?? 'new',
    defaultFilterId ?? 'none',
    defaultPriorityId ?? 'none',
  ].join(':')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogOverlay className='bg-background/20 backdrop-blur-lg' />
      <DialogContent className='bg-background/40 backdrop-blur-lg'>
        {cast ? (
          <CastSubscribeDialogForm
            key={dialogKey}
            cast={cast}
            defaultFilterId={defaultFilterId}
            defaultPriorityId={defaultPriorityId}
            filters={filters}
            priorities={priorities}
            onOpenChange={onOpenChange}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
