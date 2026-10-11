export const portal = __PORTAL__
export const isDoctor = portal === 'doctor'

const tokenKey = `medical-platform-${portal}-token`

export function token() {
  try { return sessionStorage.getItem(tokenKey) } catch { return null }
}

export function setToken(value) {
  try {
    if (value) sessionStorage.setItem(tokenKey, value)
    else sessionStorage.removeItem(tokenKey)
  } catch { /* storage unavailable: the session lasts until reload */ }
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  if (token()) headers.Authorization = `Bearer ${token()}`
  let payload
  if (form) {
    payload = new FormData()
    for (const [key, value] of Object.entries(form)) {
      if (value === undefined || value === null) continue
      if (Array.isArray(value) && value.every(item => item instanceof Blob)) value.forEach(item => payload.append(key, item))
      else if (value instanceof Blob) payload.append(key, value)
      else payload.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value))
    }
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  let response
  try {
    response = await fetch(`/api${path}`, { method, headers, body: payload })
  } catch {
    throw new ApiError('网络连接失败，请检查网络后重试', 0)
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth/login') && !path.startsWith('/auth/register')) {
      setToken(null)
      window.dispatchEvent(new Event('auth-expired'))
    }
    throw new ApiError(data.error || '请求失败，请稍后重试', response.status)
  }
  return data
}

export async function download(path, filename) {
  const response = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${token()}` } })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(data.error || '下载失败，请稍后重试', response.status)
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
