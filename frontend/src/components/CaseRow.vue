<script setup>
import { computed } from 'vue'
import { ChevronRight, MessageCircle, Paperclip } from 'lucide-vue-next'
import { isDoctor } from '../api'
import { elapsed, relative } from '../format'
import AppLink from './AppLink.vue'
import StatusTag from './StatusTag.vue'
import UrgencyTag from './UrgencyTag.vue'

const props = defineProps({ item: { type: Object, required: true }, showWaiting: Boolean })

const note = computed(() => {
  const c = props.item
  if (isDoctor) {
    if (props.showWaiting && c.status === 'pending') return c.overdue ? `已超时 · 等待 ${elapsed(c.created_at)}` : `等待 ${elapsed(c.created_at)}`
    if (c.status === 'awaiting_info') return '等待患者补充资料'
    return `更新于 ${relative(c.updated_at)}`
  }
  if (c.status === 'awaiting_info') return '医生请你补充资料'
  if (c.status === 'declined') return '医生已退回，可改投其他医生'
  if (c.followup_state === 'due') return '已到随访时间'
  return `更新于 ${relative(c.updated_at)}`
})
const attention = computed(() => {
  const c = props.item
  return isDoctor ? c.overdue : ['awaiting_info', 'declined'].includes(c.status) || c.followup_state === 'due'
})
</script>

<template>
  <AppLink :to="`/cases/${item.id}`" class="case-row" :class="[`urgency-${item.urgency}`, { attention }]">
    <span class="case-row-main">
      <span class="case-row-title">
        <span v-if="item.kind === 'followup'" class="tag tone-closed">复诊</span>
        <strong>{{ item.title }}</strong>
      </span>
      <span class="case-row-meta">
        <template v-if="isDoctor">
          <span>{{ item.patient.name }}</span>
          <span v-if="item.patient.age !== undefined && item.patient.age !== null">{{ item.patient.gender }} {{ item.patient.age }} 岁</span>
          <span v-for="flag in item.flags || []" :key="flag" class="flag">{{ flag }}</span>
        </template>
        <template v-else>
          <span>{{ item.doctor.name }}</span><span>{{ item.doctor.department }}</span>
        </template>
        <span class="faint">{{ item.number }}</span>
      </span>
      <span class="case-row-note" :class="{ alert: attention }">{{ note }}</span>
    </span>
    <span class="case-row-side">
      <span class="case-row-tags">
        <UrgencyTag v-if="isDoctor" :level="item.urgency" />
        <StatusTag :status="item.status" />
      </span>
      <span class="case-row-icons">
        <span v-if="item.unread" class="unread" :aria-label="`${item.unread} 条新消息`"><MessageCircle :size="14" />{{ item.unread }}</span>
        <span v-if="item.attachment_count" class="faint" :aria-label="`${item.attachment_count} 个附件`"><Paperclip :size="13" />{{ item.attachment_count }}</span>
      </span>
    </span>
    <ChevronRight class="case-row-chevron" :size="18" aria-hidden="true" />
  </AppLink>
</template>
