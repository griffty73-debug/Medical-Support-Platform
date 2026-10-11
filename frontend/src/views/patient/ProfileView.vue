<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { CircleAlert, Eye, EyeOff, LoaderCircle, ShieldCheck } from 'lucide-vue-next'
import { api } from '../../api'
import { navigate, route } from '../../router'
import { session, toast } from '../../session'
import SecuritySettings from '../../components/SecuritySettings.vue'

const profile = ref(null)
const form = reactive({ name: '', national_id: '', allergies: '', history: '', medications: '' })
const editingId = ref(false)
const revealed = ref('')
const busy = ref(false)
const problem = ref('')
const setup = computed(() => route.query.setup === '1')

function fill(data) {
  profile.value = data
  Object.assign(form, { name: data.name, national_id: '', allergies: data.allergies, history: data.history, medications: data.medications })
  editingId.value = !data.has_national_id
}

async function save() {
  busy.value = true
  problem.value = ''
  try {
    const body = { ...form }
    if (!editingId.value) delete body.national_id
    const data = await api('/profile', { method: 'PUT', body })
    fill(data)
    revealed.value = ''
    session.user.name = data.name
    toast('健康档案已保存')
    if (setup.value) navigate('/')
  } catch (err) { problem.value = err.message }
  finally { busy.value = false }
}

async function reveal() {
  if (revealed.value) { revealed.value = ''; return }
  try { revealed.value = (await api('/profile/reveal-id', { method: 'POST' })).national_id }
  catch (err) { toast(err.message, 'error') }
}

onMounted(async () => {
  try { fill(await api('/profile')) } catch (err) { problem.value = err.message }
})
</script>

<template>
  <div class="page page-narrow">
    <header class="page-head">
      <div>
        <h1 class="title-doc page-title">{{ setup ? '完善健康档案' : '我的' }}</h1>
        <p>{{ setup ? '提交病例前需要这些信息。档案会在每次提交时随病例一起发给医生。' : '健康档案会在每次提交病例时随病例发给医生；修改不会影响已提交的病例。' }}</p>
      </div>
    </header>

    <div v-if="!profile && !problem" class="loading"><LoaderCircle class="spin" :size="20" /></div>
    <form v-else-if="profile" class="settings-section profile-form" @submit.prevent="save">
      <h2 class="section-title">健康档案</h2>
      <div class="form-grid">
        <label class="field"><span class="label">姓名</span><input v-model="form.name" class="input" required maxlength="50" autocomplete="name" /></label>
        <div class="field">
          <label class="label" for="national-id">身份证号</label>
          <input v-if="editingId" id="national-id" v-model="form.national_id" class="input" maxlength="18" autocomplete="off" inputmode="text"
                 placeholder="18 位身份证号码" :required="!profile.has_national_id" />
          <div v-else class="id-display">
            <span class="nowrap">{{ revealed || profile.national_id_masked }}</span>
            <button type="button" class="icon-btn" :aria-label="revealed ? '隐藏' : '显示完整号码'" :title="revealed ? '隐藏' : '显示完整号码'" @click="reveal">
              <EyeOff v-if="revealed" :size="16" /><Eye v-else :size="16" />
            </button>
            <button type="button" class="link-btn small" @click="editingId = true">修改</button>
          </div>
          <span class="hint"><ShieldCheck :size="12" /> 加密保存，医生默认只看到部分号码</span>
        </div>
      </div>
      <div v-if="profile.has_national_id" class="derived">
        <dl>
          <div><dt>性别</dt><dd>{{ profile.gender }}</dd></div>
          <div><dt>年龄</dt><dd>{{ profile.age }} 岁</dd></div>
          <div><dt>出生日期</dt><dd>{{ profile.birth_date }}</dd></div>
        </dl>
        <p class="hint">根据身份证号自动识别，无需填写</p>
      </div>
      <label class="field"><span class="label">过敏史</span>
        <textarea v-model="form.allergies" class="textarea" rows="2" maxlength="3000" required placeholder="药物、食物或其他过敏，例如：青霉素过敏（皮疹）。没有请填“无”" /></label>
      <label class="field"><span class="label">当前用药</span>
        <textarea v-model="form.medications" class="textarea" rows="2" maxlength="3000" required placeholder="正在服用的药物和剂量。没有请填“无”" /></label>
      <label class="field"><span class="label">既往病史<span class="optional">选填</span></span>
        <textarea v-model="form.history" class="textarea" rows="3" maxlength="3000" placeholder="慢性病、手术史、住院史等" /></label>
      <p v-if="problem" class="form-error" role="alert"><CircleAlert :size="16" />{{ problem }}</p>
      <div><button class="btn btn-primary" :disabled="busy"><LoaderCircle v-if="busy" class="spin" :size="16" />保存健康档案</button></div>
    </form>
    <p v-else class="form-error"><CircleAlert :size="16" />{{ problem }}</p>

    <SecuritySettings v-if="!setup" />
  </div>
</template>
