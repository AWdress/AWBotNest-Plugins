import { request } from '@/api/request.ts'
import { type Cast } from '@/api/cast.ts'
import { type Movie } from '@/api/movie.ts'
import type { LibraryFilterValue } from '@/features/rank/movie/rank-filter.tsx'

export interface RankMovieInfo {
  sync_time: string
  movies?: Movie[]
  page: number
  pageSize: number
  total: number
  totalPages: number
}

export interface RankCastInfo {
  sync_time: string
  casts?: Cast[]
}

export function fetchRankMovie(rankName: string, page = 1, libraryFilter: LibraryFilterValue = 'all') {
  return request<RankMovieInfo>({
    url: '/rank/movie',
    method: 'get',
    params: {
      rank_name: rankName,
      page,
      library_filter: libraryFilter,
    },
  })
}

export function fetchRankCast(rankName: string) {
  return request<RankCastInfo>({
    url: '/rank/cast',
    method: 'get',
    params: { rank_name: rankName },
  })
}
