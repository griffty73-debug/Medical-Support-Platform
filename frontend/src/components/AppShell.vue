<script setup>
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { CalendarClock, ClipboardList, House, Inbox, LogOut, Settings, Stethoscope, UserRound, Files } from 'lucide-vue-next'
import { api, isDoctor } from '../api'
import { canLeave, route } from '../router'
import { session, signOut, toast } from '../session'
import { caseStore, loadCases, resetCases } from '../store'
import AppLink from './AppLink.vue'
import BrandMark from './BrandMark.vue'
import NotificationBell from './NotificationBell.vue'

const counts = computed(() => {
  const list = caseStore.list
  return {
    pending: list.filter(c => c.status === 'pending').length,
    attention: list.filter(c => c.status === 'awaiting_info' || c.unread > 0 || c.status === 'declined').length,
    followups: list.filter(c => c.followup_state === 'due' || c.followup_state === 'upcoming').length,
  }
})

const nav = computed(() => isDoctor
  ? [
      { to: '/', label: '接诊队列', icon: Inbox, badge: counts.value.pending },
      { to: '/cases', label: '全部病例', icon: Files },
      { to: '/followups', label: '随访', icon: CalendarClock, badge: counts.value.followups, quiet: true },
      { to: '/me', label: '设置', icon: Settings },
    ]
  : [
      { to: '/', label: '首页', icon: House },
      { to: '/cases', label: '病例', icon: ClipboardList, badge: counts.value.attention },
      { to: '/doctors', label: '医生', icon: Stethoscope },
      { to: '/me', label: '我的', icon: UserRound },
    ])

function active(to) {
  if (to === '/') return route.path === '/'
  if (to === '/cases') return route.path.startsWith('/cases')
  return route.path.startsWith(to)
}

async function toggleAccepting(event) {
  const accepting = event.target.checked
  try {
    session.user = await api('/account/doctor', { method: 'PUT', body: { accepting } })
    toast(accepting ? '已恢复接诊，患者可以向你提交病例' : '已暂停接诊，新病例将无法选择你')
  } catch (err) {
    event.target.checked = !accepting
    toast(err.message, 'error')
  }
}

function logout() {
  if (!canLeave()) return
  resetCases()
  signOut()
}

let timer
onMounted(() => {
  loadCases()
  timer = setInterval(() => { if (!document.hidden) loadCases() }, 30000)
})
onUnmounted(() => clearInterval(timer))
watch(() => session.activity, () => loadCases())
</script>

<template>
  <div class="shell" :class="isDoctor ? 'shell-doctor' : 'shell-patient'">
    <a class="skip-link" href="#main">跳到主要内容</a>

    <aside v-if="isDoctor" class="sidebar">
      <AppLink to="/" class="brand"><BrandMark :size="30" /><span>医疗平台<small>医生工作台</small></span></AppLink>
      <nav aria-label="主导航" class="side-nav">
        <AppLink v-for="item in nav" :key="item.to" :to="item.to" :title="item.label" :class="{ active: active(item.to) }" :aria-current="active(item.to) ? 'page' : undefined">
          <component :is="item.icon" :size="19" /><span>{{ item.label }}</span>
          <span v-if="item.badge" class="count" :class="{ quiet: item.quiet }">{{ item.badge }}</span>
        </AppLink>
      </nav>
      <div class="side-foot">
        <label class="switch accepting">
          <input type="checkbox" :checked="session.user.accepting" @change="toggleAccepting" />
          <span class="track"></span>
          <span>{{ session.user.accepting ? '正在接诊' : '已暂停接诊' }}</span>
        </label>
        <div class="side-account">
          <span class="avatar">{{ session.user.name.slice(-2) }}</span>
          <span class="side-account-text"><strong>{{ session.user.name }}</strong><span>{{ session.user.department }}</span></span>
          <button class="icon-btn" title="退出登录" aria-label="退出登录" @click="logout"><LogOut :size="18" /></button>
        </div>
      </div>
    </aside>

    <header class="topbar">
      <div class="topbar-inner">
        <AppLink to="/" class="brand"><BrandMark :size="28" /><span>医疗平台<small v-if="isDoctor">医生工作台</small></span></AppLink>
        <nav v-if="!isDoctor" aria-label="主导航" class="top-nav">
          <AppLink v-for="item in nav" :key="item.to" :to="item.to" :class="{ active: active(item.to) }" :aria-current="active(item.to) ? 'page' : undefined">
            {{ item.label }}<span v-if="item.badge" class="count">{{ item.badge }}</span>
          </AppLink>
        </nav>
        <NotificationBell />
      </div>
    </header>

    <main id="main" class="main" tabindex="-1"><slot /></main>

    <nav aria-label="主导航" class="tabbar">
      <AppLink v-for="item in nav" :key="item.to" :to="item.to" :class="{ active: active(item.to) }" :aria-current="active(item.to) ? 'page' : undefined">
        <span class="tab-icon"><component :is="item.icon" :size="22" /><span v-if="item.badge" class="count">{{ item.badge }}</span></span>
        <span>{{ item.label }}</span>
      </AppLink>
    </nav>
  </div>
</template>
