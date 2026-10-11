<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ArrowLeft, CircleAlert, LoaderCircle, Phone, ShieldCheck, Sparkles, TriangleAlert } from 'lucide-vue-next'
import { api } from '../../api'
import { DURATION_HINTS, URGENCY } from '../../constants'
import { fullDay } from '../../format'
import { navigate, route, setLeaveGuard } from '../../router'
import { toast } from '../../session'
import { loadCases } from '../../store'
import AppLink from '../../components/AppLink.vue'
import DoctorPicker from '../../components/DoctorPicker.vue'
import FilePicker from '../../components/FilePicker.vue'

const steps = ['描述症状', '预问诊', '选择医生', '确认提交']
const step = ref(1)
const form = reactive({ title: '', description: '', duration: '', doctor_id: null, consent_ai: false, consent_share: false })
const files = ref([])
const doctors = ref([])
const profile = ref(null)
const parent = ref(null)
const triage = ref(null)
const answers = ref([])
const checking = ref(false)
const acknowledged = ref(false)
const submitting = ref(false)
const problem = ref('')
let submitted = false

const fingerprint = computed(() => `${form.title.trim()}\u001f${form.description.trim()}\u001f${form.duration.trim()}`)
let triagedFor = ''
watch(fingerprint, value => { if (triage.value && value !== triagedFor) { triage.value = null; answers.value = []; acknowledged.value = false } })
watch(() => form.consent_ai, value => { if (!value && triage.value?.ai) { triage.value = { ...triage.value, ai: null }; answers.value = [] } })

const emergency = computed(() => triage.value?.level === 'emergency')
const crisis = computed(() => triage.value?.flags.some(f => f.level === 'crisis'))
const chosenDoctor = computed(() => doctors.value.find(d => d.id === form.doctor_id))
const stepOneValid = computed(() => form.title.trim().length >= 2 && form.description.trim().length >= 10)
const dirty = computed(() => !submitted && (form.title || form.description || files.value.length))

function leaveGuard() { return !dirty.value || window.confirm('病例还没有提交，确认离开？填写的内容不会保存。') }
function beforeUnload(event) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }

async function runTriage(useAi) {
  checking.value = true
  problem.value = ''
  try {
    const result = await api('/triage', { method: 'POST', body: { title: form.title, description: form.description, duration: form.duration, use_ai: useAi } })
    triage.value = result
    triagedFor = fingerprint.value
    answers.value = (result.ai?.questions || []).map(q => ({ q, a: answers.value.find(item => item.q === q)?.a || '' }))
    if (result.ai?.department && !form.doctor_id) {
      const match = doctors.value.find(d => d.accepting && d.department && (result.ai.department.includes(d.department) || d.department.includes(result.ai.department)))
      if (match) form.doctor_id = match.id
    }
  } catch (err) {
    problem.value = err.message
  } finally {
    checking.value = false
  }
}

function go(target) {
  problem.value = ''
  if (target === 2 && !stepOneValid.value) { problem.value = '请填写病情标题（至少 2 个字）和症状描述（至少 10 个字）'; return }
  if (target === 2 && !triage.value) runTriage(false)
  if (target === 3 && emergency.value && !acknowledged.value) { problem.value = '请先确认你已了解就医提示'; return }
  if (target === 4 && !form.doctor_id) { problem.value = '请选择一位医生'; return }
  step.value = target
  window.scrollTo({ top: 0 })
}

async function submit() {
  if (!form.consent_share) { problem.value = '请勾选同意将资料提供给医生'; return }
  submitting.value = true
  problem.value = ''
  try {
    const created = await api('/cases', {
      method: 'POST',
      form: {
        title: form.title.trim(), description: form.description.trim(), duration: form.duration.trim(),
        doctor_id: form.doctor_id, consent_share: true, consent_ai: form.consent_ai,
        triage_id: triage.value?.id, parent_id: parent.value?.id,
        answers: JSON.stringify(answers.value.filter(item => item.a.trim())), attachments: files.value,
      },
    })
    submitted = true
    loadCases()
    toast('病例已提交，医生接诊后会通知你')
    navigate(`/cases/${created.id}`, { replace: true })
  } catch (err) {
    problem.value = err.message
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  setLeaveGuard(leaveGuard)
  window.addEventListener('beforeunload', beforeUnload)
  try {
    const [team, me] = await Promise.all([api('/doctors'), api('/profile')])
    doctors.value = team
    profile.value = me
    if (route.query.doctor) form.doctor_id = Number(route.query.doctor)
    if (route.query.parent) {
      parent.value = await api(`/cases/${route.query.parent}`)
      form.title = `复诊：${parent.value.title}`.slice(0, 100)
      if (team.find(d => d.id === parent.value.doctor.id && d.accepting)) form.doctor_id = parent.value.doctor.id
    }
  } catch (err) { problem.value = err.message }
})
onUnmounted(() => { setLeaveGuard(null); window.removeEventListener('beforeunload', beforeUnload) })
</script>

<template>
  <div class="page page-narrow new-case">
    <AppLink :to="parent ? `/cases/${parent.id}` : '/'" class="back-link"><ArrowLeft :size="16" />{{ parent ? '返回原病例' : '返回首页' }}</AppLink>
    <header class="page-head">
      <div><h1 class="title-doc page-title">{{ parent ? '发起复诊' : '描述新的症状' }}</h1></div>
    </header>

    <ol class="stepper" aria-label="提交步骤">
      <li v-for="(label, index) in steps" :key="label" :class="{ done: step > index + 1, current: step === index + 1 }"
          :aria-current="step === index + 1 ? 'step' : undefined"><span>{{ index + 1 }}</span>{{ label }}</li>
    </ol>

    <div v-if="profile && !profile.complete" class="notice notice-block">
      <CircleAlert :size="20" />
      <span><strong>请先完善健康档案</strong><span>医生需要你的身份证号、过敏史和当前用药来评估病情。</span></span>
      <AppLink to="/me?setup=1" class="btn btn-primary btn-sm">去完善</AppLink>
    </div>

    <template v-else>
      <!-- Step 1 -->
      <section v-if="step === 1" class="step-body">
        <div v-if="parent" class="parent-context">
          <span class="faint small">复诊病例</span>
          <strong>{{ parent.title }}</strong>
          <span class="small muted">{{ parent.number }}，{{ parent.doctor.name }}于 {{ fullDay(parent.published_at) }} 发布报告</span>
        </div>
        <label class="field">
          <span class="label">一句话概括</span>
          <input v-model="form.title" class="input" maxlength="100" placeholder="例如：反复咳嗽伴咽痛" />
        </label>
        <label class="field">
          <span class="label">详细描述</span>
          <textarea v-model="form.description" class="textarea" rows="7" maxlength="15000"
                    :placeholder="parent ? '和上次相比有什么变化？按建议处理后效果如何？有没有新的症状？' : '哪里不舒服？从什么时候开始？程度如何、有没有加重或缓解？已经做过哪些检查、用过什么药？'" />
          <span class="hint">写得越具体，医生判断越准确。{{ form.description.length }} / 15000</span>
        </label>
        <div class="field">
          <span class="label" id="duration-label">持续多久<span class="optional">选填</span></span>
          <div class="chips" role="group" aria-labelledby="duration-label">
            <button v-for="hint in DURATION_HINTS" :key="hint" type="button" class="chip" :class="{ selected: form.duration === hint }" @click="form.duration = hint">{{ hint }}</button>
          </div>
          <input v-model="form.duration" class="input" maxlength="100" placeholder="也可以直接填写，例如：5 天" aria-labelledby="duration-label" />
        </div>
      </section>

      <!-- Step 2 -->
      <section v-else-if="step === 2" class="step-body">
        <p class="muted">提交前先检查描述中是否有需要立即就医的情况。</p>

        <div class="ai-optin">
          <label class="switch">
            <input v-model="form.consent_ai" type="checkbox" />
            <span class="track"></span>
            <span><strong>使用 AI 预问诊</strong></span>
          </label>
          <p class="small muted">AI 会提出几个补充问题并建议就诊科室，医生也可以用它起草报告。你的描述、附件、年龄、性别、过敏史和用药会发送给第三方模型服务；姓名、手机号和身份证号不会发送。不使用也可以正常提交。</p>
          <button v-if="form.consent_ai && !triage?.ai" class="btn btn-secondary btn-sm" :disabled="checking" @click="runTriage(true)">
            <LoaderCircle v-if="checking" class="spin" :size="16" /><Sparkles v-else :size="16" />{{ checking ? 'AI 正在分析…' : '让 AI 提问' }}
          </button>
        </div>

        <div v-if="checking && !triage" class="loading"><LoaderCircle class="spin" :size="20" /></div>
        <template v-if="triage">
          <div v-if="crisis" class="alert alert-danger" role="alert">
            <h2>你不必独自面对</h2>
            <p>如果你有伤害自己的想法，请现在就拨打心理援助热线，或联系身边信任的人陪着你。</p>
            <div class="alert-actions">
              <a class="btn btn-danger" href="tel:12356"><Phone :size="16" />拨打 12356</a>
              <a class="btn btn-danger" href="tel:120"><Phone :size="16" />拨打 120</a>
            </div>
          </div>
          <div v-else-if="emergency" class="alert alert-danger" role="alert">
            <h2><TriangleAlert :size="20" />这些情况可能需要立即就医</h2>
            <ul><li v-for="flag in triage.flags.filter(f => f.level !== 'urgent')" :key="flag.label"><strong>{{ flag.label }}</strong>：{{ flag.advice }}</li></ul>
            <p v-if="triage.ai?.red_flags?.length" class="small">AI 还提示：{{ triage.ai.red_flags.join('、') }}</p>
            <div class="alert-actions"><a class="btn btn-danger" href="tel:120"><Phone :size="16" />拨打 120</a></div>
          </div>
          <div v-else-if="triage.level === 'urgent'" class="alert alert-warning">
            <h2>建议尽快处理</h2>
            <ul><li v-for="flag in triage.flags" :key="flag.label"><strong>{{ flag.label }}</strong>：{{ flag.advice }}</li></ul>
            <p v-if="!triage.flags.length && triage.ai?.patient_advice">{{ triage.ai.patient_advice }}</p>
            <p class="small">你的病例会被标记为“尽快”，医生会优先处理。</p>
          </div>
          <div v-else class="alert alert-calm">
            <ShieldCheck :size="20" />
            <p>描述中没有发现需要立即就医的危险信号。如果症状突然加重，请直接前往医院。</p>
          </div>
          <label v-if="emergency" class="check ack"><input v-model="acknowledged" type="checkbox" />我已了解，仍要继续在线咨询（线上咨询不会耽误我先去就医）</label>

          <div v-if="triage.ai" class="ai-result">
            <p class="ai-label"><Sparkles :size="16" />AI 预问诊<span v-if="triage.ai.department">建议科室：<strong>{{ triage.ai.department }}</strong></span></p>
            <p v-if="triage.ai.patient_advice && triage.level !== 'urgent'" class="muted">{{ triage.ai.patient_advice }}</p>
            <div v-if="answers.length" class="questions">
              <p class="small muted">回答下面的问题能帮医生更快判断，不知道的可以不填。</p>
              <label v-for="item in answers" :key="item.q" class="field">
                <span class="label">{{ item.q }}</span>
                <textarea v-model="item.a" class="textarea" rows="2" maxlength="1000" />
              </label>
            </div>
          </div>
          <p v-else-if="triage.ai_error" class="hint">{{ triage.ai_error }}</p>
        </template>
      </section>

      <!-- Step 3 -->
      <section v-else-if="step === 3" class="step-body">
        <div class="field">
          <span class="label">选择医生</span>
          <DoctorPicker v-model="form.doctor_id" :doctors="doctors" :suggested="triage?.ai?.department || ''" />
        </div>
        <div class="field">
          <span class="label">检查报告或照片<span class="optional">选填</span></span>
          <FilePicker v-model="files" />
        </div>
      </section>

      <!-- Step 4 -->
      <section v-else class="step-body">
        <dl class="review">
          <div><dt>病情</dt><dd><strong>{{ form.title }}</strong><p class="prewrap muted">{{ form.description }}</p></dd></div>
          <div v-if="form.duration"><dt>持续时间</dt><dd>{{ form.duration }}</dd></div>
          <div v-if="answers.some(item => item.a.trim())"><dt>补充回答</dt>
            <dd><p v-for="item in answers.filter(item => item.a.trim())" :key="item.q"><span class="muted">{{ item.q }}</span><br />{{ item.a }}</p></dd></div>
          <div><dt>医生</dt><dd>{{ chosenDoctor?.name }}　{{ chosenDoctor?.department }}</dd></div>
          <div><dt>附件</dt><dd>{{ files.length ? `${files.length} 个文件` : '无' }}</dd></div>
          <div><dt>初步分级</dt><dd>{{ URGENCY[triage?.level || 'routine'].label }}<span class="faint small">　{{ URGENCY[triage?.level || 'routine'].hint }}</span></dd></div>
          <div><dt>健康档案</dt><dd>过敏史：{{ profile?.allergies }}；当前用药：{{ profile?.medications }}<br /><AppLink to="/me" class="small">有变化？先更新档案</AppLink></dd></div>
        </dl>
        <div class="consents">
          <label class="check"><input v-model="form.consent_share" type="checkbox" />我同意将本次描述、附件和健康档案提供给所选医生，用于诊疗评估。（必选）</label>
          <label class="check"><input v-model="form.consent_ai" type="checkbox" />我同意第三方 AI 服务处理本病例资料，用于预问诊和医生的报告草稿；不含姓名、手机号和身份证号。（可选）</label>
        </div>
      </section>

      <p v-if="problem" class="form-error" role="alert"><CircleAlert :size="16" />{{ problem }}</p>

      <footer class="step-actions">
        <button v-if="step > 1" class="btn btn-secondary" :disabled="submitting" @click="go(step - 1)">上一步</button>
        <button v-if="step < 4" class="btn btn-primary" :disabled="checking" @click="go(step + 1)">下一步：{{ steps[step] }}</button>
        <button v-else class="btn btn-primary" :disabled="submitting" @click="submit">
          <LoaderCircle v-if="submitting" class="spin" :size="18" />提交给{{ chosenDoctor?.name || '医生' }}
        </button>
      </footer>
    </template>
  </div>
</template>
