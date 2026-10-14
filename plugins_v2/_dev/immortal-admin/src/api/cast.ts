import { request } from '@/api/request.ts'

export interface CastSubscribeSummary {
  id: number
  cast_id: number
  status: 'active' | 'paused' | 'canceled'
  max_coactors?: number | null
  max_page?: number | null
  replace_max_page?: number | null
  is_single: boolean
  earliest_release_date?: string | null
  exclude_vr: boolean
  filter_id?: number | null
  priority_id?: number | null
  create_time: string
}

export interface Cast {
  id: number
  name: string
  avatar: string
  cn_name?: string
  former_name: string[]
  photo: string
  subscribe?: CastSubscribeSummary | null
}

export interface CastSearchParams {
  page: number
  pageSize: number
  keyword?: string
}

export interface CastSearchResult {
  items: Cast[]
  total: number
  hasMore: boolean
  page: number
  pageSize: number
}

export function searchCasts(params: CastSearchParams) {
  return request<CastSearchResult>({
    url: '/casts/search',
    method: 'post',
    data: {
      page: params.page,
      page_size: params.pageSize,
      keyword: params.keyword,
    },
  })
}

export interface CastNetworkSearchResult {
  keyword: string
  usedKeyword?: string
  attemptedKeywords?: string[]
  found: boolean
  savedCount: number
  source?: 'local' | 'avbase' | null
}

export function networkSearchCasts(keyword: string) {
  return request<CastNetworkSearchResult>({
    url: '/casts/network-search',
    method: 'post',
    data: {
      keyword,
    },
  })
}
