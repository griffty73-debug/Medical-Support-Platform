<script setup>
import { computed, onMounted } from 'vue'
import { CircleAlert, CircleCheck, LoaderCircle, X } from 'lucide-vue-next'
import { isDoctor } from './api'
import { resolve, route } from './router'
import { boot, session } from './session'
import AppShell from './components/AppShell.vue'
import AuthView from './views/AuthView.vue'
import NotFound from './views/NotFound.vue'
import PatientHome from './views/patient/HomeView.vue'
import PatientCases from './views/patient/CasesView.vue'
import NewCase from './views/patient/NewCaseView.vue'
import PatientCase from './views/patient/CaseView.vue'
import Doctors from './views/patient/DoctorsView.vue'
import Profile from './views/patient/ProfileView.vue'
import Queue from './views/doctor/QueueView.vue'
import DoctorCases from './views/doctor/CasesView.vue'
import Followups from './views/doctor/FollowupsView.vue'
import DoctorCase from './views/doctor/CaseView.vue'
import DoctorSettings from './views/doctor/SettingsView.vue'

const routes = isDoctor
  ? { '/': Queue, '/cases': DoctorCases, '/cases/:id': DoctorCase, '/followups': Followups, '/me': DoctorSettings }
  : { '/': PatientHome, '/cases': PatientCases, '/cases/new': NewCase, '/cases/:id': PatientCase, '/doctors': Doctors, '/me': Profile }

const matched = computed(() => resolve(routes, route.path) || { component: NotFound, params: {} })

onMounted(boot)
</script>

<template>
  <div v-if="session.booting" class="boot" role="status"><LoaderCircle class="spin" :size="24" /><span>正在打开医疗平台</span></div>
  <AuthView v-else-if="!session.user" />
  <AppShell v-else>
    <component :is="matched.component" v-bind="matched.params" :key="route.path" />
  </AppShell>
  <Transition name="toast">
    <div v-if="session.toast" :key="session.toast.id" class="toast" :class="session.toast.type" role="status" aria-live="polite">
      <CircleAlert v-if="session.toast.type === 'error'" :size="18" /><CircleCheck v-else :size="18" />
      <span>{{ session.toast.message }}</span>
      <button class="icon-btn" aria-label="关闭提示" @click="session.toast = null"><X :size="16" /></button>
    </div>
  </Transition>
</template>
