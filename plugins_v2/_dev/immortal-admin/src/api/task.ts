import { request } from '@/api/request.ts'

export interface ArgRule {
  label: string
  key: string
  required?: boolean
  require?: boolean
  type: 'string' | 'number' | 'select' | 'multi-select' | 'boolean' | 'directory'
  options?: { label: string; value: string }[]
  description?: string
  placeholder?: string
}

export interface TaskFunc {
  func_name: string
  func_label: string
  func_args: string[]
  func_args_rule: ArgRule[]
}

export interface Task {
  id: number
  task_name: string
  task_func: string
  task_args: string
  task_cron: string
  enable: boolean
  push_enable: boolean
  push_title_template: string | null
  push_message_template: string | null
}

export interface TaskDirectoryItem {
  name: string
  path: string
}

export interface TaskDirectoryBrowseResult {
  current_path: string
  parent_path: string | null
  items: TaskDirectoryItem[]
}

export interface TaskRunningResult {
  task_ids: number[]
}

export interface TaskLogFilter {
  page: number
  pageSize: number
  task_func: string
}
export interface TaskLog {
  id: number
  task_name: string
  task_func: string
  start_time: string
  end_time: string
  execute_seconds: number
  execute_result: string
  execute_flag: string
  success: boolean
  error: string
  create_time: string
}
export interface TaskLogResult {
  total: number
  items: TaskLog[]
}

export function getTasks() {
  return request<Task[]>({ url: '/tasks/' })
}

export function fetchFuncList() {
  return request<TaskFunc[]>({ url: '/tasks/funcs' })
}

export function browseTaskDirectories(path?: string) {
  return request<TaskDirectoryBrowseResult>({
    url: '/tasks/browse-dirs',
    params: path ? { path } : undefined,
  })
}

export function addTask(task: Task) {
  return request({ url: '/tasks/', method: 'post', data: task })
}

export function updateTask(task: Task) {
  return request({ url: '/tasks/', method: 'put', data: task })
}

export function deleteTask(task_id: number) {
  return request({ url: `/tasks/${task_id}`, method: 'delete' })
}

export function runTask(task_id: number) {
  return request<{ running: boolean; task_id: number }>({ url: `/tasks/run/${task_id}`, method: 'get' })
}

export function getRunningTasks() {
  return request<TaskRunningResult>({ url: '/tasks/running' })
}

export function pageTaskLog(filter: TaskLogFilter) {
  return request<TaskLogResult>({
    url: `/tasks/log/search`,
    method: 'post',
    data: {
      page: filter.page,
      page_size: filter.pageSize,
      task_func: filter.task_func,
    },
  })
}
