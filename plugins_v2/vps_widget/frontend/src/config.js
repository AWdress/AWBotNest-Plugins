export const sources = [
  ['guduo', '骨朵'], ['douban', '豆瓣'], ['mgtv', '芒果 TV'], ['theater', '剧场片单'],
  ['bangumi', 'Bangumi'], ['tmdb', 'TMDB'], ['bili', 'B站'], ['mal', 'MyAnimeList'],
  ['anilist', 'AniList'], ['trakt', 'Trakt'],
]
export const defaults = {
  tmdb_key: '', trakt_client_id: '', sources: sources.map(([id]) => id), category_limit: 30,
  auto_update: false, update_time: '17:00', notify_results: false, public_enabled: false, public_base_url: '',
}
export function configValues(saved) {
  if (!saved || typeof saved !== 'object' || Array.isArray(saved)) throw new Error('配置读取失败')
  const value = {}
  for (const [key, fallback] of Object.entries(defaults)) value[key] = structuredClone(saved[key] ?? fallback)
  return value
}
export function validate(value) {
  const errors = {}
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(value.update_time)) errors.update_time = '请填写 00:00～23:59。'
  if (!Number.isInteger(value.category_limit) || value.category_limit < 10 || value.category_limit > 100) errors.category_limit = '请填写 10～100 的整数。'
  if (!Array.isArray(value.sources) || value.sources.some((id) => !sources.some(([key]) => key === id))) errors.sources = '榜单来源无效，请重新读取。'
  for (const key of ['auto_update', 'public_enabled', 'notify_results']) if (typeof value[key] !== 'boolean') errors[key] = '开关格式无效，请重新读取。'
  for (const key of ['tmdb_key', 'trakt_client_id']) if (typeof value[key] !== 'string' || value[key].length > 2048 || /[\x00-\x1f]/.test(value[key])) errors[key] = '密钥格式无效。'
  const base = String(value.public_base_url).trim()
  if (base) {
    try {
      const url = new URL(base)
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash
        || /[\s\\<>"']/.test(base) || url.pathname.split('/').includes('api') || /(?:^|\/)\.{1,2}(?:\/|$)/.test(base)) throw new Error()
    } catch { errors.public_base_url = '请填写有效的平台 http(s) 地址，不含密码、查询参数或 /api 路径。' }
  }
  if (value.public_enabled && !base) errors.public_base_url = '开启客户端读取前，请填写平台访问地址。'
  return errors
}
export function apiError(error, action) {
  const status = Number(error?.status || error?.statusCode || error?.response?.status)
  if ([404, 409].includes(status)) return `${action}失败：请先在插件列表启用 VPS-Widget，再重试。`
  if ([401, 403].includes(status)) return `${action}失败：请重新登录平台管理员账号。`
  return `${action}失败，请检查插件是否启用、平台日志或网络后重试。你的填写内容已保留。`
}
