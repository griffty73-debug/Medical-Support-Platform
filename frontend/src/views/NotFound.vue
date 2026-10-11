<script setup>
import { Compass } from 'lucide-vue-next'
import AppLink from '../components/AppLink.vue'
import EmptyState from '../components/EmptyState.vue'
</script>

<template>
  <div class="page">
    <EmptyState :icon="Compass" title="页面不存在" text="链接可能已失效。可以回到首页继续。">
      <AppLink to="/" class="btn btn-secondary">回到首页</AppLink>
    </EmptyState>
  </div>
</template>
