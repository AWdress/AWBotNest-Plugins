import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, SearchIcon, UserPen, UserPlus } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from 'recharts'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart.tsx'
import {
  getMovieFrequencyStats,
  type MovieFrequencyStatItem,
} from '@/api/movie.ts'
import type { Cast } from '@/api/cast.ts'
import { LazyImage } from '@/components/lazy-image.tsx'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card.tsx'
import { Loading } from '@/components/loading.tsx'
import { useImageMode } from '@/context/image-mode-provider.tsx'
import { useIsMobile } from '@/hooks/use-mobile.tsx'
import { cn } from '@/lib/utils.ts'
import { useSearch } from '@/context/search-provider.tsx'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu.tsx'
import { CastSubscribeDialog } from '@/features/rank/cast/subscribe-dialog.tsx'

const BAR_COLORS = ['#f97316', '#fb7185', '#38bdf8', '#34d399', '#a78bfa']

const chartConfig = {
  count: {
    label: '数量',
    color: '#f97316',
  },
}

function formatDisplayName(name: string, limit = 8) {
  return name.length > limit ? `${name.slice(0, limit)}...` : name
}

function ProgressBar({ width, color }: { width: string; color: string }) {
  return (
    <div className='w-full min-w-0 overflow-hidden rounded-full bg-muted'>
      <div
        className='h-2.5 max-w-full rounded-full transition-all duration-500'
        style={{ width, backgroundColor: color }}
      />
    </div>
  )
}

function FrequencyList({
  data,
  compact = false,
}: {
  data: MovieFrequencyStatItem[]
  compact?: boolean
}) {
  const maxCount = Math.max(...data.map((item) => item.count), 1)

  return (
    <div className={cn('w-full min-w-0 space-y-2', compact && 'space-y-1.5')}>
      {data.map((item, index) => {
        const width = `${Math.max((item.count / maxCount) * 100, 8)}%`
        return (
          <div
            key={`${item.name}-${index}`}
            className={cn(
              'w-full min-w-0 overflow-hidden rounded-2xl border border-border/60 bg-background/60 px-3 py-2.5',
              compact && 'px-2.5 py-2'
            )}
          >
            <div className='mb-2 flex min-w-0 items-center justify-between gap-3'>
              <div className='min-w-0 flex-1 truncate text-sm font-medium'>
                {item.name}
              </div>
              <div className='shrink-0 text-sm font-semibold tabular-nums text-foreground'>
                {item.count}
              </div>
            </div>
            <ProgressBar
              width={width}
              color={BAR_COLORS[index % BAR_COLORS.length]}
            />
          </div>
        )
      })}
    </div>
  )
}

function FrequencyBarChart({
  title,
  data,
  isMobile,
}: {
  title: string
  data: MovieFrequencyStatItem[]
  isMobile: boolean
}) {
  return (
    <Card className='min-w-0 border-none shadow-none'>
      <CardHeader className='pb-2'>
        <CardTitle className='text-base'>{title}</CardTitle>
      </CardHeader>
      <CardContent className={cn('min-w-0', isMobile ? 'px-0 pt-1' : 'h-80')}>
        {data.length === 0 ? (
          <div className='rounded-2xl border border-dashed border-border/80 bg-background/60 px-4 py-8 text-center text-sm text-muted-foreground'>
            暂无统计数据
          </div>
        ) : isMobile ? (
          <FrequencyList data={data} compact />
        ) : (
          <ChartContainer config={chartConfig} className='h-80 w-full min-w-0'>
            <BarChart
              data={data}
              layout='vertical'
              margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
            >
              <CartesianGrid horizontal={false} strokeDasharray='3 3' />
              <XAxis type='number' allowDecimals={false} />
              <YAxis
                type='category'
                dataKey='name'
                width={72}
                tickLine={false}
                axisLine={false}
                interval={0}
                tickFormatter={(value: string) => formatDisplayName(value)}
              />
              <ChartTooltip
                cursor={false}
                content={<ChartTooltipContent hideLabel />}
              />
              <Bar dataKey='count' radius={6} maxBarSize={22}>
                {data.map((item, index) => (
                  <Cell
                    key={`${item.name}-${index}`}
                    fill={BAR_COLORS[index % BAR_COLORS.length]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  )
}

function buildCastFromStat(item: MovieFrequencyStatItem): Cast {
  return {
    id: item.id || 0,
    name: item.name,
    cn_name: item.name,
    avatar: item.avatar || '',
    photo: item.avatar || '',
    former_name: [],
    subscribe: item.subscribe || null,
  }
}

function ActorAvatar({ item, isMobile }: { item: MovieFrequencyStatItem; isMobile: boolean }) {
  const { mode } = useImageMode()
  const [imageError, setImageError] = useState(false)
  const canShowImage = mode !== 'hide' && item.avatar && !imageError

  return (
    <div
      className={cn(
        'shrink-0 overflow-hidden rounded-full border border-border/70 bg-muted',
        isMobile ? 'h-10 w-10' : 'h-12 w-12'
      )}
    >
      {canShowImage ? (
        <LazyImage
          src={item.avatar}
          alt={item.name}
          referrerPolicy='no-referrer'
          className={cn(
            'h-full w-full object-cover transition-all duration-300',
            mode === 'blur' && 'blur-md'
          )}
          onError={() => setImageError(true)}
        />
      ) : (
        <div className='flex h-full w-full items-center justify-center text-sm font-semibold text-muted-foreground'>
          {item.name.slice(0, 1)}
        </div>
      )}
    </div>
  )
}

function ActorActionMenu({
  item,
  children,
  onCreate,
  onEdit,
}: {
  item: MovieFrequencyStatItem
  children: React.ReactNode
  onCreate: (cast: Cast) => void
  onEdit: (cast: Cast) => void
}) {
  const { handleSearch } = useSearch()
  const cast = buildCastFromStat(item)
  const subscribeItem = cast.subscribe
    ? { ...cast.subscribe, cast }
    : null

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent align='start' className='w-52 bg-background/20 backdrop-blur-md'>
        <div className='px-2 py-1.5 text-xs font-medium text-muted-foreground'>
          {item.name}
        </div>
        <DropdownMenuItem onClick={() => handleSearch(item.name, { target: 'articles' })}>
          <SearchIcon className='mr-2 h-4 w-4' />
          搜索资源库
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleSearch(item.name, { target: 'movie-search' })}>
          <SearchIcon className='mr-2 h-4 w-4' />
          搜索影片库
        </DropdownMenuItem>
        {subscribeItem ? (
          <DropdownMenuItem onClick={() => onEdit(cast)}>
            <UserPen className='mr-2 h-4 w-4' />
            编辑订阅
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem onClick={() => onCreate(cast)}>
            <UserPlus className='mr-2 h-4 w-4' />
            订阅演员
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function ActorFrequencyChart({
  data,
  isMobile,
}: {
  data: MovieFrequencyStatItem[]
  isMobile: boolean
}) {
  const maxCount = Math.max(...data.map((item) => item.count), 1)
  const [selectedCast, setSelectedCast] = useState<Cast | null>(null)
  const [castDialogOpen, setCastDialogOpen] = useState(false)

  return (
    <>
      <Card className='min-w-0 border-none shadow-none'>
        <CardHeader className='pb-2'>
          <CardTitle className='text-base'>高频演员</CardTitle>
          <CardDescription>按已订阅或已完成影片的关联演员统计</CardDescription>
        </CardHeader>
        <CardContent className={cn('min-w-0', isMobile ? 'px-0 pt-1' : 'h-80')}>
          {data.length === 0 ? (
            <div className='rounded-2xl border border-dashed border-border/80 bg-background/60 px-4 py-8 text-center text-sm text-muted-foreground'>
              暂无统计数据
            </div>
          ) : (
            <div
              className={cn(
                'min-w-0 space-y-2',
                isMobile
                  ? 'max-h-none overflow-visible'
                  : 'scrollbar-hide h-full overflow-y-auto pr-1'
              )}
            >
              {data.map((item, index) => {
                const width = `${Math.max((item.count / maxCount) * 100, 8)}%`
                return (
                  <div
                    key={`${item.name}-${index}`}
                    className={cn(
                      'flex w-full min-w-0 items-center gap-3 overflow-hidden rounded-2xl border border-border/60 bg-background/60 px-3 py-2.5',
                      isMobile && 'px-2.5 py-2'
                    )}
                  >
                    <ActorActionMenu
                      item={item}
                      onCreate={(cast) => {
                        setSelectedCast(cast)
                        setCastDialogOpen(true)
                      }}
                      onEdit={(cast) => {
                        setSelectedCast(cast)
                        setCastDialogOpen(true)
                      }}
                    >
                      <button type='button' className='shrink-0'>
                        <ActorAvatar item={item} isMobile={isMobile} />
                      </button>
                    </ActorActionMenu>
                    <div className='min-w-0 flex-1 space-y-2'>
                      <div className='flex min-w-0 items-center justify-between gap-3'>
                        <div className='min-w-0 flex-1'>
                          <ActorActionMenu
                            item={item}
                            onCreate={(cast) => {
                              setSelectedCast(cast)
                              setCastDialogOpen(true)
                            }}
                            onEdit={(cast) => {
                              setSelectedCast(cast)
                              setCastDialogOpen(true)
                            }}
                          >
                            <button type='button' className='min-w-0 max-w-full text-left'>
                              <div className='truncate text-sm font-medium hover:text-primary'>
                                {item.subscribe ? `🎭 ${item.name}` : item.name}
                              </div>
                            </button>
                          </ActorActionMenu>
                          <div className='text-xs text-muted-foreground'>
                            第 {index + 1} 位
                          </div>
                        </div>
                        <div className='shrink-0 text-sm font-semibold tabular-nums text-foreground'>
                          {item.count}
                        </div>
                      </div>
                      <ProgressBar
                        width={width}
                        color={BAR_COLORS[index % BAR_COLORS.length]}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <CastSubscribeDialog
        cast={selectedCast}
        open={castDialogOpen}
        onOpenChange={(openValue) => {
          setCastDialogOpen(openValue)
          if (!openValue) {
            setSelectedCast(null)
          }
        }}
      />
    </>
  )
}

export function MovieFrequencyStatsPanel() {
  const isMobile = useIsMobile()
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', 'movie-frequency-stats'],
    queryFn: async () => {
      const res = await getMovieFrequencyStats()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  return (
    <Card className='overflow-hidden border-sky-500/20 bg-linear-to-br from-sky-500/8 via-background to-background'>
      <CardHeader className='space-y-2'>
        <div className='flex items-center gap-3'>
          <div className='rounded-xl bg-sky-500/12 p-2.5 text-sky-500'>
            <BarChart3 className='h-5 w-5' />
          </div>
          <div className='min-w-0'>
            <CardTitle>已订阅影片频次趋势</CardTitle>
          </div>
        </div>
      </CardHeader>
      <CardContent className='min-w-0'>
        {isLoading ? (
          <Loading />
        ) : (
          <div className='grid min-w-0 gap-4 md:gap-6 xl:grid-cols-3'>
            <ActorFrequencyChart
              data={data?.actors || []}
              isMobile={isMobile}
            />
            <FrequencyBarChart
              title='高频制作商'
              data={data?.producers || []}
              isMobile={isMobile}
            />
            <FrequencyBarChart
              title='高频系列'
              data={data?.series || []}
              isMobile={isMobile}
            />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
