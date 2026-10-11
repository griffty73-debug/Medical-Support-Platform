// A small history router: the app has a handful of routes per portal and no
// nested views, so a dependency is not needed.
import { reactive } from 'vue'

export const route = reactive({ path: location.pathname, query: parse(location.search) })
let leaveGuard = null

function parse(search) {
  return Object.fromEntries(new URLSearchParams(search))
}

function sync() {
  route.path = location.pathname
  route.query = parse(location.search)
}

/** Register a function that returns false to keep the user on the page (unsaved edits). */
export function setLeaveGuard(fn) {
  leaveGuard = fn
}

export function canLeave() {
  return !leaveGuard || leaveGuard() !== false
}

export function navigate(to, { replace = false } = {}) {
  if (to === location.pathname + location.search) return true
  if (!canLeave()) return false
  leaveGuard = null
  history[replace ? 'replaceState' : 'pushState']({}, '', to)
  sync()
  window.scrollTo(0, 0)
  return true
}

window.addEventListener('popstate', () => {
  if (!canLeave()) {
    history.pushState({}, '', route.path + (Object.keys(route.query).length ? '?' + new URLSearchParams(route.query) : ''))
    return
  }
  leaveGuard = null
  sync()
})

/** Match a path against `{ '/cases/:id': Component }` patterns; returns { component, params }. */
export function resolve(routes, path) {
  for (const [pattern, component] of Object.entries(routes)) {
    const keys = []
    const expression = new RegExp('^' + pattern.replace(/:(\w+)/g, (_, key) => { keys.push(key); return '([^/]+)' }) + '/?$')
    const match = path.match(expression)
    if (match) return { component, params: Object.fromEntries(keys.map((key, index) => [key, decodeURIComponent(match[index + 1])])) }
  }
  return null
}

/** Use on <a> elements: keeps modifier-click behaviour and routes plain clicks in-app. */
export function linkHandler(event, to) {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  navigate(to)
}
