import { request } from '@/api/request.ts'

export interface Priority {
  id?: number
  priority_name: string
  resolutions: string[]
  subtitles: string[]
  mosaic: string[]
  priority_sort: string[]
  is_default: boolean
}

export function listPriority() {
  return request<Priority[]>({ url: '/priorities/', method: 'get' })
}

export function addPriority(priority: Priority) {
  return request({ url: '/priorities/', method: 'post', data: priority })
}

export function updatePriority(priority: Priority) {
  return request({ url: '/priorities/', method: 'put', data: priority })
}

export function deletePriority(priority_id: number) {
  return request({ url: `/priorities/${priority_id}`, method: 'delete' })
}
