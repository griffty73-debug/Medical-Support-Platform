<script setup>
import { onMounted, ref } from 'vue'
import { LoaderCircle, Star, Stethoscope } from 'lucide-vue-next'
import { api } from '../../api'
import { toast } from '../../session'
import AppLink from '../../components/AppLink.vue'
import EmptyState from '../../components/EmptyState.vue'

const doctors = ref(null)
onMounted(async () => {
  try { doctors.value = await api('/doctors') } catch (err) { toast(err.message, 'error'); doctors.value = [] }
})
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div><h1 class="title-doc page-title">医生</h1><p>每位医生都经过平台核验。暂停接诊的医生暂时不能选择。</p></div>
    </header>
    <div v-if="!doctors" class="loading"><LoaderCircle class="spin" :size="20" /></div>
    <EmptyState v-else-if="!doctors.length" :icon="Stethoscope" title="暂时没有医生" text="平台正在邀请医生加入。" />
    <ul v-else class="directory">
      <li v-for="doctor in doctors" :key="doctor.id" :class="{ paused: !doctor.accepting }">
        <span class="directory-initial" aria-hidden="true">{{ doctor.name.slice(0, 1) }}</span>
        <div class="directory-main">
          <h2><span class="title-doc">{{ doctor.name }}</span><span class="muted small">{{ doctor.title }}</span></h2>
          <p class="muted">{{ doctor.department }}</p>
          <p v-if="doctor.specialty" class="small">擅长：{{ doctor.specialty }}</p>
          <p class="directory-stats small">
            <span v-if="doctor.rating" class="rating"><Star :size="13" />{{ doctor.rating }}<span class="faint">（{{ doctor.rating_count }} 条评价）</span></span>
            <span class="faint">{{ doctor.accepting ? (doctor.waiting ? `${doctor.waiting} 人等待接诊` : '目前无需排队') : '暂停接诊' }}</span>
          </p>
        </div>
        <AppLink v-if="doctor.accepting" :to="`/cases/new?doctor=${doctor.id}`" class="btn btn-secondary">向{{ doctor.name }}咨询</AppLink>
      </li>
    </ul>
  </div>
</template>
