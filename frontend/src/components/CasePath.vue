<script setup>
// The case path: one line, coloured by the case status, with a station for each
// step. It answers "where is my case now" at a glance.
import { computed } from 'vue'
import { STATUS } from '../constants'
import { day, dateTime } from '../format'

const props = defineProps({ record: { type: Object, required: true }, compact: Boolean })

const stations = computed(() => {
  const r = props.record
  const at = kind => [...(r.events || [])].reverse().find(e => e.kind === kind)?.created_at
  if (r.status === 'declined' || r.status === 'cancelled') {
    return [
      { label: '提交', time: r.created_at, state: 'done' },
      { label: r.status === 'declined' ? '医生退回' : '已撤回', time: at(r.status) || r.updated_at, state: 'stop' },
    ]
  }
  const list = [
    { label: '提交', time: r.created_at, state: 'done' },
    { label: '接诊', time: r.accepted_at, state: r.status === 'pending' ? 'current' : 'done' },
    { label: r.status === 'awaiting_info' ? '待你补充' : '评估', time: r.status === 'awaiting_info' ? at('info_requested') : null,
      state: r.status === 'pending' ? 'todo' : r.status === 'completed' ? 'done' : 'current' },
    { label: r.published_version > 1 ? '报告已更正' : '报告', time: r.amended_at || r.published_at,
      state: r.status === 'completed' ? (r.followup_due ? 'done' : 'current') : 'todo' },
  ]
  if (r.followup_due) {
    const state = r.followup_state === 'returned' ? 'done' : (r.followup_state === 'due' || r.followup_state === 'upcoming') ? 'current' : 'todo'
    list.push({ label: '随访', time: r.followup_due, date: true, state })
  }
  return list
})

const tone = computed(() => STATUS[props.record.status]?.tone || 'closed')
const progress = computed(() => {
  const list = stations.value
  const index = Math.max(0, list.findLastIndex(s => s.state !== 'todo'))
  return list.length > 1 ? index / (list.length - 1) : 0
})
</script>

<template>
  <ol class="case-path" :class="[`tone-${tone}`, { compact }]" :style="{ '--progress': progress, '--n': stations.length }"
      :aria-label="`病例进度：${STATUS[record.status]?.label}`">
    <li v-for="station in stations" :key="station.label" :class="station.state"
        :aria-current="station.state === 'current' ? 'step' : undefined">
      <span class="station" aria-hidden="true"></span>
      <span class="station-label">{{ station.label }}</span>
      <time v-if="station.time && !compact" class="station-time">{{ station.date ? day(station.time) : dateTime(station.time) }}</time>
    </li>
  </ol>
</template>
