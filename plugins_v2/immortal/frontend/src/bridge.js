const methods = new Set(['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
const domains = new Set(['articles', 'config', 'tasks', 'download-log', 'rules', 'logs', 'rank', 'movies', 'casts', 'filters', 'priorities', 'subscribes'])
const forbiddenKeys = /^(?:TGBotConfig|DiscordBotConfig|WeComBotConfig|PageAgentConfig|Notification(?:\.|$))/
const maxBody = 6 * 1024 * 1024
const maxJSON = 2 * 1024 * 1024
export function validateBridgeBody(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('接口请求无效。')
  if (!methods.has(value.method) || typeof value.path !== 'string' || value.path.length > 300 || !value.path.startsWith('/api/v1/') || /[\\%\x00-\x20?#]/.test(value.path) || value.path.includes('..')) throw new Error('不允许的接口路径或方法。')
  const parts = value.path.slice(8).split('/')
  if (!domains.has(parts[0])) throw new Error('此功能由平台管理。')
  if (parts[0] === 'config' && forbiddenKeys.test(parts[1] || String(value.body?.key || ''))) throw new Error('机器人和通知渠道请在平台配置。')
  if (value.query && (typeof value.query !== 'object' || Array.isArray(value.query) || Object.keys(value.query).length > 30 || new TextEncoder().encode(JSON.stringify(value.query)).length > 20000 || Object.entries(value.query).some(([key, entry]) => key.length > 100 || typeof entry !== 'string' || entry.length > 16000))) throw new Error('接口参数无效。')
  if (value.body_base64 !== undefined) {
    if (typeof value.body_base64 !== 'string' || value.body_base64.length > Math.ceil(maxBody / 3) * 4 || !/^[A-Za-z0-9+/]*={0,2}$/.test(value.body_base64) || value.body_base64.length % 4 !== 0 || value.body !== undefined) throw new Error('文件内容无效或超过 6 MB。')
  } else if (value.body !== undefined && new TextEncoder().encode(JSON.stringify(value.body)).length > maxJSON) throw new Error('请求超过 2 MB。')
  if (value.content_type !== undefined && (typeof value.content_type !== 'string' || value.content_type.length > 200 || /[\r\n]/.test(value.content_type))) throw new Error('文件类型无效。')
  return value
}
export function createHostBridge({ host, iframe, session, origin, connected, error }) {
  let closed = false
  let active = 0
  const seen = new Set()
  return {
    close() { closed = true; seen.clear() },
    async receive(event) {
      if (closed || !iframe() || event.source !== iframe().contentWindow || event.origin !== origin) return
      const message = event.data
      if (!message || typeof message !== 'object' || message.session !== session) return
      const reply = result => { if (!closed && iframe()?.contentWindow === event.source) event.source.postMessage(result, origin) }
      if (message.type === 'immortal:ready') {
        connected(); reply({ type: 'immortal:connected', session }); return
      }
      if (message.type !== 'immortal:request' || typeof message.id !== 'string' || !/^[a-z0-9-]{1,80}$/.test(message.id) || seen.has(message.id)) return
      seen.add(message.id)
      if (seen.size > 10000) { error('管理页请求过多，请重新打开管理页。'); return }
      try {
        if (++active > 24) throw new Error('请求过多，请稍后重试。')
        let result
        if (message.operation === 'status' && message.body === undefined) result = await host.callApi('/status')
        else if (message.operation === 'request') result = await host.callApi('/request', { method: 'POST', body: validateBridgeBody(message.body) })
        else throw new Error('不允许的操作。')
        reply({ type: 'immortal:response', session, id: message.id, result })
      } catch (failure) {
        reply({ type: 'immortal:response', session, id: message.id, error: failure instanceof Error ? failure.message : '请求失败，请查看插件日志。' })
      } finally { active-- }
    },
  }
}
