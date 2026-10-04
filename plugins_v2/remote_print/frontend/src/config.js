const has = (value, key) => Object.prototype.hasOwnProperty.call(value, key)
const clone = (value) => value === undefined ? undefined : JSON.parse(JSON.stringify(value))

export function configFields(schema) {
  return Object.entries(schema).filter(([, spec]) => !['info', 'action'].includes(spec.type))
}

export function configValues(schema, saved) {
  if (!saved || typeof saved !== 'object' || Array.isArray(saved)) {
    throw new Error('平台未返回有效配置，已停止保存。请重新读取。')
  }
  const values = {}
  for (const [key, spec] of configFields(schema)) {
    if (has(saved, key)) values[key] = clone(saved[key])
    else if (has(spec, 'default')) values[key] = clone(spec.default)
  }
  return values
}

export function configPayload(schema, values) {
  const payload = {}
  for (const [key] of configFields(schema)) {
    if (has(values, key)) payload[key] = clone(values[key])
  }
  return payload
}

export function isVisible(spec, values) {
  if (!spec.show_if || typeof spec.show_if !== 'object') return true
  return Object.entries(spec.show_if).every(([key, expected]) => values[key] === expected)
}

export function validateConfig(schema, values) {
  const errors = {}
  for (const [key, spec] of configFields(schema)) {
    if (!isVisible(spec, values)) continue
    const value = values[key]
    const empty = value === undefined || value === null || value === ''
    if (spec.required && empty) errors[key] = '请填写此项。'
    else if (spec.type === 'number' && !empty) {
      if (typeof value !== 'number' || !Number.isFinite(value)) errors[key] = '请填写有效数字。'
      else if (!Number.isInteger(value)) errors[key] = '请填写整数。'
      else if (spec.min !== undefined && value < spec.min) errors[key] = `不能小于 ${spec.min}。`
      else if (spec.max !== undefined && value > spec.max) errors[key] = `不能大于 ${spec.max}。`
    }
  }
  return errors
}

export function apiError(error, operation = '操作') {
  const text = String(error?.message || error || `${operation}失败`)
  const status = Number(error?.status || error?.statusCode || error?.response?.status)
  if (status === 404 || status === 409 || /\b(?:404|409)\b/.test(text)
      || /插件未启用|插件尚未运行|接口未注册|未注册接口|插件不存在或尚未安装/.test(text)) {
    return `${operation}未执行：请先在插件列表启用“远程打印”，再重试。\n${text}`
  }
  if (status === 401 || status === 403 || /\b(?:401|403)\b/.test(text)) {
    return `${operation}失败：请确认管理员登录仍有效，并重新登录后重试。\n${text}`
  }
  return `${operation}失败：${text}`
}
