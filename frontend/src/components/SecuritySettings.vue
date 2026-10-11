<script setup>
import { reactive, ref } from 'vue'
import { CircleAlert, LoaderCircle, LogOut } from 'lucide-vue-next'
import { api, setToken } from '../api'
import { dateTime } from '../format'
import { canLeave } from '../router'
import { session, signOut, toast } from '../session'
import { resetCases } from '../store'

const form = reactive({ current: '', next: '', confirm: '' })
const busy = ref(false)
const problem = ref('')

async function change() {
  problem.value = ''
  if (form.next !== form.confirm) { problem.value = '两次输入的新密码不一致'; return }
  busy.value = true
  try {
    const result = await api('/auth/password', { method: 'POST', body: { current_password: form.current, new_password: form.next } })
    setToken(result.token)
    session.user = result.user
    Object.assign(form, { current: '', next: '', confirm: '' })
    toast('密码已修改，其他设备需要重新登录')
  } catch (err) { problem.value = err.message }
  finally { busy.value = false }
}

async function logoutOthers() {
  try {
    const result = await api('/auth/logout-others', { method: 'POST' })
    setToken(result.token)
    toast('已退出其他设备上的登录')
  } catch (err) { toast(err.message, 'error') }
}

function logout() {
  if (!canLeave()) return
  resetCases()
  signOut()
}
</script>

<template>
  <section class="settings-section" aria-labelledby="security-title">
    <h2 id="security-title" class="section-title">账号与安全</h2>
    <dl class="account-facts">
      <div><dt>登录手机号</dt><dd>{{ session.user.phone }}</dd></div>
      <div v-if="session.user.password_changed_at"><dt>上次修改密码</dt><dd>{{ dateTime(session.user.password_changed_at) }}</dd></div>
    </dl>
    <form class="password-form" @submit.prevent="change">
      <h3 class="label">修改密码</h3>
      <label class="field"><span class="label">当前密码</span><input v-model="form.current" class="input" type="password" autocomplete="current-password" required /></label>
      <label class="field"><span class="label">新密码</span><input v-model="form.next" class="input" type="password" autocomplete="new-password" required placeholder="至少 8 位，包含字母和数字" /></label>
      <label class="field"><span class="label">再次输入新密码</span><input v-model="form.confirm" class="input" type="password" autocomplete="new-password" required /></label>
      <p v-if="problem" class="form-error" role="alert"><CircleAlert :size="16" />{{ problem }}</p>
      <div><button class="btn btn-secondary" :disabled="busy || !form.current || !form.next"><LoaderCircle v-if="busy" class="spin" :size="16" />修改密码</button></div>
    </form>
    <div class="session-actions">
      <button class="btn btn-quiet" @click="logoutOthers">退出其他设备</button>
      <button class="btn btn-quiet" @click="logout"><LogOut :size="16" />退出登录</button>
    </div>
  </section>
</template>
