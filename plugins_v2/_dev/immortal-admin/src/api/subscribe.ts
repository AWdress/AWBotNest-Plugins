import type { Cast } from '@/api/cast.ts'
import { type Movie } from '@/api/movie.ts'
import { request } from '@/api/request.ts'

export type SubscribeStatus = 'active' | 'paused' | 'completed' | 'canceled'

export interface SubscribeParam {
  movie_id: number
  filter_id?: number
  priority_id?: number
  pre_download_enabled?: boolean
}

export interface SubscribeUpdateParam {
  subscribe_id: number
  filter_id?: number
  priority_id?: number
  pre_download_enabled?: boolean
}

export interface CastSubscribeParam {
  cast_id: number
  max_coactors?: number
  max_page?: number
  replace_max_page?: number
  is_single?: boolean
  earliest_release_date?: string
  exclude_vr?: boolean
  filter_id?: number
  priority_id?: number
}

export interface CastSubscribeUpdateParam {
  cast_subscribe_id: number
  max_coactors?: number
  max_page?: number
  replace_max_page?: number
  is_single?: boolean
  earliest_release_date?: string
  exclude_vr?: boolean
  filter_id?: number
  priority_id?: number
}

export interface GeneralSubscribeParam {
  number_prefix?: string
  publisher?: string
  series?: string
  producer?: string
  genres?: string[]
  max_coactors?: number
  earliest_release_date?: string
  exclude_vr?: boolean
  filter_id?: number
  priority_id?: number
}

export interface GeneralSubscribeUpdateParam extends GeneralSubscribeParam {
  general_subscribe_id: number
}

export interface GeneralSubscribeItem {
  id: number
  number_prefix?: string | null
  publisher?: string | null
  series?: string | null
  producer?: string | null
  genres?: string[] | null
  max_coactors?: number | null
  earliest_release_date?: string | null
  exclude_vr: boolean
  filter_id?: number | null
  priority_id?: number | null
  status: Extract<SubscribeStatus, 'active' | 'paused' | 'canceled'>
  create_time: string
}

export interface GeneralSubscribeListResult {
  items: GeneralSubscribeItem[]
  total: number
  hasMore: boolean
  page: number
  pageSize: number
}

export interface GeneralSubscribeOptionsResult {
  publishers: string[]
  series: string[]
  producers: string[]
  genres: string[]
}

export interface FetchSubscribesPageParams {
  page: number
  pageSize: number
  keyword?: string
  status?: SubscribeStatus
  releaseDateStart?: string
  releaseDateEnd?: string
}

export interface SubscribeListResult {
  items: Movie[]
  total: number
  hasMore: boolean
  page: number
  pageSize: number
}

export interface CastSubscribeItem {
  id: number
  cast_id: number
  status: Extract<SubscribeStatus, 'active' | 'paused' | 'canceled'>
  max_coactors?: number | null
  max_page?: number | null
  replace_max_page?: number | null
  is_single: boolean
  earliest_release_date?: string | null
  exclude_vr: boolean
  filter_id?: number | null
  priority_id?: number | null
  create_time: string
  cast: Cast
}

export interface CastSubscribeListResult {
  items: Cast[]
  total: number
  hasMore: boolean
  page: number
  pageSize: number
}

export function subscribe(param: SubscribeParam) {
  return request<{ subscribe_id: number }>({
    url: '/subscribes/sub',
    method: 'post',
    data: param,
  })
}

export function cancelSub(subscribe_id: number) {
  return request({
    url: '/subscribes/cancel',
    method: 'put',
    params: { subscribe_id },
  })
}

export function pauseSubscribe(subscribe_id: number) {
  return request({
    url: '/subscribes/pause',
    method: 'put',
    params: { subscribe_id },
  })
}

export function resumeSubscribe(subscribe_id: number) {
  return request({
    url: '/subscribes/resume',
    method: 'put',
    params: { subscribe_id },
  })
}

export interface ExecuteSubscribeDownloadResult {
  subscribe_id: number
  movie_id: number
  movie_number: string
  article_id: number | null
  success: boolean
  message?: string | null
}

export function executeSubscribeDownload(subscribe_id: number) {
  return request<ExecuteSubscribeDownloadResult>({
    url: '/subscribes/execute',
    method: 'put',
    params: { subscribe_id },
  })
}

export function updateSubscribe(param: SubscribeUpdateParam) {
  return request<{ subscribe_id?: number }>({
    url: '/subscribes/update',
    method: 'put',
    data: param,
  })
}

export function fetchSubscribesPage(params: FetchSubscribesPageParams) {
  return request<SubscribeListResult>({
    url: '/subscribes/search',
    method: 'post',
    data: {
      page: params.page,
      page_size: params.pageSize,
      keyword: params.keyword,
      status: params.status,
      release_date_start: params.releaseDateStart,
      release_date_end: params.releaseDateEnd,
    },
  })
}

export function subscribeCast(param: CastSubscribeParam) {
  return request<{ cast_subscribe_id: number }>({
    url: '/subscribes/cast/sub',
    method: 'post',
    data: param,
  })
}

export function updateCastSubscribe(param: CastSubscribeUpdateParam) {
  return request({
    url: '/subscribes/cast/update',
    method: 'put',
    data: param,
  })
}

export function cancelCastSub(cast_subscribe_id: number) {
  return request({
    url: '/subscribes/cast/cancel',
    method: 'put',
    params: { cast_subscribe_id },
  })
}

export function pauseCastSubscribe(cast_subscribe_id: number) {
  return request({
    url: '/subscribes/cast/pause',
    method: 'put',
    params: { cast_subscribe_id },
  })
}

export function resumeCastSubscribe(cast_subscribe_id: number) {
  return request({
    url: '/subscribes/cast/resume',
    method: 'put',
    params: { cast_subscribe_id },
  })
}

export function fetchCastSubscribesPage(params: FetchSubscribesPageParams) {
  return request<CastSubscribeListResult>({
    url: '/subscribes/cast/search',
    method: 'post',
    data: {
      page: params.page,
      page_size: params.pageSize,
      keyword: params.keyword,
      status: params.status,
    },
  })
}

export function subscribeGeneral(param: GeneralSubscribeParam) {
  return request<{ general_subscribe_id: number }>({
    url: '/subscribes/general/sub',
    method: 'post',
    data: param,
  })
}

export function updateGeneralSubscribe(param: GeneralSubscribeUpdateParam) {
  return request({
    url: '/subscribes/general/update',
    method: 'put',
    data: param,
  })
}

export function cancelGeneralSubscribe(general_subscribe_id: number) {
  return request({
    url: '/subscribes/general/cancel',
    method: 'put',
    params: { general_subscribe_id },
  })
}

export function pauseGeneralSubscribe(general_subscribe_id: number) {
  return request({
    url: '/subscribes/general/pause',
    method: 'put',
    params: { general_subscribe_id },
  })
}

export function resumeGeneralSubscribe(general_subscribe_id: number) {
  return request({
    url: '/subscribes/general/resume',
    method: 'put',
    params: { general_subscribe_id },
  })
}

export function fetchGeneralSubscribesPage(params: FetchSubscribesPageParams) {
  return request<GeneralSubscribeListResult>({
    url: '/subscribes/general/search',
    method: 'post',
    data: {
      page: params.page,
      page_size: params.pageSize,
      keyword: params.keyword,
      status: params.status,
    },
  })
}

export function fetchGeneralSubscribeOptions(params?: {
  publisher?: string
  series?: string
  producer?: string
  genres?: string[]
}) {
  return request<GeneralSubscribeOptionsResult>({
    url: '/subscribes/general/options',
    method: 'get',
    params: {
      publisher: params?.publisher,
      series: params?.series,
      producer: params?.producer,
      genres: params?.genres,
    },
  })
}
