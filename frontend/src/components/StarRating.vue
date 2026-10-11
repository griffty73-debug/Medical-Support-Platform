<script setup>
import { Star } from 'lucide-vue-next'
const value = defineModel({ type: Number, default: 0 })
defineProps({ readonly: Boolean })
const labels = ['', '不满意', '一般', '还可以', '满意', '非常满意']
</script>

<template>
  <div v-if="readonly" class="stars readonly" :aria-label="`${value} 星，${labels[value]}`">
    <Star v-for="n in 5" :key="n" :size="18" :class="{ on: n <= value }" />
  </div>
  <div v-else class="stars" role="radiogroup" aria-label="评分">
    <button v-for="n in 5" :key="n" type="button" role="radio" :aria-checked="value === n" :aria-label="`${n} 星，${labels[n]}`"
            :class="{ on: n <= value }" @click="value = n"><Star :size="26" /></button>
    <span class="small muted">{{ labels[value] }}</span>
  </div>
</template>
