import { AxiosError } from 'axios'
import { toast } from 'sonner'
export function handleServerError(error: unknown) {
  if (error instanceof AxiosError && error.response?.status === 401) {
    toast.error('平台登录已过期，请返回 AWBotNest 重新登录。')
    return
  }
  toast.error(error instanceof Error ? error.message : '操作失败，请查看插件日志后重试。')
}
