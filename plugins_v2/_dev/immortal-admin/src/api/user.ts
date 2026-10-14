import { hostCall } from '@/lib/host-bridge'
export async function getVersion() {
  const result = await hostCall<{ version: string }>('status')
  return { code: 0, message: '已读取插件版本', data: result.version }
}
