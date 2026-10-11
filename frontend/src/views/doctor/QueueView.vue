<script setup>
import { computed, onMounted } from 'vue'
import { CircleAlert, Inbox, LoaderCircle } from 'lucide-vue-next'
import { fullDay } from '../../format'
import { session } from '../../session'
import { byPriority, caseStore, loadCases } from '../../store'
import CaseRow from '../../components/CaseRow.vue'
import EmptyState from '../../components/EmptyState.vue'

const groups = computed(() => {
  const list = caseStore.list
  return [
    { key: 'pending', title: '待接诊', hint: '按紧急程度和等待时间排序', items: list.filter(c => c.status === 'pending').sort(byPriority), waiting: true },
    { key: 'processing', title: '评估中', hint: '已接诊、尚未发布报告', items: list.filter(c => c.status === 'processing').sort(byPriority) },
    { key: 'awaiting', title: '等待患者补充', hint: '患者补充后会回到评估中', items: list.filter(c => c.status === 'awaiting_info') },
    { key: 'messages', title: '已完成病例的新消息', hint: '报告发布后患者的追问', items: list.filter(c => c.status === 'completed' && c.unread > 0) },
  ].filter(group => group.items.length)
})

const summary = computed(() => {
  const pending = caseStore.list.filter(c => c.status === 'pending')
  const emergency = pending.filter(c => c.urgency === 'emergency').length
  const overdue = pending.filter(c => c.overdue).length
  if (!pending.length) return '没有等待接诊的病例。'
  return `${pending.length} 份病例等待接诊` + (emergency ? `，其中 ${emergency} 份紧急` : '') + (overdue ? `，${overdue} 份已超过响应时限` : '') + '。'
})

onMounted(loadCases)
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div>
        <h1 class="title-doc page-title">接诊队列</h1>
        <p>{{ fullDay(new Date().toISOString()) }}　{{ summary }}</p>
      </div>
    </header>
    <p v-if="!session.user.accepting" class="notice notice-block">
      <CircleAlert :size="20" /><span><strong>你已暂停接诊</strong><span>患者暂时不能选择你，已接收的病例仍需处理。可以在左下角恢复接诊。</span></span>
    </p>
    <div v-if="!caseStore.loaded" class="loading"><LoaderCircle class="spin" :size="20" /></div>
    <template v-else-if="groups.length">
      <section v-for="group in groups" :key="group.key" class="queue-group" :aria-labelledby="`group-${group.key}`">
        <div class="section-head">
          <h2 :id="`group-${group.key}`" class="section-title">{{ group.title }}<span class="count quiet">{{ group.items.length }}</span></h2>
          <span class="faint small">{{ group.hint }}</span>
        </div>
        <div class="case-list"><CaseRow v-for="item in group.items" :key="item.id" :item="item" :show-waiting="group.waiting" /></div>
      </section>
    </template>
    <EmptyState v-else :icon="Inbox" title="队列已清空" text="新的病例、患者补充的资料和消息会出现在这里。" />
  </div>
</template>
