import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import type { Cast } from '@/api/cast.ts'
import { recommendMoviesFromSubscribes, type Movie } from '@/api/movie.ts'
import { ImagePreview } from '@/components/image-preview.tsx'
import { Loading } from '@/components/loading.tsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { CastSubscribeDialog } from '@/features/rank/cast/subscribe-dialog.tsx'
import { MovieCard } from '@/features/rank/movie/movie-card.tsx'
import { SubscribeDialog } from '@/features/rank/movie/subscribe-dialog.tsx'

const DASHBOARD_RECOMMEND_PAGE_SIZE = 12

export function SubscriptionRecommendations() {
  const [previewImages, setPreviewImages] = useState<string[]>([])
  const [imgPreviewOpen, setImgPreviewOpen] = useState(false)
  const [alt, setAlt] = useState('')
  const [subscribeDialogOpen, setSubscribeDialogOpen] = useState(false)
  const [selectedMovie, setSelectedMovie] = useState<Movie | null>(null)
  const [castDialogOpen, setCastDialogOpen] = useState(false)
  const [selectedCast, setSelectedCast] = useState<Cast | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', 'subscription-recommendations'],
    queryFn: async () => {
      const res = await recommendMoviesFromSubscribes({
        page: 1,
        pageSize: DASHBOARD_RECOMMEND_PAGE_SIZE,
      })
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const items = useMemo(
    () => (data?.items || []).filter((movie) => movie.in_library !== true),
    [data?.items]
  )

  return (
    <>
      <Card className='overflow-hidden border-amber-500/20 bg-linear-to-br from-amber-500/8 via-background to-background'>
        <CardHeader className='space-y-2'>
          <div className='flex items-center gap-3'>
            <div className='rounded-xl bg-amber-500/12 p-2.5 text-amber-500'>
              <Sparkles className='h-5 w-5' />
            </div>
            <div className='min-w-0'>
              <CardTitle>订阅推荐</CardTitle>
            </div>
            <div className='ml-auto rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 text-sm font-medium text-amber-500'>
              {items.length} 部
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && <Loading />}

          {!isLoading && items.length === 0 && (
            <div className='rounded-2xl border border-dashed border-border/80 bg-background/60 px-4 py-8 text-center text-sm text-muted-foreground'>
              暂时没有可推荐的影片，先多订阅几部再来看看。
            </div>
          )}

          {!isLoading && items.length > 0 && (
            <div className='grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-4'>
              {items.map((movie) => (
                <MovieCard
                  key={movie.id}
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
                    setSelectedMovie(movie)
                    setSubscribeDialogOpen(true)
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
        open={subscribeDialogOpen}
        onOpenChange={(openValue) => {
          setSubscribeDialogOpen(openValue)
          if (!openValue) {
            setSelectedMovie(null)
          }
        }}
        movieIdList={selectedMovie ? [selectedMovie.id] : []}
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
