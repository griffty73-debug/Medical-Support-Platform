<script setup>
import { computed, onMounted, ref } from 'vue'
import { ArrowRight, CalendarClock, ClipboardList, Plus, UserRound } from 'lucide-vue-next'
import { api } from '../../api'
import { day, greeting, untilText } from '../../format'
import { session } from '../../session'
import { caseStore, loadCases } from '../../store'
import AppLink from '../../components/AppLink.vue'
import CasePath from '../../components/CasePath.vue'
import CaseRow from '../../components/CaseRow.vue'
import StatusTag from '../../components/StatusTag.vue'

const profile = ref(null)
const active = computed(() => caseStore.list
  .filter(c => ['awaiting_info', 'declined', 'pending', 'processing'].includes(c.status))
  .sort((a, b) => rank(a) - rank(b)))
const followups = computed(() => caseStore.list.filter(c => c.followup_state === 'due' || c.followup_state === 'upcoming'))
const recent = computed(() => caseStore.list.filter(c => !active.value.includes(c)).slice(0, 4))
const needsAction = computed(() => active.value.filter(c => ['awaiting_info', 'declined'].includes(c.status)).length + followups.value.length)

function rank(c) { return { awaiting_info: 0, declined: 1, processing: 2, pending: 3 }[c.status] }

function next(c) {
  if (c.status === 'pending') return { text: `等待${c.doctor.name}接诊，预计 ${untilText(c.due_at)}回应` }
  if (c.status === 'processing') return { text: `${c.doctor.name}正在评估，报告发布后会通知你` }
  if (c.status === 'awaiting_info') return { text: '医生请你补充资料，补充后才能继续评估', action: '去补充' }
  return { text: '医生退回了这份病例，可以改投其他医生', action: '查看原因' }
}

const summary = computed(() => {
  if (!caseStore.loaded) return ''
  if (needsAction.value) return `有 ${needsAction.value} 件事需要你处理。`
  if (active.value.length) return `${active.value.length} 份病例正在推进，有进展会通知你。`
  return '描述你的症状，医生会结合健康档案给出评估。'
})

onMounted(async () => {
  loadCases()
  try { profile.value = await api('/profile') } catch { /* profile banner stays hidden */ }
})
</script>

<template>
  <div class="page home">
    <header class="home-head">
      <h1 class="title-doc page-title">{{ greeting() }}，{{ session.user.name }}</h1>
      <p class="muted">{{ summary }}</p>
    </header>

    <AppLink v-if="profile && !profile.complete" to="/me?setup=1" class="notice notice-action">
      <UserRound :size="20" />
      <span><strong>先完善健康档案</strong><span>身份证号、过敏史和当前用药是医生评估的基础，填写后才能提交病例。</span></span>
      <ArrowRight :size="18" />
    </AppLink>

    <section v-if="active.length" class="home-section" aria-labelledby="active-title">
      <h2 id="active-title" class="visually-hidden">进行中的病例</h2>
      <article v-for="item in active" :key="item.id" class="journey-card" :class="`status-${item.status}`">
        <header>
          <div>
            <AppLink :to="`/cases/${item.id}`" class="journey-title title-doc">{{ item.title }}</AppLink>
            <p class="faint small"><span>{{ item.doctor.name }}</span>　<span>{{ item.doctor.department }}</span>　<span>{{ item.number }}</span></p>
          </div>
          <StatusTag :status="item.status" />
        </header>
        <CasePath :record="item" compact />
        <footer>
          <p>{{ next(item).text }}<span v-if="item.unread && item.status !== 'awaiting_info'" class="unread-note">，医生发来 {{ item.unread }} 条消息</span></p>
          <AppLink :to="`/cases/${item.id}`" class="btn btn-sm" :class="next(item).action ? 'btn-primary' : 'btn-secondary'">{{ next(item).action || '查看' }}</AppLink>
        </footer>
      </article>
    </section>

    <section v-if="followups.length" class="home-section" aria-labelledby="followup-title">
      <h2 id="followup-title" class="section-title">随访提醒</h2>
      <div class="case-list">
        <div v-for="item in followups" :key="item.id" class="followup-row">
          <CalendarClock :size="20" />
          <span>
            <strong>{{ item.title }}</strong>
            <span class="small muted">{{ item.doctor.name }}建议在 {{ day(item.followup_due) }} 前后复诊{{ item.followup_state === 'due' ? '，现在可以发起' : '' }}</span>
          </span>
          <AppLink :to="`/cases/new?parent=${item.id}`" class="btn btn-secondary btn-sm">发起复诊</AppLink>
        </div>
      </div>
    </section>

    <AppLink to="/cases/new" class="btn btn-primary btn-lg new-case-cta"><Plus :size="20" />描述新的症状</AppLink>

    <section v-if="recent.length" class="home-section" aria-labelledby="recent-title">
      <div class="section-head">
        <h2 id="recent-title" class="section-title">以往病例</h2>
        <AppLink to="/cases" class="small">全部病例</AppLink>
      </div>
      <div class="case-list"><CaseRow v-for="item in recent" :key="item.id" :item="item" /></div>
    </section>

    <section v-if="caseStore.loaded && !caseStore.list.length" class="home-empty">
      <ClipboardList :size="22" />
      <p>写下哪里不舒服、从什么时候开始、有什么变化。可以附上检查报告或照片，医生会在 48 小时内回应，紧急情况会被优先处理。</p>
    </section>
  </div>
</template>
