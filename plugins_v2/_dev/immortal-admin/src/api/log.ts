import { request } from '@/api/request.ts'

export interface LogFilter {
  page_size?: number
  before_line_no?: number
  after_line_no?: number
}

export interface LogEntry {
  line_no: number
  text: string
}

export interface LogPage {
  items: LogEntry[]
  total_lines: number
  page_size: number
  before_line_no?: number | null
  after_line_no?: number | null
  oldest_line_no: number | null
  latest_line_no: number | null
  has_more_before: boolean
  has_more_after: boolean
}

export function fetchLogs(filters: LogFilter) {
  return request<LogPage>({ url: '/logs/', method: 'get', params: filters })
}
