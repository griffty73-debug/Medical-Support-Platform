<script setup>
import { computed, onMounted } from 'vue'
import { CalendarClock, LoaderCircle } from 'lucide-vue-next'
import { day } from '../../format'
import { caseStore, loadCases } from '../../store'
import AppLink from '../../components/AppLink.vue'
import EmptyState from '../../components/EmptyState.vue'

const byDue = (a, b) => a.followup_due.localeCompare(b.followup_due)
const groups = computed(() => {
  const list = caseStore.list.filter(c => c.followup_due && c.status === 'completed')
  return [
    { key: 'due', title: '已到随访时间', hint: '患者还没有发起复诊，可以发消息问候', items: list.filter(c => c.followup_state === 'due').sort(byDue) },
    { key: 'upcoming', title: '即将到期', hint: '两天内到期，患者已收到提醒', items: list.filter(c => c.followup_state === 'upcoming').sort(byDue) },
    { key: 'scheduled', title: '已安排', items: list.filter(c => c.followup_state === 'scheduled').sort(byDue) },
    { key: 'returned', title: '已复诊', items: list.filter(c => c.followup_state === 'returned').sort(byDue) },
  ].filter(group => group.items.length)
})
onMounted(loadCases)
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div><h1 class="title-doc page-title">随访</h1><p>报告中设置了随访时间的病例。患者会在到期前收到提醒，并可以基于原病例发起复诊。</p></div>
    </header>
    <div v-if="!caseStore.loaded" class="loading"><LoaderCircle class="spin" :size="20" /></div>
    <template v-else-if="groups.length">
      <section v-for="group in groups" :key="group.key" class="queue-group">
        <div class="section-head"><h2 class="section-title">{{ group.title }}<span class="count quiet">{{ group.items.length }}</span></h2><span v-if="group.hint" class="faint small">{{ group.hint }}</span></div>
        <div class="case-list">
          <div v-for="item in group.items" :key="item.id" class="followup-row">
            <span class="followup-date" :class="{ due: group.key === 'due' }">{{ day(item.followup_due) }}</span>
            <span>
              <AppLink :to="`/cases/${item.id}`"><strong>{{ item.title }}</strong></AppLink>
              <span class="small muted">{{ item.patient.name }}　{{ item.patient.gender }} {{ item.patient.age }} 岁　{{ item.number }}</span>
            </span>
            <AppLink v-if="group.key === 'due' || group.key === 'upcoming'" :to="`/cases/${item.id}?tab=messages`" class="btn btn-secondary btn-sm">发消息问候</AppLink>
          </div>
        </div>
      </section>
    </template>
    <EmptyState v-else :icon="CalendarClock" title="暂无随访" text="在报告中选择随访天数后，病例会出现在这里。" />
  </div>
</template>
