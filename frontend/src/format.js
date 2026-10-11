const zh = 'zh-CN'

export function dateTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString(zh, { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function day(value) {
  if (!value) return ''
  const date = new Date(value.length === 10 ? value + 'T00:00:00' : value)
  return date.toLocaleDateString(zh, { month: 'numeric', day: 'numeric' })
}

export function fullDay(value) {
  if (!value) return ''
  const date = new Date(value.length === 10 ? value + 'T00:00:00' : value)
  return date.toLocaleDateString(zh, { year: 'numeric', month: 'long', day: 'numeric' })
}

/** "3 分钟前", "2 小时前", "昨天 14:20", "10月3日" */
export function relative(value) {
  if (!value) return ''
  const date = new Date(value)
  const seconds = (Date.now() - date.getTime()) / 1000
  if (seconds < 60) return '刚刚'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`
  const today = new Date()
  if (date.toDateString() === today.toDateString()) return `${Math.floor(seconds / 3600)} 小时前`
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  const time = date.toLocaleTimeString(zh, { hour: '2-digit', minute: '2-digit' })
  if (date.toDateString() === yesterday.toDateString()) return `昨天 ${time}`
  return date.toLocaleDateString(zh, { month: 'numeric', day: 'numeric' })
}

/** Elapsed time as "45 分钟", "3 小时", "2 天". */
export function elapsed(value) {
  const minutes = Math.max(0, (Date.now() - new Date(value).getTime()) / 60000)
  if (minutes < 60) return `${Math.max(1, Math.floor(minutes))} 分钟`
  if (minutes < 60 * 48) return `${Math.floor(minutes / 60)} 小时`
  return `${Math.floor(minutes / 1440)} 天`
}

export function untilText(value) {
  const minutes = (new Date(value).getTime() - Date.now()) / 60000
  if (minutes <= 0) return '已超时'
  if (minutes < 60) return `${Math.ceil(minutes)} 分钟内`
  if (minutes < 60 * 48) return `${Math.ceil(minutes / 60)} 小时内`
  return `${Math.ceil(minutes / 1440)} 天内`
}

export function fileSize(value) {
  return value > 1024 * 1024 ? `${(value / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(value / 1024))} KB`
}

export function greeting() {
  const hour = new Date().getHours()
  return hour < 5 ? '夜深了' : hour < 11 ? '早上好' : hour < 13 ? '中午好' : hour < 18 ? '下午好' : '晚上好'
}
