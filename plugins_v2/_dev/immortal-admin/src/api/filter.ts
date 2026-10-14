import { request } from '@/api/request.ts'

export interface Filter {
  id?: number
  filter_name: string
  keyword?: string
  regex?: string
  resolutions?: string[]
  subtitles?: string[]
  mosaic?: string[]
  min_size?: number
  max_size?: number
  skip_in_library_check: boolean
  enable_pre_download: boolean
  is_default: boolean
}

export function listFilter() {
  return request<Filter[]>({ url: '/filters/', method: 'get' })
}

export function addFilter(filter: Filter) {
  return request({ url: '/filters/', method: 'post', data: filter })
}

export function updateFilter(filter: Filter) {
  return request({ url: '/filters/', method: 'put', data: filter })
}

export function deleteFilter(filter_id: number) {
  return request({ url: `/filters/${filter_id}`, method: 'delete' })
}
