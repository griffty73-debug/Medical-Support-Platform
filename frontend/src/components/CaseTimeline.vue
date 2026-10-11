<script setup>
import { dateTime } from '../format'
defineProps({ events: { type: Array, required: true } })
</script>

<template>
  <ol class="timeline">
    <li v-for="(event, index) in [...events].reverse()" :key="index" :class="`event-${event.kind}`">
      <span class="timeline-mark" aria-hidden="true"></span>
      <div>
        <p class="timeline-message">{{ event.message }}</p>
        <p v-if="event.detail" class="timeline-detail prewrap">{{ event.detail }}</p>
        <time class="faint tiny">{{ dateTime(event.created_at) }}</time>
      </div>
    </li>
  </ol>
</template>
