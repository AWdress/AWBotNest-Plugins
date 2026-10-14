import { type ReactNode, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  Building2,
  CalendarIcon,
  CircleX,
  Clock,
  Download,
  Heart,
  ImageIcon,
  Layers,
  MoreVertical,
  Pause,
  Pencil,
  SearchIcon,
  StepForward,
  Tag,
  UserPen,
  UserPlus,
} from 'lucide-react'
import type { Cast } from '@/api/cast.ts'
import { type Movie } from '@/api/movie.ts'
import {
  cancelSub,
  executeSubscribeDownload,
  pauseSubscribe,
  resumeSubscribe,
} from '@/api/subscribe.ts'
import { cn } from '@/lib/utils.ts'
import { useImageMode } from '@/context/image-mode-provider.tsx'
import { useSearch } from '@/context/search-provider.tsx'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button.tsx'
import { Card } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu.tsx'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { LazyImage } from '@/components/lazy-image'
import { MOVIE_SUBSCRIPTION_QUERY_KEYS } from '@/lib/subscription-query-keys.ts'

const RANK_CONFIG: Record<
  number,
  { bg: string; text: string; ring: string; glow: string; label: string }
> = {
  1: {
    label: '壹',
    bg: 'bg-gradient-to-r from-yellow-300 via-amber-400 to-yellow-500',
    text: 'text-yellow-900',
    ring: 'ring-1 ring-yellow-400/60',
    glow: 'md:shadow-[0_0_20px_2px_rgba(251,191,36,0.30)]',
  },
  2: {
    label: '貳',
    bg: 'bg-gradient-to-r from-slate-200 via-gray-300 to-slate-400',
    text: 'text-slate-700',
    ring: 'ring-1 ring-slate-300/60',
    glow: 'md:shadow-[0_0_14px_2px_rgba(148,163,184,0.25)]',
  },
  3: {
    label: '叁',
    bg: 'bg-gradient-to-r from-orange-300 via-amber-500 to-orange-500',
    text: 'text-orange-950',
    ring: 'ring-1 ring-orange-400/50',
    glow: 'md:shadow-[0_0_14px_2px_rgba(251,146,60,0.25)]',
  },
}

const STATUS_CONFIG: Record<
  Movie['status'],
  { label: string; className: string; overlayClassName: string }
> = {
  active: {
    label: '订阅中',
    className: 'bg-emerald-500/15 text-emerald-500 border-emerald-500/30',
    overlayClassName:
      'border-emerald-400/50 bg-emerald-500/95 text-white backdrop-blur-md shadow-md shadow-black/50',
  },
  paused: {
    label: '已暂停',
    className: 'bg-amber-500/15 text-amber-500 border-amber-500/30',
    overlayClassName:
      'border-amber-400/50 bg-amber-500/95 text-white backdrop-blur-md shadow-md shadow-black/50',
  },
  completed: {
    label: '已完成',
    className: 'bg-blue-500/15 text-blue-500 border-blue-500/30',
    overlayClassName:
      'border-blue-400/50 bg-blue-500/95 text-white backdrop-blur-md shadow-md shadow-black/50',
  },
  released: {
    label: '未订阅',
    className: 'bg-muted/60 text-muted-foreground border-border',
    overlayClassName:
      'border-white/20 bg-black/75 text-white backdrop-blur-md shadow-md shadow-black/50',
  },
  canceled: {
    label: '已取消',
    className: 'bg-muted/60 text-muted-foreground border-border',
    overlayClassName:
      'border-zinc-600/50 bg-zinc-800/90 text-zinc-300 backdrop-blur-md shadow-md shadow-black/50',
  },
}

function formatDuration(minutes?: number) {
  if (!minutes) return null
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h > 0) return `${h}h ${m}m`
  return `${m}min`
}

function getCastDisplayName(cast: Cast) {
  return cast.cn_name || cast.name
}

function CastAvatar({
  cast,
}: {
  cast: Cast
}) {
  const [err, setErr] = useState(false)
  const displayName = getCastDisplayName(cast)

  return !err && cast.avatar ? (
    <LazyImage
      src={cast.avatar}
      alt={displayName}
      referrerPolicy='no-referrer'
      className='h-full w-full object-cover'
      onError={() => setErr(true)}
    />
  ) : (
    <div className='flex h-full w-full items-center justify-center bg-muted text-[10px] font-medium text-muted-foreground'>
      {displayName.slice(0, 1)}
    </div>
  )
}

function CastActionMenu({
  cast,
  onSearchResources,
  onSearchMovies,
  onCreateSubscribe,
  onEditSubscribe,
  children,
}: {
  cast: Cast
  onSearchResources: (keyword: string) => void
  onSearchMovies: (keyword: string) => void
  onCreateSubscribe?: (cast: Cast) => void
  onEditSubscribe?: (cast: Cast) => void
  children: ReactNode
}) {
  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent align='start' className='w-52 bg-background/20 backdrop-blur-md'>
        <div className='px-2 py-1.5 text-xs font-medium text-muted-foreground'>
          {getCastDisplayName(cast)}
        </div>
        <DropdownMenuItem onClick={() => onSearchResources(cast.name)}>
          <SearchIcon className='mr-2 h-4 w-4' />
          搜索资源库
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onSearchMovies(cast.name)}>
          <SearchIcon className='mr-2 h-4 w-4' />
          搜索影片库
        </DropdownMenuItem>
        {cast.subscribe && onEditSubscribe ? (
          <DropdownMenuItem onClick={() => onEditSubscribe(cast)}>
            <UserPen className='mr-2 h-4 w-4' />
            编辑订阅
          </DropdownMenuItem>
        ) : onCreateSubscribe ? (
          <DropdownMenuItem onClick={() => onCreateSubscribe(cast)}>
            <UserPlus className='mr-2 h-4 w-4' />
            订阅演员
          </DropdownMenuItem>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function MovieCard({
  movie,
  index,
  onImgClick,
  onSubscribe,
  onEditSubscribe,
  onCreateCastSubscribe,
  onEditCastSubscribe,
}: {
  movie: Movie
  index?: number
  onImgClick?: () => void
  onSubscribe: () => void
  onEditSubscribe?: (movie: Movie) => void
  onCreateCastSubscribe?: (cast: Cast) => void
  onEditCastSubscribe?: (cast: Cast) => void
}) {
  const [imageError, setImageError] = useState(false)
  const { mode } = useImageMode()
  const rank = typeof index === 'number' ? index + 1 : null
  const isTop3 = rank !== null && rank <= 3
  const rankCfg = isTop3 && rank ? RANK_CONFIG[rank] : null
  const statusCfg = STATUS_CONFIG[movie.status]
  const duration = formatDuration(movie.duration)
  const queryClient = useQueryClient()
  const { handleSearch } = useSearch()
  const subscribeId = movie.subscribe_id ?? movie.id
  const visibleCasts = movie.casts?.slice(0, 5) ?? []

  const handleMovieSearch = () => {
    handleSearch(movie.number || movie.cn_title || movie.title, { target: 'articles' })
  }

  const handleCastResourceSearch = (castName: string) => {
    handleSearch(castName, { target: 'articles' })
  }

  const handleCastMovieSearch = (castName: string) => {
    handleSearch(castName, { target: 'movie-search' })
  }

  const invalidate = () => {
    for (const queryKey of MOVIE_SUBSCRIPTION_QUERY_KEYS) {
      queryClient.invalidateQueries({
        queryKey,
        exact: false,
      })
    }
  }

  const handleCancelSub = () => {
    cancelSub(subscribeId).then((r) => {
      if (r.code === 0) {
        invalidate()
      }
    })
  }

  const handlePauseSub = () => {
    pauseSubscribe(subscribeId).then((r) => {
      if (r.code === 0) {
        invalidate()
      }
    })
  }

  const handleResumeSub = () => {
    resumeSubscribe(subscribeId).then((r) => {
      if (r.code === 0) {
        invalidate()
      }
    })
  }

  const [isExecutingSubscribe, setIsExecutingSubscribe] = useState(false)

  const handleExecuteSubscribeDownload = async () => {
    if (isExecutingSubscribe) return

    setIsExecutingSubscribe(true)
    try {
      const response = await executeSubscribeDownload(subscribeId)
      if (response.code !== 0) {
        return
      }

      if (response.data?.success) {
        toast.success(response.message || '已执行订阅下载')
      } else {
        toast.error(response.data?.message || response.message || '执行订阅下载失败')
      }

      invalidate()
    } finally {
      setIsExecutingSubscribe(false)
    }
  }

  return (
    <Card className='group glass-card relative flex w-full max-w-full cursor-pointer flex-col gap-0 overflow-hidden rounded-none border-0 py-0 shadow-none ring-0 transition-all duration-300 md:rounded-2xl'>
      {movie.banner && mode !== 'hide' && (
        <div
          className='relative w-full cursor-pointer overflow-hidden'
          onClick={onImgClick}
        >
          {!imageError ? (
            <>
              <LazyImage
                src={movie.banner}
                alt={movie.title}
                className={`h-full w-full object-cover transition-all duration-500 group-hover:scale-110 ${
                  mode === 'blur' ? 'blur-md' : ''
                }`}
                onError={() => setImageError(true)}
              />

              {movie.still_photos && movie.still_photos.length > 1 && (
                <div className='absolute right-2 bottom-2 flex items-center gap-1 rounded-full bg-black/70 px-2 py-1 text-xs text-white backdrop-blur-sm'>
                  <ImageIcon className='h-3 w-3' />
                  {movie.still_photos.length}
                </div>
              )}

              <div className='absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 transition-opacity duration-300 group-hover:opacity-100'>
                <div className='rounded-full bg-white/20 p-3 backdrop-blur-sm'>
                  <ImageIcon className='h-6 w-6 text-white' />
                </div>
              </div>
            </>
          ) : (
            <div className='flex h-40 w-full items-center justify-center bg-muted'>
              <ImageIcon className='h-12 w-12 text-muted-foreground/30' />
            </div>
          )}

          {rankCfg && (
            <div
              className={cn(
                'absolute top-2.5 left-2.5 flex items-center justify-center rounded-full px-2.5 py-0.5 text-[11px] font-black tracking-widest',
                rankCfg.bg,
                rankCfg.text,
                rankCfg.ring
              )}
            >
              {rankCfg.label}
            </div>
          )}

          <div className='absolute top-2.5 right-2 flex items-center'>
            <span
              className={cn(
                'rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-wide',
                statusCfg.overlayClassName
              )}
            >
              {statusCfg.label}
            </span>
          </div>
        </div>
      )}

      <div className='relative flex flex-col gap-3 px-4 pt-3 pb-4'>
        <div className='absolute top-2 right-2 z-10'>
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <Button
                size='icon'
                variant='ghost'
                className='h-8 w-8 rounded-full'
                onClick={(e) => e.stopPropagation()}
              >
                <MoreVertical className='h-4 w-4' />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align='end'
              className='w-40 bg-background/20 backdrop-blur-md'
            >
              <DropdownMenuItem onClick={handleMovieSearch}>
                <SearchIcon className='mr-2 h-4 w-4' />
                搜索资源库
              </DropdownMenuItem>
              {(movie.status === 'released' || movie.status === 'canceled' || movie.status === 'completed') && (
                <DropdownMenuItem onClick={onSubscribe}>
                  <Heart className='mr-2 h-4 w-4' />
                  订阅影片
                </DropdownMenuItem>
              )}

              {onEditSubscribe && (movie.status === 'active' || movie.status === 'paused') && (
                <DropdownMenuItem onClick={() => onEditSubscribe(movie)}>
                  <Pencil className='mr-2 h-4 w-4' />
                  编辑订阅
                </DropdownMenuItem>
              )}
              {(movie.status === 'active' || movie.status === 'paused') && (
                <DropdownMenuItem
                  onClick={handleExecuteSubscribeDownload}
                  disabled={isExecutingSubscribe}
                >
                  <Download className='mr-2 h-4 w-4' />
                  {isExecutingSubscribe ? '执行中...' : '执行订阅'}
                </DropdownMenuItem>
              )}
              {movie.status === 'active' && (
                <>
                  <DropdownMenuItem onClick={handlePauseSub}>
                    <Pause className='mr-2 h-4 w-4' />
                    暂停订阅
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleCancelSub} className='text-destructive focus:text-destructive'>
                    <CircleX className='mr-2 h-4 w-4' />
                    取消订阅
                  </DropdownMenuItem>
                </>
              )}
              {movie.status === 'paused' && (
                <>
                  <DropdownMenuItem onClick={handleResumeSub}>
                    <StepForward className='mr-2 h-4 w-4' />
                    恢复订阅
                  </DropdownMenuItem>

                  <DropdownMenuItem onClick={handleCancelSub} className='text-destructive focus:text-destructive'>
                    <CircleX className='mr-2 h-4 w-4' />
                    取消订阅
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className='flex flex-wrap items-center gap-1.5 pr-8'>
          <span
            className={cn(
              'rounded-full px-2.5 py-0.5 font-mono text-[12px] font-medium shadow-sm',
              rankCfg?.bg,
              rankCfg?.text,
              rankCfg?.ring,
              !rankCfg && 'bg-secondary text-secondary-foreground'
            )}
          >
            {movie.number}
          </span>

          {movie.in_library === true && (
            <span className='rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-500'>
              已入库
            </span>
          )}

          {(!movie.banner || mode === 'hide') && (
            <span
              className={cn(
                'rounded-full border px-2 py-0.5 text-[10px] font-medium',
                statusCfg.className
              )}
            >
              {statusCfg.label}
            </span>
          )}

          {movie.release_date && (
            <span className='flex items-center gap-1 text-xs text-muted-foreground'>
              <CalendarIcon className='h-3 w-3' />
              {movie.release_date}
            </span>
          )}

          {duration && (
            <span className='flex items-center gap-1 text-xs text-muted-foreground'>
              <Clock className='h-3 w-3' />
              {duration}
            </span>
          )}
        </div>

        <div className='flex flex-col gap-0.5 pr-8'>
          <h6 className='line-clamp-2 text-sm leading-snug font-semibold wrap-break-word'>
            {movie.cn_title || movie.title}
          </h6>
          {movie.cn_title && movie.title && movie.cn_title !== movie.title && (
            <p className='line-clamp-1 text-xs text-muted-foreground/70'>
              {movie.title}
            </p>
          )}
        </div>

        {visibleCasts.length > 0 && (
          <div className='space-y-2'>
            {mode !== 'hide' && (
              <div className='flex items-center gap-2'>
                <div className='flex -space-x-1.5'>
                  {visibleCasts.map((cast) => {
                    const displayName = getCastDisplayName(cast)
                    return (
                      <Tooltip key={cast.id}>
                        <TooltipTrigger asChild>
                          <CastActionMenu
                            cast={cast}
                            onSearchResources={handleCastResourceSearch}
                            onSearchMovies={handleCastMovieSearch}
                            onCreateSubscribe={onCreateCastSubscribe}
                            onEditSubscribe={onEditCastSubscribe}
                          >
                            <button
                              type='button'
                              className='relative h-12 w-12 shrink-0 overflow-hidden rounded-full ring-1 ring-border transition-transform hover:scale-110 hover:ring-primary/60'
                            >
                              <CastAvatar cast={cast} />
                            </button>
                          </CastActionMenu>
                        </TooltipTrigger>
                        <TooltipContent side='top' className='text-xs'>
                          {displayName}
                          {cast.cn_name && cast.name !== cast.cn_name && (
                            <span className='ml-1 text-muted-foreground'>({cast.name})</span>
                          )}
                        </TooltipContent>
                      </Tooltip>
                    )
                  })}
                </div>
                {movie.casts && movie.casts.length > 5 && (
                  <span className='text-xs text-muted-foreground'>
                    +{movie.casts.length - 5}
                  </span>
                )}
              </div>
            )}
            </div>
          )}

          <div className='h-px w-full bg-border/50' />

          <div className='flex flex-col gap-1.5 text-xs text-muted-foreground'>
            {movie.producer && (
              <div className='flex items-center gap-1.5'>
                <Building2 className='h-3 w-3 shrink-0' />
                <span className='truncate'>{movie.producer}</span>
              </div>
            )}


          {movie.publisher && movie.publisher !== movie.producer && (
            <div className='flex items-center gap-1.5'>
              <Tag className='h-3 w-3 shrink-0' />
              <span className='truncate'>{movie.publisher}</span>
            </div>
          )}
          {movie.series && (
            <div className='flex items-center gap-1.5'>
              <Layers className='h-3 w-3 shrink-0' />
              <span className='truncate'>{movie.series}</span>
            </div>
          )}
        </div>

        {movie.genres && movie.genres.length > 0 && (
          <div className='flex flex-wrap gap-1'>
            {movie.genres.slice(0, 5).map((g) => (
              <Badge
                key={g}
                variant='secondary'
                className='px-1.5 py-0 text-[10px] font-normal'
              >
                {g}
              </Badge>
            ))}
            {movie.genres.length > 5 && (
              <span className='self-center text-[10px] text-muted-foreground'>
                +{movie.genres.length - 5}
              </span>
            )}
          </div>
        )}

        {(movie.cn_description || movie.description) && (
          <p className='line-clamp-2 text-xs leading-relaxed text-muted-foreground/80'>
            {movie.cn_description || movie.description}
          </p>
        )}
      </div>
    </Card>
  )
}
