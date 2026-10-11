import { reactive } from 'vue'
import { api, isDoctor, portal, setToken, token } from './api'
import { navigate } from './router'

export const session = reactive({
  user: null,
  booting: true,
  unread: 0,
  // Increments whenever the server reports new activity, so open views can refresh.
  activity: 0,
  toast: null,
})

let toastTimer
let pollTimer

export function toast(message, type = 'success') {
  session.toast = { message, type, id: Date.now() }
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { session.toast = null }, type === 'error' ? 6000 : 3500)
}

export async function boot() {
  if (token()) {
    try {
      const user = await api('/auth/me')
      if (user.role === portal) session.user = user
      else setToken(null)
    } catch { setToken(null) }
  }
  session.booting = false
  if (session.user) startPolling()
}

export function signIn(result) {
  setToken(result.token)
  session.user = result.user
  startPolling()
}

export function signOut({ expired = false } = {}) {
  setToken(null)
  session.user = null
  session.unread = 0
  clearInterval(pollTimer)
  navigate('/', { replace: true })
  if (expired) toast('登录已过期，请重新登录', 'error')
}

export async function refreshSummary() {
  if (!session.user) return
  try {
    const { unread_notifications: unread } = await api('/summary')
    if (unread > session.unread) session.activity++
    session.unread = unread
  } catch { /* the next foreground request reports problems */ }
}

function startPolling() {
  clearInterval(pollTimer)
  refreshSummary()
  pollTimer = setInterval(() => { if (!document.hidden) refreshSummary() }, isDoctor ? 15000 : 20000)
}

window.addEventListener('auth-expired', () => { if (session.user) signOut({ expired: true }) })
document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshSummary() })
