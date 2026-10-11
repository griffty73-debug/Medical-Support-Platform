<script setup>
import { AlertTriangle, Zap } from 'lucide-vue-next'
import { URGENCY } from '../constants'
defineProps({ level: { type: String, required: true }, always: Boolean })
</script>

<template>
  <span v-if="level !== 'routine' || always" class="tag" :class="level === 'routine' ? 'tone-closed' : `tone-${level}`"
        :title="URGENCY[level]?.hint">
    <AlertTriangle v-if="level === 'emergency'" :size="12" /><Zap v-else-if="level === 'urgent'" :size="12" />{{ URGENCY[level]?.label }}
  </span>
</template>
