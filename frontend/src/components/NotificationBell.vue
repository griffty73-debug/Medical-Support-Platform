<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { Bell, LoaderCircle } from 'lucide-vue-next'
import { api } from '../api'
import { refreshSummary, session, toast } from '../session'
import { navigate } from '../router'
import { relative } from '../format'

const open = ref(false)
const items = ref([])
const loading = ref(false)
const root = ref(null)

async function load() {
  loading.value = true
  try { items.value = await api('/notifications') }
  catch (err) { toast(err.message, 'error') }
  finally { loading.value = false }
}

function toggle() {
  open.value = !open.value
  if (open.value) load()
}

async function choose(item) {
  open.value = false
  if (!item.read) {
    await api('/notifications/read', { method: 'POST', body: { ids: [item.id] } }).catch(() => {})
    refreshSummary()
  }
  if (item.case_id) navigate(`/cases/${item.case_id}`)
}

async function readAll() {
  await api('/notifications/read', { method: 'POST', body: {} }).catch(err => toast(err.message, 'error'))
  items.value = items.value.map(item => ({ ...item, read: true }))
  refreshSummary()
}

function outside(event) { if (open.value && root.value && !root.value.contains(event.target)) open.value = false }
function escape(event) { if (event.key === 'Escape') open.value = false }
onMounted(() => { document.addEventListener('pointerdown', outside); document.addEventListener('keydown', escape) })
onUnmounted(() => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape) })
</script>

<template>
  <div ref="root" class="bell">
    <button class="icon-btn bell-button" :aria-expanded="open" aria-haspopup="true"
            :aria-label="session.unread ? `消息通知，${session.unread} 条未读` : '消息通知'" title="消息通知" @click="toggle">
      <Bell :size="20" />
      <span v-if="session.unread" class="bell-dot">{{ session.unread > 99 ? '99+' : session.unread }}</span>
    </button>
    <section v-if="open" class="bell-panel" aria-label="消息通知">
      <header>
        <h2>通知</h2>
        <button v-if="items.some(item => !item.read)" class="link-btn small" @click="readAll">全部标为已读</button>
      </header>
      <div v-if="loading && !items.length" class="bell-empty"><LoaderCircle class="spin" :size="18" /></div>
      <p v-else-if="!items.length" class="bell-empty">还没有通知。病例有新进展时会出现在这里。</p>
      <ul v-else>
        <li v-for="item in items" :key="item.id">
          <button :class="{ unread: !item.read }" @click="choose(item)">
            <strong>{{ item.title }}</strong>
            <span v-if="item.body" class="bell-body">{{ item.body }}</span>
            <time>{{ relative(item.created_at) }}</time>
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>
