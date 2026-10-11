import { reactive } from 'vue'
import { api } from './api'

// Case list shared by the navigation counts and the list views.
export const caseStore = reactive({ list: [], loaded: false, error: '' })
let inflight = null

export function loadCases() {
  if (inflight) return inflight
  inflight = api('/cases')
    .then(list => { caseStore.list = list; caseStore.loaded = true; caseStore.error = '' })
    .catch(err => { caseStore.error = err.message })
    .finally(() => { inflight = null })
  return inflight
}

export function resetCases() {
  caseStore.list = []
  caseStore.loaded = false
}

const rank = { emergency: 0, urgent: 1, routine: 2 }
/** Doctor queue order: urgency first, then overdue, then longest waiting. */
export function byPriority(a, b) {
  return (rank[a.urgency] - rank[b.urgency]) || (Number(b.overdue) - Number(a.overdue))
    || (new Date(a.created_at) - new Date(b.created_at))
}
