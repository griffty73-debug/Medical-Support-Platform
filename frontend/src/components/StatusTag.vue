<script setup>
import { computed } from 'vue'
import { STATUS } from '../constants'
const props = defineProps({ status: { type: String, required: true } })
const meta = computed(() => STATUS[props.status] || { label: props.status, tone: 'closed' })
</script>

<template>
  <span class="tag" :class="`tone-${meta.tone}`"><span class="dot"></span>{{ meta.label }}</span>
</template>
