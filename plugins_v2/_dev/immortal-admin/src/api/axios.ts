import Axios, { AxiosError, AxiosHeaders, type AxiosAdapter } from 'axios'
import { hostCall, type BridgeReply } from '@/lib/host-bridge'

const MAX_BODY = 6 * 1024 * 1024
const MAX_JSON = 2 * 1024 * 1024
const MAX_RESPONSE = 8 * 1024 * 1024
function encode(bytes: Uint8Array) {
  let text = ''
  for (let start = 0; start < bytes.length; start += 16384) text += String.fromCharCode(...bytes.subarray(start, start + 16384))
  return btoa(text)
}
function decode(value: string) {
  if (value.length > Math.ceil(MAX_RESPONSE / 3) * 4 + 4) throw new Error('返回文件超过 8 MB，请缩小导出范围。')
  const text = atob(value)
  if (text.length > MAX_RESPONSE) throw new Error('返回文件超过 8 MB，请缩小导出范围。')
  return Uint8Array.from(text, c => c.charCodeAt(0))
}
const adapter: AxiosAdapter = async config => {
  const relative = String(config.url || '')
  if (!relative.startsWith('/') || relative.startsWith('//') || /[\\\x00-\x1f]/.test(relative)) throw new Error('接口路径无效。')
  const url = new URL(`/api/v1${relative}`, 'http://plugin.invalid')
  const query: Record<string, string> = Object.fromEntries(url.searchParams)
  for (const [key, value] of Object.entries(config.params || {})) {
    if (value !== null && value !== undefined) query[key] = Array.isArray(value) ? value.join(',') : String(value)
  }
  const payload: Record<string, unknown> = { method: String(config.method || 'GET').toUpperCase(), path: url.pathname, query }
  const headers = AxiosHeaders.from(config.headers)
  if (config.data instanceof FormData) {
    const form = new Request('http://plugin.invalid', { method: 'POST', body: config.data })
    const bytes = new Uint8Array(await form.arrayBuffer())
    if (bytes.byteLength > MAX_BODY) throw new Error('上传文件超过 6 MB，请拆分后重新上传。')
    payload.body_base64 = encode(bytes); payload.content_type = form.headers.get('content-type')
    config.onUploadProgress?.({ loaded: bytes.byteLength, total: bytes.byteLength, progress: 1, bytes: bytes.byteLength, upload: true, lengthComputable: true })
  } else if (config.data !== undefined && config.data !== null) {
    const data = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    if (new TextEncoder().encode(JSON.stringify(data)).length > MAX_JSON) throw new Error('请求内容超过 2 MB，请缩小范围。')
    payload.body = data
    payload.content_type = String(headers.get('Content-Type') || 'application/json')
  }
  const reply = await hostCall<BridgeReply>('request', payload)
  if (!reply || !Number.isInteger(reply.status)) throw new Error('平台返回的接口结果无效，请刷新后重试。')
  const responseHeaders = AxiosHeaders.from(reply.headers || {})
  let data: unknown = reply.body
  if (reply.body_base64 !== undefined) {
    const bytes = decode(reply.body_base64)
    data = config.responseType === 'blob' ? new Blob([bytes], { type: String(responseHeaders.get('content-type') || 'application/octet-stream') })
      : config.responseType === 'arraybuffer' ? bytes.buffer : new TextDecoder().decode(bytes)
  } else if (config.responseType === 'blob') {
    data = new Blob([typeof data === 'string' ? data : JSON.stringify(data)], { type: String(responseHeaders.get('content-type') || 'application/octet-stream') })
  }
  const response = { data, status: reply.status, statusText: String(reply.status), headers: responseHeaders, config }
  if (reply.status < 200 || reply.status >= 300) {
    const errorBody = data as { detail?: string; message?: string } | undefined
    throw new AxiosError(errorBody?.detail || errorBody?.message || `请求失败（HTTP ${reply.status}）`, String(reply.status), config, undefined, response)
  }
  return response
}
export default Axios.create({ adapter, timeout: 125000 })
