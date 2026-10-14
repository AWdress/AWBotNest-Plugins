import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CalendarRange } from 'lucide-react'
import type { Cast } from '@/api/cast.ts'
import { type Movie } from '@/api/movie.ts'
import { fetchSubscribesPage } from '@/api/subscribe.ts'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card.tsx'
import { ImagePreview } from '@/components/image-preview.tsx'
import { Loading } from '@/components/loading.tsx'
import { CastSubscribeDialog } from '@/features/rank/cast/subscribe-dialog.tsx'
import { MovieCard } from '@/features/rank/movie/movie-card.tsx'
import { SubscribeDialog } from '@/features/rank/movie/subscribe-dialog.tsx'

const DASHBOARD_SUBSCRIBE_PAGE_SIZE = 200
const RECENT_RELEASE_DAY_RANGE = 7

function formatDate(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function buildRecentReleaseRange() {
  const start = new Date()
  const end = new Date(start)
  end.setDate(end.getDate() + RECENT_RELEASE_DAY_RANGE - 1)
  return {
    start: formatDate(start),
    end: formatDate(end),
  }
}

function normalizeReleaseDate(value?: string) {
  if (!value) return ''
  return value.slice(0, 10)
}

export function RecentReleaseSubscribes() {
  const recentRange = buildRecentReleaseRange()
  const [previewImages, setPreviewImages] = useState<string[]>([])
  const [imgPreviewOpen, setImgPreviewOpen] = useState(false)
  const [alt, setAlt] = useState('')
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editMovie, setEditMovie] = useState<Movie | null>(null)
  const [castDialogOpen, setCastDialogOpen] = useState(false)
  const [selectedCast, setSelectedCast] = useState<Cast | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: [
      'dashboard',
      'recent-release-subscribes',
      recentRange.start,
      recentRange.end,
    ],
    queryFn: async () => {
      const [activeRes, pausedRes] = await Promise.all([
        fetchSubscribesPage({
          page: 1,
          pageSize: DASHBOARD_SUBSCRIBE_PAGE_SIZE,
          status: 'active',
          releaseDateStart: recentRange.start,
          releaseDateEnd: recentRange.end,
        }),
        fetchSubscribesPage({
          page: 1,
          pageSize: DASHBOARD_SUBSCRIBE_PAGE_SIZE,
          status: 'paused',
          releaseDateStart: recentRange.start,
          releaseDateEnd: recentRange.end,
        }),
      ])
      return [
        ...(activeRes.data?.items ?? []),
        ...(pausedRes.data?.items ?? []),
      ]
    },
    staleTime: 60 * 1000,
  })

  const items = useMemo(() => {
    const activeStatusRank = { active: 0, paused: 1 } as const
    return (data ?? [])
      .filter((movie) => movie.in_library !== true)
      .filter((movie) => movie.status === 'active' || movie.status === 'paused')
      .sort((left, right) => {
        const releaseCompare = normalizeReleaseDate(
          left.release_date
        ).localeCompare(normalizeReleaseDate(right.release_date))
        if (releaseCompare !== 0) return releaseCompare

        const leftRank =
          activeStatusRank[left.status as 'active' | 'paused'] ?? 99
        const rightRank =
          activeStatusRank[right.status as 'active' | 'paused'] ?? 99
        if (leftRank !== rightRank) return leftRank - rightRank

        return (right.subscribe_time || '').localeCompare(
          left.subscribe_time || ''
        )
      })
  }, [data])

  return (
    <>
      <Card className='overflow-hidden border-primary/15 bg-linear-to-br from-primary/5 via-background to-background'>
        <CardHeader className='space-y-2'>
          <div className='flex items-center gap-3'>
            <div className='rounded-xl bg-primary/12 p-2.5 text-primary'>
              <CalendarRange className='h-5 w-5' />
            </div>
            <div className='min-w-0'>
              <CardTitle>近日发售待入库</CardTitle>
            </div>
            <div className='ml-auto rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-sm font-medium text-primary'>
              {items.length} 部
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && <Loading />}

          {!isLoading && items.length === 0 && (
            <div className='rounded-2xl border border-dashed border-border/80 bg-background/60 px-4 py-8 text-center text-sm text-muted-foreground'>
              近期没有待入库的已订阅发售影片。
            </div>
          )}

          {!isLoading && items.length > 0 && (
            <div className='grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-4'>
              {items.map((movie) => (
                <MovieCard
                  key={`${movie.subscribe_id ?? movie.id}-${movie.id}`}
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
                  onSubscribe={() => undefined}
                  onEditSubscribe={(currentMovie) => {
                    setEditMovie(currentMovie)
                    setEditDialogOpen(true)
                  }}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

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
        open={castDialogOpen}
        onOpenChange={(openValue) => {
          setCastDialogOpen(openValue)
          if (!openValue) {
            setSelectedCast(null)
          }
        }}
        cast={selectedCast}
      />
    </>
  )
}
