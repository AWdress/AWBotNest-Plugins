import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Camera,
  CircleX,
  Clapperboard,
  Heart,
  MoreVertical,
  Pause,
  Pencil,
  SearchIcon,
  StepForward,
} from 'lucide-react'
import type { Cast } from '@/api/cast.ts'
import {
  cancelCastSub,
  pauseCastSubscribe,
  resumeCastSubscribe,
  type CastSubscribeItem,
} from '@/api/subscribe.ts'
import { useImageMode } from '@/context/image-mode-provider.tsx'
import { useSearch } from '@/context/search-provider.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Card } from '@/components/ui/card.tsx'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu.tsx'
import { cn } from '@/lib/utils.ts'
import { toast } from 'sonner'
import { LazyImage } from '@/components/lazy-image'
import { CAST_SUBSCRIPTION_QUERY_KEYS } from '@/lib/subscription-query-keys.ts'

const STATUS_MAP: Record<CastSubscribeItem['status'], { label: string; className: string }> = {
  active: {
    label: '订阅中',
    className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600',
  },
  paused: {
    label: '已暂停',
    className: 'border-amber-500/30 bg-amber-500/10 text-amber-600',
  },
  canceled: {
    label: '已取消',
    className: 'border-border bg-muted text-muted-foreground',
  },
}

const RANK_STYLE: Record<number, string> = {
  1: 'from-yellow-300 via-amber-400 to-yellow-500 text-yellow-950',
  2: 'from-slate-200 via-slate-300 to-slate-400 text-slate-800',
  3: 'from-orange-300 via-amber-500 to-orange-500 text-orange-950',
}

interface CastCardProps {
  cast: Cast
  rank?: number
  showCreatedTime?: boolean
  onCreate?: (cast: Cast) => void
  onEdit?: (cast: Cast) => void
  onStatusChanged?: () => void
}

export function CastCard({
  cast,
  rank,
  showCreatedTime = false,
  onCreate,
  onEdit,
  onStatusChanged,
}: CastCardProps) {
  const queryClient = useQueryClient()
  const { handleSearch } = useSearch()
  const { mode } = useImageMode()
  const [imgError, setImgError] = useState(false)

  const resolvedSubscribeItem = cast.subscribe
    ? ({ ...cast.subscribe, cast } as CastSubscribeItem)
    : null

  const displayName = cast.cn_name || cast.name
  const aliases = (cast.former_name || []).filter((name) => name && name !== displayName)
  const status = resolvedSubscribeItem ? STATUS_MAP[resolvedSubscribeItem.status] : null
  const imageUrl = cast.photo || cast.avatar
  const showImage = mode !== 'hide'

  const invalidate = () => {
    for (const queryKey of CAST_SUBSCRIPTION_QUERY_KEYS) {
      queryClient.invalidateQueries({ queryKey, exact: false })
    }
    onStatusChanged?.()
  }

  const pauseMutation = useMutation({
    mutationFn: async () => {
      if (!resolvedSubscribeItem) return null
      return pauseCastSubscribe(resolvedSubscribeItem.id)
    },
    onSuccess: (res) => {
      if (!res || res.code !== 0) return
      toast.success(res.message || '已暂停演员订阅')
      invalidate()
    },
  })

  const resumeMutation = useMutation({
    mutationFn: async () => {
      if (!resolvedSubscribeItem) return null
      return resumeCastSubscribe(resolvedSubscribeItem.id)
    },
    onSuccess: (res) => {
      if (!res || res.code !== 0) return
      toast.success(res.message || '已恢复演员订阅')
      invalidate()
    },
  })

  const cancelMutation = useMutation({
    mutationFn: async () => {
      if (!resolvedSubscribeItem) return null
      return cancelCastSub(resolvedSubscribeItem.id)
    },
    onSuccess: (res) => {
      if (!res || res.code !== 0) return
      toast.success(res.message || '已取消演员订阅')
      invalidate()
    },
  })

  return (
    <Card className='overflow-hidden py-0'>
      <div className='flex gap-4 p-4'>
        {showImage && (
          <div className='relative h-32 w-24 shrink-0 overflow-hidden rounded-lg bg-muted'>
            {!imgError && imageUrl ? (
              <LazyImage
                src={imageUrl}
                alt={displayName}
                referrerPolicy='no-referrer'
                className={cn(
                  'h-full w-full object-cover object-top transition duration-300',
                  mode === 'blur' && 'blur-xl'
                )}
                onError={() => setImgError(true)}
              />
            ) : (
              <div className='flex h-full w-full items-center justify-center text-muted-foreground'>
                <Camera className='h-8 w-8' />
              </div>
            )}

            {rank ? (
              <div
                className={cn(
                  'absolute top-2 left-2 inline-flex min-w-10 items-center justify-center rounded-full bg-linear-to-r px-2.5 py-1 text-xs font-semibold shadow-sm',
                  RANK_STYLE[rank] || 'from-primary/80 to-primary text-primary-foreground'
                )}
              >
                #{rank}
              </div>
            ) : null}
          </div>
        )}

        <div className='min-w-0 flex-1 space-y-3'>
          <div className='flex items-start justify-between gap-3'>
            <div className='min-w-0 space-y-1'>
              <div className='flex flex-wrap items-center gap-2'>
                <div className='line-clamp-1 text-base font-semibold'>{displayName}</div>
                {!showImage && rank ? (
                  <Badge variant='secondary' className='text-xs'>
                    #{rank}
                  </Badge>
                ) : null}
              </div>
              {cast.cn_name && cast.cn_name !== cast.name && (
                <div className='line-clamp-1 text-sm text-muted-foreground'>{cast.name}</div>
              )}
            </div>

            <div className='flex items-center gap-2'>
              {status ? (
                <Badge variant='outline' className={status.className}>
                  {status.label}
                </Badge>
              ) : null}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    type='button'
                    className='rounded-full p-2 text-muted-foreground transition hover:bg-muted hover:text-foreground'
                  >
                    <MoreVertical className='h-4 w-4' />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align='end'>
                  <DropdownMenuItem onClick={() => handleSearch(cast.name || displayName, { target: 'articles' })}>
                    <SearchIcon className='mr-2 h-4 w-4' />
                    搜索资源库
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleSearch(cast.name || displayName, { target: 'cast-search' })}>
                    <Clapperboard className='mr-2 h-4 w-4' />
                    搜索影片库
                  </DropdownMenuItem>
                  {(!resolvedSubscribeItem || resolvedSubscribeItem.status === 'canceled') &&
                  onCreate ? (
                    <DropdownMenuItem onClick={() => onCreate(cast)}>
                      <Heart className='mr-2 h-4 w-4' />
                      订阅演员
                    </DropdownMenuItem>
                  ) : null}
                  {resolvedSubscribeItem && resolvedSubscribeItem.status !== 'canceled' && onEdit ? (
                    <DropdownMenuItem onClick={() => onEdit(cast)}>
                      <Pencil className='mr-2 h-4 w-4' />
                      编辑订阅
                    </DropdownMenuItem>
                  ) : null}

                  {resolvedSubscribeItem?.status === 'active' ? (
                    <DropdownMenuItem onClick={() => pauseMutation.mutate()}>
                      <Pause className='mr-2 h-4 w-4' />
                      暂停订阅
                    </DropdownMenuItem>
                  ) : null}
                  {resolvedSubscribeItem?.status === 'paused' ? (
                    <DropdownMenuItem onClick={() => resumeMutation.mutate()}>
                      <StepForward className='mr-2 h-4 w-4' />
                      恢复订阅
                    </DropdownMenuItem>
                  ) : null}
                  {resolvedSubscribeItem && resolvedSubscribeItem.status !== 'canceled' ? (
                    <DropdownMenuItem
                      className='text-destructive focus:text-destructive'
                      onClick={() => cancelMutation.mutate()}
                    >
                      <CircleX className='mr-2 h-4 w-4' />
                      取消订阅
                    </DropdownMenuItem>
                  ) : null}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          {resolvedSubscribeItem ? (
            <div className='flex flex-wrap gap-2 text-xs text-muted-foreground'>
              {showCreatedTime ? (
                <span className='rounded-full bg-muted px-2 py-1'>创建时间：{resolvedSubscribeItem.create_time || '-'}</span>
              ) : null}
              <span className='rounded-full bg-muted px-2 py-1'>最大共演人数：{resolvedSubscribeItem.max_coactors ?? '不限'}</span>
              <span className='rounded-full bg-muted px-2 py-1'>最大页数：{resolvedSubscribeItem.max_page ?? '不限'}</span>
              <span className='rounded-full bg-muted px-2 py-1'>替换最大页数：{resolvedSubscribeItem.replace_max_page ?? '否'}</span>
              <span className='rounded-full bg-muted px-2 py-1'>仅单体：{resolvedSubscribeItem.is_single ? '是' : '否'}</span>
              <span className='rounded-full bg-muted px-2 py-1'>最早发布日期：{resolvedSubscribeItem.earliest_release_date || '不限'}</span>
              <span className='rounded-full bg-muted px-2 py-1'>排除 VR：{resolvedSubscribeItem.exclude_vr ? '是' : '否'}</span>
            </div>
          ) : (
            <div className='text-xs text-muted-foreground'>可从此处直接创建演员订阅</div>
          )}

          {aliases.length > 0 ? (
            <div className='text-sm text-muted-foreground'>曾用名：{aliases.join(' / ')}</div>
          ) : null}
        </div>
      </div>
    </Card>
  )
}
