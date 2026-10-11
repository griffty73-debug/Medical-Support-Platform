<script setup>
defineProps({ size: { type: Number, default: 32 } })
</script>

<template>
  <!-- A wayfinding line that turns a corner: from first visit to report. -->
  <svg :width="size" :height="size" viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="8" fill="var(--accent)" />
    <path d="M8.5 22.5 H17.5 a4.5 4.5 0 0 0 4.5 -4.5 V9.5" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" />
    <circle cx="8.5" cy="22.5" r="2.6" fill="#fff" />
    <circle cx="22" cy="9.5" r="3.4" fill="var(--accent)" stroke="#fff" stroke-width="2.4" />
  </svg>
</template>
