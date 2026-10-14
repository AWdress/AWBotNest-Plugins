import { useMemo, useRef, useState, useEffect, type ComponentType } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Film, Loader2, SearchIcon, Sparkles, Users } from 'lucide-react'
import type { Cast } from '@/api/cast.ts'
import { type Movie } from '@/api/movie.ts'
import { fetchCastSubscribesPage, fetchSubscribesPage } from '@/api/subscribe.ts'
import { useDebounce } from '@/hooks/use-debounce.tsx'
import { useIsMobile } from '@/hooks/use-mobile.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { EmptyState } from '@/components/empty.tsx'
import { ImagePreview } from '@/components/image-preview.tsx'
import { Loading } from '@/components/loading.tsx'
import { CommonPagination } from '@/components/pagination.tsx'
import { CastSubscribeDialog } from '@/features/rank/cast/subscribe-dialog.tsx'
import { MovieCard } from '@/features/rank/movie/movie-card.tsx'
import { SubscribeDialog } from '@/features/rank/movie/subscribe-dialog.tsx'
import { CastCard } from '@/features/subscribes/cast-subscribe-card.tsx'
import { GeneralSubscribePanel } from '@/features/subscribes/general-subscribe-panel.tsx'

type SubscribeEntityTab = 'movie' | 'cast' | 'general'
type MovieSubscribeStatusTab = 'active' | 'completed' | 'paused'
type CastSubscribeStatusTab = 'active' | 'paused'
type GeneralSubscribeStatusTab = 'active' | 'paused'

const ENTITY_TABS: Array<{
  value: SubscribeEntityTab
  label: string
  mobileLabel: string
  icon: ComponentType<{ className?: string }>
}> = [
  { value: 'movie', label: '影片订阅', mobileLabel: '影片', icon: Film },
  { value: 'cast', label: '演员订阅', mobileLabel: '演员', icon: Users },
  { value: 'general', label: '综合订阅', mobileLabel: '综合', icon: Sparkles },
]

const MOVIE_STATUS_TABS: Array<{
  value: MovieSubscribeStatusTab
  label: string
}> = [
  { value: 'active', label: '订阅中' },
  { value: 'completed', label: '已完成' },
  { value: 'paused', label: '已暂停' },
]

const CAST_STATUS_TABS: Array<{
  value: CastSubscribeStatusTab
  label: string
}> = [
  { value: 'active', label: '订阅中' },
  { value: 'paused', label: '已暂停' },
]

const GENERAL_STATUS_TABS: Array<{
  value: GeneralSubscribeStatusTab
  label: string
}> = [
  { value: 'active', label: '订阅中' },
  { value: 'paused', label: '已暂停' },
]

export function SubscribeList() {
  const isMobile = useIsMobile()
  const [entityType, setEntityType] = useState<SubscribeEntityTab>('movie')
  const [movieStatus, setMovieStatus] =
    useState<MovieSubscribeStatusTab>('active')
  const [castStatus, setCastStatus] = useState<CastSubscribeStatusTab>('active')
  const [generalStatus, setGeneralStatus] =
    useState<GeneralSubscribeStatusTab>('active')
  const [generalTotal, setGeneralTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const debouncedKeyword = useDebounce(keyword, 300)

  const [previewImages, setPreviewImages] = useState<string[]>([])
  const [imgPreviewOpen, setImgPreviewOpen] = useState(false)
  const [alt, setAlt] = useState('')
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editMovie, setEditMovie] = useState<Movie | null>(null)
  const [editCastDialogOpen, setEditCastDialogOpen] = useState(false)
  const [editCast, setEditCast] = useState<Cast | null>(null)
  const loadMoreRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPage(1)
  }, [entityType, movieStatus, castStatus, generalStatus, debouncedKeyword])

  const desktopMovieQuery = useQuery({
    queryKey: [
      'subscribes',
      'movie',
      'desktop',
      movieStatus,
      debouncedKeyword,
      page,
    ],
    queryFn: async () => {
      const res = await fetchSubscribesPage({
        page,
        pageSize: 20,
        keyword: debouncedKeyword || undefined,
        status: movieStatus,
      })
      return res.data
    },
    enabled: !isMobile && entityType === 'movie',
    staleTime: 60 * 1000,
  })

  const desktopCastQuery = useQuery({
    queryKey: [
      'cast-subscribes',
      'desktop',
      castStatus,
      debouncedKeyword,
      page,
    ],
    queryFn: async () => {
      const res = await fetchCastSubscribesPage({
        page,
        pageSize: 20,
        keyword: debouncedKeyword || undefined,
        status: castStatus,
      })
      return res.data
    },
    enabled: !isMobile && entityType === 'cast',
    staleTime: 60 * 1000,
  })

  const mobileMovieQuery = useInfiniteQuery({
    queryKey: ['subscribes', 'movie', 'mobile', movieStatus, debouncedKeyword],
    queryFn: async ({ pageParam = 1 }) => {
      const res = await fetchSubscribesPage({
        page: pageParam,
        pageSize: 12,
        keyword: debouncedKeyword || undefined,
        status: movieStatus,
      })
      return res.data
    },
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? lastPage.page + 1 : undefined,
    initialPageParam: 1,
    enabled: isMobile && entityType === 'movie',
    staleTime: 60 * 1000,
  })

  const mobileCastQuery = useInfiniteQuery({
    queryKey: ['cast-subscribes', 'mobile', castStatus, debouncedKeyword],
    queryFn: async ({ pageParam = 1 }) => {
      const res = await fetchCastSubscribesPage({
        page: pageParam,
        pageSize: 12,
        keyword: debouncedKeyword || undefined,
        status: castStatus,
      })
      return res.data
    },
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? lastPage.page + 1 : undefined,
    initialPageParam: 1,
    enabled: isMobile && entityType === 'cast',
    staleTime: 60 * 1000,
  })

  const activeMobileQuery =
    entityType === 'movie' ? mobileMovieQuery : mobileCastQuery
  const activeStatusTabs =
    entityType === 'movie'
      ? MOVIE_STATUS_TABS
      : entityType === 'cast'
        ? CAST_STATUS_TABS
        : GENERAL_STATUS_TABS
  const activeStatusValue =
    entityType === 'movie'
      ? movieStatus
      : entityType === 'cast'
        ? castStatus
        : generalStatus

  useEffect(() => {
    if (!isMobile || entityType === 'general' || !loadMoreRef.current) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (
          entry.isIntersecting &&
          activeMobileQuery.hasNextPage &&
          !activeMobileQuery.isFetchingNextPage
        ) {
          activeMobileQuery.fetchNextPage()
        }
      },
      { root: null, rootMargin: '120px' }
    )
    observer.observe(loadMoreRef.current)
    return () => observer.disconnect()
  }, [activeMobileQuery, entityType, isMobile])

  const movieItems = useMemo(() => {
    if (entityType !== 'movie') return []
    if (isMobile) {
      return (
        mobileMovieQuery.data?.pages.flatMap((result) => result.items) || []
      )
    }
    return desktopMovieQuery.data?.items || []
  }, [
    desktopMovieQuery.data?.items,
    entityType,
    isMobile,
    mobileMovieQuery.data?.pages,
  ])

  const castItems = useMemo<Cast[]>(() => {
    if (entityType !== 'cast') return []
    if (isMobile) {
      return mobileCastQuery.data?.pages.flatMap((result) => result.items) || []
    }
    return desktopCastQuery.data?.items || []
  }, [
    desktopCastQuery.data?.items,
    entityType,
    isMobile,
    mobileCastQuery.data?.pages,
  ])

  const total = useMemo(() => {
    if (entityType === 'general') {
      return generalTotal
    }
    if (entityType === 'movie') {
      return isMobile
        ? (mobileMovieQuery.data?.pages[0]?.total ?? 0)
        : (desktopMovieQuery.data?.total ?? 0)
    }
    return isMobile
      ? (mobileCastQuery.data?.pages[0]?.total ?? 0)
      : (desktopCastQuery.data?.total ?? 0)
  }, [
    desktopCastQuery.data?.total,
    desktopMovieQuery.data?.total,
    entityType,
    generalTotal,
    isMobile,
    mobileCastQuery.data?.pages,
    mobileMovieQuery.data?.pages,
  ])

  const pageSize =
    entityType === 'movie'
      ? desktopMovieQuery.data?.pageSize || 20
      : entityType === 'cast'
        ? desktopCastQuery.data?.pageSize || 20
        : 20

  const isLoading =
    entityType === 'general'
      ? false
      : entityType === 'movie'
        ? isMobile
          ? mobileMovieQuery.isLoading
          : desktopMovieQuery.isLoading
        : isMobile
          ? mobileCastQuery.isLoading
          : desktopCastQuery.isLoading

  const placeholder =
    entityType === 'movie'
      ? '搜索番号、标题、描述、演员姓名'
      : entityType === 'cast'
        ? '搜索演员姓名'
        : '搜索番号前缀、发行商、系列、制作商、类型'
  const hasItems =
    entityType === 'general'
      ? true
      : entityType === 'movie'
        ? movieItems.length > 0
        : castItems.length > 0

  return (
    <div className='-mx-4 flex flex-col space-y-3 overflow-hidden md:mx-0 md:w-full'>
      <div className='mx-4 shrink-0 space-y-3'>
        <Tabs
          value={entityType}
          onValueChange={(value) => setEntityType(value as SubscribeEntityTab)}
        >
          <TabsList className='w-full gap-2 bg-transparent p-0'>
            {ENTITY_TABS.map((tab) => {
              const Icon = tab.icon
              return (
                <TabsTrigger
                  key={tab.value}
                  value={tab.value}
                  className='group gap-1 rounded-2xl border border-border/60 bg-background/45 px-3 py-2 text-foreground/78 transition-all data-[state=active]:border-amber-500/20 data-[state=active]:bg-amber-500/10 data-[state=active]:text-amber-700 data-[state=active]:shadow-[0_10px_30px_rgba(245,158,11,0.08)] dark:data-[state=active]:text-amber-300'
                >
                  <span className='me-1 flex size-8 items-center justify-center rounded-xl border border-emerald-500/12 bg-emerald-500/7 text-emerald-700 transition-all group-data-[state=active]:border-amber-500/25 group-data-[state=active]:bg-amber-500/12 group-data-[state=active]:text-amber-700 dark:text-emerald-300 dark:group-data-[state=active]:text-amber-300'>
                    <Icon className='h-4 w-4' />
                  </span>
                  {isMobile ? tab.mobileLabel : tab.label}
                </TabsTrigger>
              )
            })}
          </TabsList>
        </Tabs>

        <Tabs
          value={activeStatusValue}
          onValueChange={(value) => {
            if (entityType === 'movie') {
              setMovieStatus(value as MovieSubscribeStatusTab)
              return
            }
            if (entityType === 'cast') {
              setCastStatus(value as CastSubscribeStatusTab)
              return
            }
            setGeneralStatus(value as GeneralSubscribeStatusTab)
          }}
        >
          <TabsList className='w-full gap-2 bg-transparent p-0'>
            {activeStatusTabs.map((tab) => (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className='rounded-xl border border-border/50 bg-background/35 px-3 py-1.5 text-foreground/72 transition-all data-[state=active]:border-amber-500/15 data-[state=active]:bg-amber-500/8 data-[state=active]:text-amber-700 dark:data-[state=active]:text-amber-300'
              >
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        <div className='relative'>
          <SearchIcon className='pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder={placeholder}
            className='pl-9'
          />
        </div>

        <p className='text-xs text-muted-foreground'>共 {total} 条订阅</p>
      </div>

      <div
        className='scrollbar-hide flex-1 overflow-auto'
        data-main-scroll-container
      >
        {entityType !== 'general' && isLoading && <Loading />}
        {entityType !== 'general' && !isLoading && !hasItems && <EmptyState />}

        {entityType === 'general' && (
          <GeneralSubscribePanel
            status={generalStatus}
            keyword={debouncedKeyword || undefined}
            onTotalChange={setGeneralTotal}
          />
        )}

        {entityType === 'movie' && (
          <div className='grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-6'>
            {movieItems.map((movie) => (
              <MovieCard
                key={`${movie.subscribe_id ?? movie.id}-${movie.id}`}
                movie={movie}
                onCreateCastSubscribe={(cast) => {
                  setEditCast(cast)
                  setEditCastDialogOpen(true)
                }}
                onEditCastSubscribe={(cast) => {
                  setEditCast(cast)
                  setEditCastDialogOpen(true)
                }}
                onImgClick={() => {
                  setPreviewImages(
                    (movie.still_photos || [])
                      .concat([movie.banner || ''])
                      .filter(Boolean)
                  )
                  setAlt(movie.number)
                  setImgPreviewOpen(true)
                }}
                onSubscribe={() => undefined}
                onEditSubscribe={(currentMovie) => {
                  setEditMovie(currentMovie)
                  setEditDialogOpen(true)
                }}
              />
            ))}
          </div>
        )}

        {entityType === 'cast' && (
          <div className='grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3'>
            {castItems.map((cast) => (
              <CastCard
                key={cast.id}
                cast={cast}
                showCreatedTime
                onEdit={(currentCast) => {
                  setEditCast(currentCast)
                  setEditCastDialogOpen(true)
                }}
              />
            ))}
          </div>
        )}

        {isMobile && entityType !== 'general' && (
          <div ref={loadMoreRef} className='py-4 text-center'>
            {activeMobileQuery.isFetchingNextPage && (
              <div className='flex items-center justify-center gap-2 text-muted-foreground'>
                <Loader2 className='h-5 w-5 animate-spin' />
                <span>加载中...</span>
              </div>
            )}
            {!activeMobileQuery.hasNextPage && hasItems && (
              <div className='text-sm text-muted-foreground'>
                已加载全部 {total} 条数据
              </div>
            )}
          </div>
        )}
      </div>

      {!isMobile && entityType !== 'general' && (
        <div className='mx-4 shrink-0'>
          <CommonPagination
            page={page}
            total={total}
            pageSize={pageSize}
            onChange={setPage}
          />
        </div>
      )}

      <ImagePreview
        images={previewImages}
        alt={alt}
        open={imgPreviewOpen}
        onClose={() => {
          setImgPreviewOpen(false)
          setAlt('')
          setPreviewImages([])
        }}
      />

      <SubscribeDialog
        open={editDialogOpen}
        onOpenChange={(openValue) => {
          setEditDialogOpen(openValue)
          if (!openValue) {
            setEditMovie(null)
          }
        }}
        mode='edit'
        subscribeId={editMovie?.subscribe_id}
        initialFilterId={editMovie?.filter_id}
        initialPriorityId={editMovie?.priority_id}
        initialPreDownloadEnabled={editMovie?.pre_download_enabled}
        movieIdList={editMovie ? [editMovie.id] : []}
      />

      <CastSubscribeDialog
        open={editCastDialogOpen}
        onOpenChange={(openValue) => {
          setEditCastDialogOpen(openValue)
          if (!openValue) {
            setEditCast(null)
          }
        }}
        cast={editCast}
      />
    </div>
  )
}
