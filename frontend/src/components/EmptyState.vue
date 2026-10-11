<script setup>
defineProps({ icon: Object, title: { type: String, required: true }, text: String })
</script>

<template>
  <div class="empty">
    <component :is="icon" v-if="icon" :size="28" aria-hidden="true" />
    <h3>{{ title }}</h3>
    <p v-if="text">{{ text }}</p>
    <slot />
  </div>
</template>
