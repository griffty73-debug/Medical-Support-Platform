<script setup>
import { ref } from 'vue'
import { LoaderCircle } from 'lucide-vue-next'
import { api } from '../../api'
import { session, toast } from '../../session'
import SecuritySettings from '../../components/SecuritySettings.vue'

const specialty = ref(session.user.specialty || '')
const busy = ref(false)

async function save(changes, message) {
  busy.value = true
  try {
    session.user = await api('/account/doctor', { method: 'PUT', body: changes })
    toast(message)
  } catch (err) { toast(err.message, 'error') }
  finally { busy.value = false }
}
</script>

<template>
  <div class="page page-narrow">
    <header class="page-head">
      <div><h1 class="title-doc page-title">设置</h1><p>{{ session.user.name }}　{{ session.user.title }}　{{ session.user.department }}</p></div>
    </header>

    <section class="settings-section">
      <h2 class="section-title">接诊</h2>
      <label class="switch">
        <input type="checkbox" :checked="session.user.accepting" :disabled="busy"
               @change="save({ accepting: $event.target.checked }, $event.target.checked ? '已恢复接诊' : '已暂停接诊')" />
        <span class="track"></span>
        <span>{{ session.user.accepting ? '正在接诊：患者可以向你提交新病例' : '已暂停接诊：患者暂时不能选择你' }}</span>
      </label>
      <label class="field">
        <span class="label">擅长领域</span>
        <textarea v-model="specialty" class="textarea" rows="3" maxlength="500" placeholder="患者选择医生时会看到，例如：慢性咳嗽、哮喘、过敏性鼻炎" />
      </label>
      <div><button class="btn btn-secondary" :disabled="busy || specialty === (session.user.specialty || '')" @click="save({ specialty }, '擅长领域已更新')">
        <LoaderCircle v-if="busy" class="spin" :size="16" />保存</button></div>
      <p class="hint">姓名、职称和科室由平台管理员核验后维护，如需修改请联系管理员。</p>
    </section>

    <SecuritySettings />
  </div>
</template>
