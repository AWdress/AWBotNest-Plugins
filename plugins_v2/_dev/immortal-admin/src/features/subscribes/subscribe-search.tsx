import { useEffect, useMemo, useRef, useState, type ComponentType } from 'react'
import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { Route } from '@/routes/_authenticated/subscribes/search.tsx'
import { Film, Loader2, SearchIcon, Users } from 'lucide-react'
import { toast } from 'sonner'
import {
  networkSearchCasts,
  searchCasts,
  type Cast,
  type CastSearchResult,
} from '@/api/cast.ts'
import { networkSearchMovies, type Movie, searchMovies } from '@/api/movie.ts'
import { useDebounce } from '@/hooks/use-debounce.tsx'
import { useIsMobile } from '@/hooks/use-mobile.tsx'
import { Button } from '@/components/ui/button.tsx'
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

type SearchEntityTab = 'movie' | 'cast'

const ENTITY_TABS: Array<{
  value: SearchEntityTab
  label: string
  icon: ComponentType<{ className?: string }>
}> = [
  { value: 'movie', label: '影片库搜索', icon: Film },
  { value: 'cast', label: '演员库搜索', icon: Users },
]

export function SubscribeSearch() {
  const isMobile = useIsMobile()
  const queryClient = useQueryClient()
  const routeSearch = Route.useSearch()
  const [entityType, setEntityType] = useState<SearchEntityTab>(
    routeSearch.entity || 'movie'
  )
  const [moviePage, setMoviePage] = useState(1)
  const [castPage, setCastPage] = useState(1)
  const [keyword, setKeyword] = useState(routeSearch.keyword || '')
  const debouncedKeyword = useDebounce(keyword, 300)

  const [previewImages, setPreviewImages] = useState<string[]>([])
  const [imgPreviewOpen, setImgPreviewOpen] = useState(false)
  const [alt, setAlt] = useState('')
  const [subscribeDialogOpen, setSubscribeDialogOpen] = useState(false)
  const [movieIdList, setMovieIdList] = useState<number[]>([])
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editMovie, setEditMovie] = useState<Movie | null>(null)

  const [selectedCast, setSelectedCast] = useState<Cast | null>(null)
  const [castDialogOpen, setCastDialogOpen] = useState(false)

  const loadMoreRef = useRef<HTMLDivElement>(null)
  const lastRouteSearchRef = useRef({
    entity: routeSearch.entity,
    keyword: routeSearch.keyword,
  })

  useEffect(() => {
    const entityChanged =
      lastRouteSearchRef.current.entity !== routeSearch.entity
    const keywordChanged =
      lastRouteSearchRef.current.keyword !== routeSearch.keyword

    if (!entityChanged && !keywordChanged) {
      return
    }

    lastRouteSearchRef.current = {
      entity: routeSearch.entity,
      keyword: routeSearch.keyword,
    }

    if (routeSearch.entity) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setEntityType(routeSearch.entity)
    }

    setKeyword(routeSearch.keyword || '')
  }, [routeSearch.entity, routeSearch.keyword])

  useEffect(() => {
    if (entityType === 'movie') {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMoviePage(1)
    } else {
      setCastPage(1)
    }
  }, [entityType, debouncedKeyword])

  const desktopMovieQuery = useQuery({
    queryKey: ['movie-search', 'desktop', debouncedKeyword, moviePage],
    queryFn: async () => {
      const res = await searchMovies({
        page: moviePage,
        pageSize: 20,
        keyword: debouncedKeyword || undefined,
      })
      return res.data
    },
    enabled: !isMobile && entityType === 'movie',
    staleTime: 60 * 1000,
  })

  const desktopCastQuery = useQuery<CastSearchResult>({
    queryKey: ['cast-search', 'desktop', debouncedKeyword, castPage],
    queryFn: async () => {
      const res = await searchCasts({
        page: castPage,
        pageSize: 20,
        keyword: debouncedKeyword || undefined,
      })
      return res.data
    },
    enabled: !isMobile && entityType === 'cast',
    staleTime: 60 * 1000,
  })

  const mobileMovieQuery = useInfiniteQuery({
    queryKey: ['movie-search', 'mobile', debouncedKeyword],
    queryFn: async ({ pageParam = 1 }) => {
      const res = await searchMovies({
        page: pageParam,
        pageSize: 12,
        keyword: debouncedKeyword || undefined,
      })
      return res.data
    },
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? lastPage.page + 1 : undefined,
    initialPageParam: 1,
    enabled: isMobile && entityType === 'movie',
    staleTime: 60 * 1000,
  })

  const mobileCastQuery = useInfiniteQuery<
    CastSearchResult,
    Error,
    InfiniteData<CastSearchResult>,
    readonly unknown[],
    number
  >({
    queryKey: ['cast-search', 'mobile', debouncedKeyword],
    queryFn: async ({ pageParam }) => {
      const res = await searchCasts({
        page: pageParam,
        pageSize: 12,
        keyword: debouncedKeyword || undefined,
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

  const isMovieNumberKeyword = (keyword: string) => {
    const normalized = (keyword || '').trim().toUpperCase()
    return /^(?:[A-Z]{2,10}-?\d{2,6}|FC2-?PPV-?\d{5,8}|FC-?\d{2,6})$/.test(
      normalized
    )
  }

  const networkSearchMutation = useMutation({
    mutationFn: async (variables: {
      entityType: SearchEntityTab
      keyword: string
    }) => {
      if (!variables.keyword) {
        throw new Error('缺少搜索关键字')
      }

      if (variables.entityType === 'movie') {
        return networkSearchMovies(variables.keyword)
      }
      if (isMovieNumberKeyword(variables.keyword)) {
        return networkSearchMovies(variables.keyword)
      }
      return networkSearchCasts(variables.keyword)
    },
    onSuccess: async (res, variables) => {
      const result = res.data
      if (result?.found) {
        const sourceLabel =
          result.source === 'local'
            ? '本地库'
            : result.source === 'javdb'
              ? 'JavDB'
              : 'AvBase'
        const usedKeyword =
          variables.entityType === 'cast' &&
          'usedKeyword' in result &&
          typeof result.usedKeyword === 'string'
            ? result.usedKeyword.trim()
            : ''
        if (usedKeyword && usedKeyword !== variables.keyword) {
          setKeyword(usedKeyword)
          toast.success(
            result.source === 'local'
              ? `已在${sourceLabel}命中结果，并切换为“${usedKeyword}”继续查询`
              : `已从${sourceLabel}同步 ${result.savedCount} 条数据，并切换为“${usedKeyword}”继续查询`
          )
        } else {
          toast.success(
            result.source === 'local'
              ? `已在${sourceLabel}命中结果`
              : `已从${sourceLabel}同步 ${result.savedCount} 条数据`
          )
        }
      } else {
        toast.error('网络资源库未找到相关内容')
      }

      const queryKey =
        variables.entityType === 'movie' ? ['movie-search'] : ['cast-search']
      await queryClient.invalidateQueries({ queryKey, exact: false })
    },
    onError: (error: Error) => {
      toast.error(error.message || '网络搜索失败')
    },
  })

  useEffect(() => {
    if (!isMobile || !loadMoreRef.current) return
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
  }, [activeMobileQuery, isMobile])

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
    isMobile,
    mobileCastQuery.data?.pages,
    mobileMovieQuery.data?.pages,
  ])

  const pageSize =
    entityType === 'movie'
      ? desktopMovieQuery.data?.pageSize || 20
      : desktopCastQuery.data?.pageSize || 20

  const isLoading =
    entityType === 'movie'
      ? isMobile
        ? mobileMovieQuery.isLoading
        : desktopMovieQuery.isLoading
      : isMobile
        ? mobileCastQuery.isLoading
        : desktopCastQuery.isLoading

  const placeholder =
    entityType === 'movie' ? '搜索番号、标题、描述、演员' : '搜索演员、番号'
  const hasItems =
    entityType === 'movie' ? movieItems.length > 0 : castItems.length > 0
  const normalizedKeyword = debouncedKeyword.trim()
  const shouldShowNetworkSearch =
    Boolean(normalizedKeyword) && !isLoading && !hasItems

  const handleMovieDialogClose = (openValue: boolean) => {
    setSubscribeDialogOpen(openValue)
    if (!openValue) {
      queryClient.invalidateQueries({
        queryKey: ['movie-search'],
        exact: false,
      })
      setMovieIdList([])
    }
  }

  const handleMovieEditClose = (openValue: boolean) => {
    setEditDialogOpen(openValue)
    if (!openValue) {
      queryClient.invalidateQueries({
        queryKey: ['movie-search'],
        exact: false,
      })
      setEditMovie(null)
    }
  }

  const handleCastDialogClose = (openValue: boolean) => {
    setCastDialogOpen(openValue)
    if (!openValue) {
      queryClient.invalidateQueries({ queryKey: ['cast-search'], exact: false })
      setSelectedCast(null)
    }
  }

  return (
    <div className='-mx-4 flex flex-col space-y-3 overflow-hidden md:mx-0 md:w-full'>
      <div className='mx-4 shrink-0 space-y-3'>
        <Tabs
          value={entityType}
          onValueChange={(value) => setEntityType(value as SearchEntityTab)}
        >
          <TabsList className='w-full gap-2 bg-transparent p-0'>
            {ENTITY_TABS.map((tab) => {
              const Icon = tab.icon
              return (
                <TabsTrigger
                  key={tab.value}
                  value={tab.value}
                  className='group gap-2 rounded-2xl border border-border/60 bg-background/45 px-3 py-2 text-foreground/78 transition-all data-[state=active]:border-amber-500/20 data-[state=active]:bg-amber-500/10 data-[state=active]:text-amber-700 data-[state=active]:shadow-[0_10px_30px_rgba(245,158,11,0.08)] dark:data-[state=active]:text-amber-300'
                >
                  <span className='me-1 flex size-8 items-center justify-center rounded-xl border border-emerald-500/12 bg-emerald-500/7 text-emerald-700 transition-all group-data-[state=active]:border-amber-500/25 group-data-[state=active]:bg-amber-500/12 group-data-[state=active]:text-amber-700 dark:text-emerald-300 dark:group-data-[state=active]:text-amber-300'>
                    <Icon className='h-4 w-4' />
                  </span>
                  {tab.label}
                </TabsTrigger>
              )
            })}
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

        <div className='space-y-2'>
          <p className='text-xs text-muted-foreground'>共 {total} 条数据</p>
          {shouldShowNetworkSearch && (
            <div className='flex flex-col gap-2 rounded-lg border border-dashed border-border/80 bg-muted/30 px-3 py-2 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between'>
              <span>
                想找的内容没有出现？点击后到网络资源库搜索，并在入库后重新查询本地结果。
              </span>
              <Button
                type='button'
                variant='outline'
                size='sm'
                className='h-8 shrink-0'
                disabled={networkSearchMutation.isPending}
                onClick={() =>
                  networkSearchMutation.mutate({
                    entityType,
                    keyword: normalizedKeyword,
                  })
                }
              >
                {networkSearchMutation.isPending ? (
                  <>
                    <Loader2 className='mr-2 h-4 w-4 animate-spin' />
                    搜索中
                  </>
                ) : (
                  '网络搜索'
                )}
              </Button>
            </div>
          )}
        </div>
      </div>

      <div
        className='scrollbar-hide flex-1 overflow-auto'
        data-main-scroll-container
      >
        {isLoading && <Loading />}
        {!isLoading && !hasItems && <EmptyState />}

        {entityType === 'movie' && (
          <div className='columns-1 gap-4 lg:columns-2 xl:columns-4 2xl:columns-6'>
            {movieItems.map((movie) => (
              <div key={movie.id} className='mb-4 break-inside-avoid'>
                <MovieCard
                  movie={movie}
                  onCreateCastSubscribe={(cast) => {
                    setSelectedCast(cast)
                    setCastDialogOpen(true)
                  }}
                  onEditCastSubscribe={(cast) => {
                    setSelectedCast(cast)
                    setCastDialogOpen(true)
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
                  onSubscribe={() => {
                    setSubscribeDialogOpen(true)
                    setMovieIdList([movie.id])
                  }}
                  onEditSubscribe={(currentMovie) => {
                    setEditMovie(currentMovie)
                    setEditDialogOpen(true)
                  }}
                />
              </div>
            ))}
          </div>
        )}

        {entityType === 'cast' && (
          <div className='grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3'>
            {castItems.map((cast) => {
              return (
                <CastCard
                  key={cast.id}
                  cast={cast}
                  onCreate={(currentCast) => {
                    setSelectedCast(currentCast)
                    setCastDialogOpen(true)
                  }}
                  onEdit={(currentCast) => {
                    setSelectedCast(currentCast)
                    setCastDialogOpen(true)
                  }}
                />
              )
            })}
          </div>
        )}

        {isMobile && (
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

      {!isMobile && (
        <div className='mx-4 shrink-0'>
          <CommonPagination
            page={entityType === 'movie' ? moviePage : castPage}
            total={total}
            pageSize={pageSize}
            onChange={entityType === 'movie' ? setMoviePage : setCastPage}
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
        open={subscribeDialogOpen}
        onOpenChange={handleMovieDialogClose}
        movieIdList={movieIdList}
      />

      <SubscribeDialog
        open={editDialogOpen}
        onOpenChange={handleMovieEditClose}
        mode='edit'
        subscribeId={editMovie?.subscribe_id}
        initialFilterId={editMovie?.filter_id ?? null}
        initialPriorityId={editMovie?.priority_id ?? null}
        initialPreDownloadEnabled={editMovie?.pre_download_enabled}
        movieIdList={editMovie ? [editMovie.id] : []}
      />

      <CastSubscribeDialog
        cast={selectedCast}
        open={castDialogOpen}
        onOpenChange={handleCastDialogClose}
      />
    </div>
  )
}
