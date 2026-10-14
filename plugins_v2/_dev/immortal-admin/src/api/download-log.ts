import { request } from '@/api/request.ts'

export interface DownloadLogFilter {
  page: number
  page_size: number
  downloader: string
  save_path: string
}

export interface DownloadLog {
  id: number
  article_id: number
  section: string
  category: string
  title: string
  size: number
  img_list: string[]
  downloader: string
  save_path: string
  download_time: string
}

export interface DownloadLogResult {
  total: number
  items: DownloadLog[]
}

export interface SectionCount {
  count: number
  section: string
}

export interface DownloadState {
  download_count: number
  section_count: SectionCount[]
}

export function pageDownloadLog(filter: DownloadLogFilter) {
  return request<DownloadLogResult>({
    url: `/download-log/search`,
    method: 'post',
    data: filter,
  })
}

export function getDownloadState() {
  return request<DownloadState>({
    url: `/download-log/state`,
    method: 'get',
  })
}
