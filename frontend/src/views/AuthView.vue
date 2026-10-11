<script setup>
import { computed, reactive, ref } from 'vue'
import { CircleAlert, Eye, EyeOff, LoaderCircle } from 'lucide-vue-next'
import { api, isDoctor, portal } from '../api'
import { navigate } from '../router'
import { signIn } from '../session'
import BrandMark from '../components/BrandMark.vue'

const mode = ref('login')
const form = reactive({ name: '', phone: '', password: '' })
const busy = ref(false)
const problem = ref('')
const reveal = ref(false)

const journey = isDoctor
  ? ['接诊', '评估', '审核发布', '随访']
  : ['描述症状', '医生接诊', '查看报告', '按时随访']
const registering = computed(() => mode.value === 'register')

async function submit() {
  busy.value = true
  problem.value = ''
  try {
    const result = await api(`/auth/${mode.value}`, { method: 'POST', body: { ...form, role: portal } })
    form.password = ''
    signIn(result)
    navigate(registering.value ? '/me?setup=1' : '/', { replace: true })
  } catch (err) {
    problem.value = err.message
  } finally {
    busy.value = false
  }
}

function switchMode() {
  mode.value = registering.value ? 'login' : 'register'
  problem.value = ''
}
</script>

<template>
  <div class="auth">
    <section class="auth-intro" aria-label="平台介绍">
      <div class="brand auth-brand"><BrandMark :size="36" /><span>医疗平台<small>{{ isDoctor ? '医生工作台' : '线上问诊与随访' }}</small></span></div>
      <h1 class="title-doc auth-title">{{ isDoctor ? '每一份报告，\n都由你审核签发。' : '把病情讲清楚，\n剩下的交给医生。' }}</h1>
      <ol class="auth-journey" aria-label="使用流程">
        <li v-for="(step, index) in journey" :key="step"><span class="auth-station">{{ index + 1 }}</span>{{ step }}</li>
      </ol>
    </section>

    <section class="auth-panel">
      <form class="auth-form" novalidate @submit.prevent="submit">
        <h2>{{ registering ? '创建账号' : isDoctor ? '医生登录' : '登录' }}</h2>
        <p class="muted small">{{ registering ? '注册后请先完善健康档案，再提交病例。' : isDoctor ? '医生账号由平台管理员开通。' : '使用注册时的手机号登录。' }}</p>
        <label v-if="registering" class="field">
          <span class="label">姓名</span>
          <input v-model="form.name" class="input" required maxlength="50" autocomplete="name" placeholder="与身份证一致" />
        </label>
        <label class="field">
          <span class="label">手机号码</span>
          <input v-model="form.phone" class="input" type="tel" inputmode="numeric" required maxlength="11" autocomplete="username" placeholder="11 位手机号" />
        </label>
        <label class="field">
          <span class="label">密码</span>
          <span class="password">
            <input v-model="form.password" class="input" :type="reveal ? 'text' : 'password'" required maxlength="128"
                   :autocomplete="registering ? 'new-password' : 'current-password'" :placeholder="registering ? '至少 8 位，包含字母和数字' : '输入密码'" />
            <button type="button" class="icon-btn" :aria-label="reveal ? '隐藏密码' : '显示密码'" :title="reveal ? '隐藏密码' : '显示密码'" @click="reveal = !reveal">
              <EyeOff v-if="reveal" :size="18" /><Eye v-else :size="18" />
            </button>
          </span>
        </label>
        <p v-if="problem" class="form-error" role="alert"><CircleAlert :size="16" />{{ problem }}</p>
        <button class="btn btn-primary btn-lg btn-block" :disabled="busy">
          <LoaderCircle v-if="busy" class="spin" :size="18" />{{ registering ? '注册并继续' : '登录' }}
        </button>
        <p v-if="!isDoctor" class="auth-switch small">
          {{ registering ? '已经有账号？' : '第一次使用？' }}
          <button type="button" class="link-btn" @click="switchMode">{{ registering ? '去登录' : '创建账号' }}</button>
        </p>
      </form>
      <p class="auth-safety">线上咨询不能替代急诊。出现胸痛、呼吸困难、意识不清等情况，请立即拨打 120。</p>
    </section>
  </div>
</template>
