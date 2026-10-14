import type { AxiosRequestConfig } from 'axios'
import { toast } from 'sonner'
import axios from './axios'

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export function request<T>(
  config: AxiosRequestConfig
): Promise<ApiResponse<T>> {
  return axios<ApiResponse<T>>(config).then((response) => {
    const body = response.data

    if (body.code !== 0) {
      toast.error(body.message)
      throw new Error(body.message || '操作失败，请检查设置后重试。')
    }
    return body
  })
}
