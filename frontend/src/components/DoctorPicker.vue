<script setup>
import { computed } from 'vue'
import { Star } from 'lucide-vue-next'

const selected = defineModel({ type: [Number, String, null], default: null })
const props = defineProps({
  doctors: { type: Array, required: true },
  suggested: { type: String, default: '' },
  exclude: { type: Array, default: () => [] },
  name: { type: String, default: 'doctor' },
})

const options = computed(() => {
  const list = props.doctors.filter(d => !props.exclude.includes(d.id))
  const matches = d => props.suggested && d.department && (props.suggested.includes(d.department) || d.department.includes(props.suggested))
  return [...list].sort((a, b) => (Number(b.accepting) - Number(a.accepting)) || (Number(matches(b)) - Number(matches(a))))
    .map(d => ({ ...d, match: matches(d) }))
})
</script>

<template>
  <div class="doctor-picker" role="radiogroup" aria-label="选择医生">
    <label v-for="doctor in options" :key="doctor.id" class="doctor-option"
           :class="{ selected: selected === doctor.id, disabled: !doctor.accepting }">
      <input v-model="selected" type="radio" :name="name" :value="doctor.id" :disabled="!doctor.accepting" />
      <span class="doctor-option-main">
        <span class="doctor-option-name">
          <strong>{{ doctor.name }}</strong><span>{{ doctor.title }}</span>
          <span v-if="doctor.match && doctor.accepting" class="tag tone-processing">推荐科室</span>
        </span>
        <span class="doctor-option-dept">{{ doctor.department }}</span>
        <span v-if="doctor.specialty" class="doctor-option-specialty">擅长：{{ doctor.specialty }}</span>
      </span>
      <span class="doctor-option-side">
        <template v-if="doctor.accepting">
          <span v-if="doctor.rating" class="rating"><Star :size="13" />{{ doctor.rating }}<span class="faint">（{{ doctor.rating_count }}）</span></span>
          <span class="faint tiny">{{ doctor.waiting ? `${doctor.waiting} 人等待中` : '暂无排队' }}</span>
        </template>
        <span v-else class="tag tone-closed">暂停接诊</span>
      </span>
    </label>
    <p v-if="!options.length" class="faint small">暂时没有可选择的医生。</p>
  </div>
</template>
