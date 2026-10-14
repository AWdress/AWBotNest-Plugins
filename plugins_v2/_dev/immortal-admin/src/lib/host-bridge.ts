export type BridgeReply = { status: number; headers?: Record<string, string>; body?: unknown; body_base64?: string }
type Pending = { resolve: (value: unknown) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> }
const session = new URLSearchParams(location.search).get('bridge') || ''
const pending = new Map<string, Pending>()
let connected = false
let counter = 0
let readyResolve: (() => void) | undefined
let readyReject: ((error: Error) => void) | undefined
const ready = new Promise<void>((resolve, reject) => { readyResolve = resolve; readyReject = reject })
const connectTimer = setTimeout(() => readyReject?.(new Error('未连接到平台配置页，请返回插件页面重新打开。')), 15000)

function receive(event: MessageEvent) {
  if (event.source !== window.parent || event.origin !== location.origin) return
  const message = event.data
  if (!message || typeof message !== 'object' || message.session !== session) return
  if (message.type === 'immortal:connected') {
    connected = true; clearTimeout(connectTimer); readyResolve?.(); return
  }
  if (message.type !== 'immortal:response' || typeof message.id !== 'string') return
  const item = pending.get(message.id)
  if (!item) return
  pending.delete(message.id); clearTimeout(item.timer)
  message.error ? item.reject(new Error(String(message.error))) : item.resolve(message.result)
}
window.addEventListener('message', receive)
if (session && window.parent !== window) {
  window.parent.postMessage({ type: 'immortal:ready', session }, location.origin)
} else {
  clearTimeout(connectTimer)
  readyReject?.(new Error('请在 AWBotNest 插件配置页打开 Immortal。'))
}

export async function hostCall<T>(operation: 'request' | 'status', body?: unknown): Promise<T> {
  await ready
  if (!connected) throw new Error('与平台的连接已断开，请重新打开插件。')
  const id = `${Date.now().toString(36)}-${(++counter).toString(36)}`
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id)
      reject(new Error('请求超时，请查看任务状态；提交中的任务不要重复操作。'))
    }, 125000)
    pending.set(id, { resolve: value => resolve(value as T), reject, timer })
    window.parent.postMessage({ type: 'immortal:request', session, id, operation, body }, location.origin)
  })
}
window.addEventListener('pagehide', () => {
  connected = false; window.removeEventListener('message', receive); clearTimeout(connectTimer)
  for (const item of pending.values()) { clearTimeout(item.timer); item.reject(new Error('页面已关闭。')) }
  pending.clear()
}, { once: true })
export function waitForHost() { return ready }
