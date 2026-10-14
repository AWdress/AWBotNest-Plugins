import { useEffect, useMemo, useRef, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import type { Cast } from '@/api/cast.ts'
import { type Movie } from '@/api/movie.ts'
import { fetchRankMovie } from '@/api/rank.ts'
import { useIsMobile } from '@/hooks/use-mobile.tsx'
import { EmptyState } from '@/components/empty.tsx'
import { ImagePreview } from '@/components/image-preview.tsx'
import { Loading } from '@/components/loading.tsx'
import { CommonPagination } from '@/components/pagination.tsx'
import { CastSubscribeDialog } from '@/features/rank/cast/subscribe-dialog.tsx'
import { MovieCard } from '@/features/rank/movie/movie-card.tsx'
import {
  RankFilter,
  type FilterValue,
  type LibraryFilterValue,
} from '@/features/rank/movie/rank-filter.tsx'
import { SubscribeDialog } from '@/features/rank/movie/subscribe-dialog.tsx'

export function RankList({
  defaultSiteId = 'library',
}: {
  defaultSiteId?: string
}) {
  const isMobile = useIsMobile()
  const loadMoreRef = useRef<HTMLDivElement>(null)
  const [previewImages, setPreviewImages] = useState<string[]>([])
  const [imgPreviewOpen, setImgPreviewOpen] = useState(false)
  const [alt, setAlt] = useState('')
  const [rankName, setRankName] = useState(`${defaultSiteId}-vl_mostwanted`)
  const [libraryFilter, setLibraryFilter] = useState<LibraryFilterValue>('all')
  const [page, setPage] = useState(1)

  const [isSubscribeDialogOpen, setIsSubscribeDialogOpen] = useState(false)
  const [movieIdList, setMovieIdList] = useState<number[]>([])
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editMovie, setEditMovie] = useState<Movie | null>(null)
  const [castDialogOpen, setCastDialogOpen] = useState(false)
  const [selectedCast, setSelectedCast] = useState<Cast | null>(null)

  const desktopQuery = useQuery({
    queryKey: ['rank-movie', 'desktop', rankName, libraryFilter, page],
    queryFn: async () => {
      const res = await fetchRankMovie(rankName, page, libraryFilter)
      return res.data
    },
    enabled: !isMobile,
    staleTime: 5 * 60 * 1000,
  })

  const mobileQuery = useInfiniteQuery({
    queryKey: ['rank-movie', 'mobile', rankName, libraryFilter],
    queryFn: async ({ pageParam = 1 }) => {
      const res = await fetchRankMovie(rankName, pageParam, libraryFilter)
      return res.data
    },
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.totalPages ? lastPage.page + 1 : undefined,
    initialPageParam: 1,
    enabled: isMobile,
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (!desktopQuery.data?.totalPages) {
      return
    }
    if (page > desktopQuery.data.totalPages) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPage(desktopQuery.data.totalPages)
    }
  }, [desktopQuery.data?.totalPages, page])

  useEffect(() => {
    if (!isMobile || !loadMoreRef.current) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (
          entry.isIntersecting &&
          mobileQuery.hasNextPage &&
          !mobileQuery.isFetchingNextPage
        ) {
          mobileQuery.fetchNextPage()
        }
      },
      { root: null, rootMargin: '120px' }
    )
    observer.observe(loadMoreRef.current)
    return () => observer.disconnect()
    // eslint-disable-next-line @tanstack/query/no-unstable-deps
  }, [isMobile, mobileQuery])

  const mobileMovies = useMemo(
    () =>
      mobileQuery.data?.pages.flatMap((pageData) => pageData.movies ?? []) ??
      [],
    [mobileQuery.data?.pages]
  )

  const desktopMovies = desktopQuery.data?.movies ?? []
  const movies = isMobile ? mobileMovies : desktopMovies
  const isLoading = isMobile ? mobileQuery.isLoading : desktopQuery.isLoading
  const total = isMobile
    ? (mobileQuery.data?.pages[0]?.total ?? 0)
    : (desktopQuery.data?.total ?? 0)
  const pageSize = isMobile
    ? (mobileQuery.data?.pages[0]?.pageSize ?? 25)
    : (desktopQuery.data?.pageSize ?? 25)

  const handleFilter = (value: FilterValue) => {
    setRankName(value.key)
    setLibraryFilter(value.libraryFilter)
    setPage(1)
  }

  return (
    <>
      {isLoading && <Loading />}
      {!isLoading && movies.length === 0 && <EmptyState />}
      <div className='grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-6'>
        {movies.map((movie, index) => (
          <MovieCard
            key={`${movie.subscribe_id ?? movie.id}-${movie.id}`}
            movie={movie}
            index={index}
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
              setIsSubscribeDialogOpen(true)
              setMovieIdList([movie.id])
            }}
            onEditSubscribe={(currentMovie) => {
              setEditMovie(currentMovie)
              setEditDialogOpen(true)
            }}
          />
        ))}
      </div>

      {isMobile ? (
        <div ref={loadMoreRef} className='py-4 text-center'>
          {mobileQuery.isFetchingNextPage && (
            <div className='flex items-center justify-center gap-2 text-muted-foreground'>
              <Loader2 className='h-5 w-5 animate-spin' />
              <span>加载中...</span>
            </div>
          )}
          {!mobileQuery.hasNextPage && movies.length > 0 && (
            <div className='text-sm text-muted-foreground'>
              已加载全部 {total} 条数据
            </div>
          )}
        </div>
      ) : (
        <div className='mt-4 flex justify-center'>
          <CommonPagination
            page={desktopQuery.data?.page || page}
            total={total}
            pageSize={pageSize}
            onChange={setPage}
          />
        </div>
      )}

      <RankFilter
        isMobile={true}
        defaultSiteId={defaultSiteId}
        showSiteTabs={false}
        onApply={handleFilter}
      />

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
        open={isSubscribeDialogOpen}
        onOpenChange={(value) => setIsSubscribeDialogOpen(value)}
        movieIdList={movieIdList}
      />

      <SubscribeDialog
        open={editDialogOpen}
        onOpenChange={(value) => {
          setEditDialogOpen(value)
          if (!value) {
            setEditMovie(null)
          }
        }}
        mode='edit'
        subscribeId={editMovie?.subscribe_id}
        initialFilterId={editMovie?.filter_id ?? null}
        initialPriorityId={editMovie?.priority_id ?? null}
        initialPreDownloadEnabled={editMovie?.pre_download_enabled}
        movieIdList={editMovie ? [editMovie.id] : []}
      />

      <CastSubscribeDialog
        open={castDialogOpen}
        onOpenChange={(value) => {
          setCastDialogOpen(value)
          if (!value) {
            setSelectedCast(null)
          }
        }}
        cast={selectedCast}
      />
    </>
  )
}
