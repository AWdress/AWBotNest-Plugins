import { request } from '@/api/request.ts'
import { type Cast } from '@/api/cast.ts'

export type SubscribeStatus =
  | 'active'
  | 'paused'
  | 'completed'
  | 'released'
  | 'canceled'

export interface Movie {
  id: number
  number: string
  title?: string
  cn_title?: string
  description?: string
  cn_description?: string
  release_date?: string
  duration?: number
  poster?: string
  banner?: string
  still_photos?: string[]
  genres?: string[]
  series?: string
  producer?: string
  publisher?: string
  casts?: Cast[]
  status: SubscribeStatus
  subscribe_id?: number
  subscribe_time?: string
  filter_id?: number | null
  priority_id?: number | null
  pre_download_enabled?: boolean
  in_library?: boolean
}

export interface MovieSearchParams {
  page: number
  pageSize: number
  keyword?: string
}

export interface MovieSearchResult {
  items: Movie[]
  total: number
  hasMore: boolean
  page: number
  pageSize: number
}

export interface MovieRecommendParams {
  page: number
  pageSize: number
}

export interface MovieFrequencyStatItem {
  id?: number
  name: string
  count: number
  avatar?: string
  subscribe?: import('@/api/cast.ts').CastSubscribeSummary | null
}

export interface MovieFrequencyStats {
  actors: MovieFrequencyStatItem[]
  producers: MovieFrequencyStatItem[]
  series: MovieFrequencyStatItem[]
}

export function searchMovies(params: MovieSearchParams) {
  return request<MovieSearchResult>({
    url: '/movies/search',
    method: 'post',
    data: {
      page: params.page,
      page_size: params.pageSize,
      keyword: params.keyword,
    },
  })
}

export interface MovieNetworkSearchResult {
  keyword: string
  found: boolean
  savedCount: number
  source?: 'avbase' | 'javdb' | null
}

export function networkSearchMovies(keyword: string) {
  return request<MovieNetworkSearchResult>({
    url: '/movies/network-search',
    method: 'post',
    data: {
      keyword,
    },
  })
}

export function recommendMoviesFromSubscribes(params: MovieRecommendParams) {
  return request<MovieSearchResult>({
    url: '/movies/recommend/subscribed',
    method: 'post',
    data: {
      page: params.page,
      page_size: params.pageSize,
    },
  })
}

export function getMovieFrequencyStats() {
  return request<MovieFrequencyStats>({
    url: '/movies/stats/frequency',
    method: 'get',
  })
}
