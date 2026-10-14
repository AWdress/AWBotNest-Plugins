import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type Cast } from '@/api/cast.ts'
import { fetchRankCast } from '@/api/rank.ts'
import { EmptyState } from '@/components/empty.tsx'
import { Loading } from '@/components/loading.tsx'
import { CastSubscribeDialog } from '@/features/rank/cast/subscribe-dialog.tsx'
import { CastCard } from '@/features/subscribes/cast-subscribe-card.tsx'

const RANK_NAME = 'library-star_mostfav'

export function RankList() {
  const [selectedCast, setSelectedCast] = useState<Cast | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['rank-cast', RANK_NAME],
    queryFn: async () => {
      const res = await fetchRankCast(RANK_NAME)
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  return (
    <>
      {isLoading && <Loading />}
      {!isLoading && (data?.casts?.length ?? 0) === 0 && <EmptyState />}

      <div className='grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3'>
        {data?.casts?.map((cast, index) => {
          return (
            <CastCard
              key={cast.id}
              cast={cast}
              rank={index + 1}
              onCreate={(currentCast) => {
                setSelectedCast(currentCast)
                setDialogOpen(true)
              }}
              onEdit={(currentCast) => {
                setSelectedCast(currentCast)
                setDialogOpen(true)
              }}
            />
          )
        })}
      </div>

      <CastSubscribeDialog
        cast={selectedCast}
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open)
          if (!open) {
            setSelectedCast(null)
          }
        }}
      />
    </>
  )
}
