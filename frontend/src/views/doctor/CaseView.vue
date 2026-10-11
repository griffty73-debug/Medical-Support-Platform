<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ArrowDownToLine, ArrowLeft, Check, CircleAlert, LoaderCircle, PenLine, Sparkles, Stethoscope } from 'lucide-vue-next'
import { api, download } from '../../api'
import { HISTORY_ACTIONS, REPORT_FIELDS, URGENCY, VISIT_FULL } from '../../constants'
import { dateTime, elapsed, fullDay, untilText } from '../../format'
import { navigate, route } from '../../router'
import { session, toast } from '../../session'
import { loadCases } from '../../store'
import AppDialog from '../../components/AppDialog.vue'
import AppLink from '../../components/AppLink.vue'
import AttachmentList from '../../components/AttachmentList.vue'
import CaseTimeline from '../../components/CaseTimeline.vue'
import DoctorPicker from '../../components/DoctorPicker.vue'
import HealthFacts from '../../components/HealthFacts.vue'
import MessageThread from '../../components/MessageThread.vue'
import ReportEditor from '../../components/ReportEditor.vue'
import ReportPaper from '../../components/ReportPaper.vue'
import StarRating from '../../components/StarRating.vue'
import StatusTag from '../../components/StatusTag.vue'
import UrgencyTag from '../../components/UrgencyTag.vue'

const props = defineProps({ id: { type: String, required: true } })
const record = ref(null)
const problem = ref('')
const tab = ref(route.query.tab || 'case')
const busy = ref(false)
const dialog = ref(null)
const input = ref({ reason: '', message: '', doctor: null, urgency: null })
const doctors = ref([])
const revealed = ref('')
const history = ref(null)
const amending = ref(false)
const editor = ref(null)

const can = action => record.value?.actions.includes(action)
const triage = computed(() => record.value?.triage || {})

async function load() {
  if (editor.value?.dirty) return
  try { record.value = await api(`/cases/${props.id}`); problem.value = '' }
  catch (err) { problem.value = err.message }
}

function open(name) {
  input.value = { reason: '', message: '', doctor: null, urgency: record.value.urgency }
  dialog.value = name
  if (name === 'transfer') api('/doctors').then(list => { doctors.value = list }).catch(err => toast(err.message, 'error'))
}

async function act(path, body, message) {
  busy.value = true
  try {
    const result = await api(`/cases/${props.id}/${path}`, { method: 'POST', body })
    dialog.value = null
    loadCases()
    toast(message)
    if (result.transferred) { navigate('/', { replace: true }); return }
    record.value = result
  } catch (err) { toast(err.message, 'error') }
  finally { busy.value = false }
}

async function reveal() {
  try { revealed.value = (await api(`/cases/${props.id}/reveal-id`, { method: 'POST' })).national_id }
  catch (err) { toast(err.message, 'error') }
}

async function showRecords() {
  tab.value = 'records'
  history.value = await api(`/cases/${props.id}/report/history`).catch(() => [])
}

async function getPdf() {
  try { await download(`/cases/${props.id}/report/pdf`, `${record.value.number}.pdf`) }
  catch (err) { toast(err.message, 'error') }
}

function updated(next) {
  record.value = next
  amending.value = false
  history.value = null
  loadCases()
}

let timer
onMounted(() => { load(); timer = setInterval(() => { if (!document.hidden && !busy.value) load() }, 20000) })
onUnmounted(() => clearInterval(timer))
watch(() => session.activity, load)
</script>

<template>
  <div class="page doctor-case">
    <AppLink to="/" class="back-link"><ArrowLeft :size="16" />接诊队列</AppLink>
    <p v-if="problem && !record" class="form-error"><CircleAlert :size="16" />{{ problem }}</p>
    <div v-else-if="!record" class="loading"><LoaderCircle class="spin" :size="20" /></div>

    <template v-else>
      <header class="case-head doctor-head">
        <div class="doctor-head-main">
          <p class="case-head-meta">
            <span>{{ record.number }}</span>
            <span v-if="record.kind === 'followup'" class="tag tone-closed">复诊</span>
            <UrgencyTag :level="record.urgency" always />
            <StatusTag :status="record.status" />
            <button v-if="can('set_urgency')" class="link-btn tiny" @click="open('urgency')">调整分级</button>
          </p>
          <h1 class="title-doc page-title">{{ record.title }}</h1>
          <p class="patient-line">
            <strong>{{ record.profile.name }}</strong><span>{{ record.profile.gender }}，{{ record.profile.age }} 岁</span>
            <span class="faint">提交于 {{ dateTime(record.created_at) }}</span>
            <span v-if="record.status === 'pending'" :class="record.overdue ? 'text-danger' : 'faint'">
              {{ record.overdue ? `已超过响应时限，等待 ${elapsed(record.created_at)}` : `需在 ${untilText(record.due_at)}接诊` }}
            </span>
          </p>
        </div>
        <div class="head-actions">
          <button v-if="can('accept')" class="btn btn-primary" :disabled="busy" @click="act('accept', {}, '已接诊，患者会收到通知')"><Check :size="18" />接诊</button>
          <button v-if="can('request_info')" class="btn btn-secondary" @click="open('request_info')">请患者补充</button>
          <button v-if="can('resume')" class="btn btn-secondary" :disabled="busy" @click="act('resume', {}, '已结束等待，可以继续评估')">结束等待</button>
          <button v-if="can('transfer')" class="btn btn-quiet" @click="open('transfer')">转诊</button>
          <button v-if="can('decline')" class="btn btn-quiet" @click="open('decline')">退回</button>
          <button v-if="record.status === 'completed'" class="btn btn-secondary" @click="getPdf"><ArrowDownToLine :size="16" />下载 PDF</button>
          <button v-if="can('amend') && !amending" class="btn btn-secondary" @click="amending = true"><PenLine :size="16" />更正报告</button>
        </div>
      </header>

      <div v-if="record.status === 'declined' || record.status === 'cancelled'" class="next tone-closed">
        <div><h2>{{ record.status === 'declined' ? '你已退回这份病例' : '患者已撤回这份病例' }}</h2>
          <p v-if="record.status_reason">原因：{{ record.status_reason }}</p></div>
      </div>

      <div class="workbench">
        <section class="workbench-info">
          <nav class="tabs" aria-label="病例内容">
            <button role="tab" :aria-selected="tab === 'case'" @click="tab = 'case'">病情</button>
            <button role="tab" :aria-selected="tab === 'messages'" @click="tab = 'messages'">沟通<span v-if="record.unread" class="count">{{ record.unread }}</span></button>
            <button role="tab" :aria-selected="tab === 'records'" @click="showRecords">记录</button>
          </nav>

          <div v-if="tab === 'case'" class="info-stack">
            <section v-if="triage.flags.length || triage.ai_summary" class="info-block triage-block">
              <ul v-if="triage.flags.length" class="flag-list">
                <li v-for="flag in triage.flags" :key="flag.label" :class="`flag-${flag.level}`"><strong>{{ flag.label }}</strong><span>描述中提到“{{ flag.evidence }}”</span></li>
              </ul>
              <div v-if="triage.ai_summary" class="ai-summary">
                <p class="ai-label"><Sparkles :size="15" />AI 预问诊摘要<span class="faint">仅供参考</span></p>
                <p class="prewrap">{{ triage.ai_summary }}</p>
                <p v-if="triage.department || triage.ai_red_flags?.length" class="small muted">
                  <template v-if="triage.department">建议科室：{{ triage.department }}　</template>
                  <template v-if="triage.ai_red_flags?.length">关注：{{ triage.ai_red_flags.join('、') }}</template>
                </p>
              </div>
            </section>

            <section class="info-block">
              <h2 class="block-title">病情描述</h2>
              <p class="prewrap description">{{ record.description }}</p>
              <dl v-if="record.duration || record.answers.length" class="qa">
                <div v-if="record.duration"><dt>持续时间</dt><dd>{{ record.duration }}</dd></div>
                <div v-for="item in record.answers" :key="item.q"><dt>{{ item.q }}</dt><dd>{{ item.a }}</dd></div>
              </dl>
            </section>

            <section v-if="record.parent" class="info-block">
              <h2 class="block-title">上次就诊</h2>
              <p class="small muted"><AppLink :to="`/cases/${record.parent.id}`">{{ record.parent.number }} {{ record.parent.title }}</AppLink>　{{ fullDay(record.parent.published_at) }}</p>
              <dl v-if="record.parent.report" class="qa">
                <div><dt>初步评估</dt><dd class="prewrap">{{ record.parent.report.summary }}</dd></div>
                <div><dt>处理建议</dt><dd class="prewrap">{{ record.parent.report.treatment }}</dd></div>
              </dl>
            </section>

            <section class="info-block">
              <h2 class="block-title">健康档案<span class="faint tiny">提交时的记录</span></h2>
              <HealthFacts :profile="record.profile" :revealed="revealed" can-reveal @reveal="reveal" @hide="revealed = ''" />
            </section>

            <section class="info-block">
              <h2 class="block-title">附件<span class="faint tiny">{{ record.attachments.length }} 个</span></h2>
              <AttachmentList v-if="record.attachments.length" :items="record.attachments" show-source />
              <p v-else class="faint small">患者没有上传附件</p>
            </section>
          </div>

          <MessageThread v-else-if="tab === 'messages'" :case-id="record.id" :can-send="can('message')" :until="record.message_until"
                         :closed-text="record.status === 'pending' ? '接诊后可以和患者沟通。' : '沟通期已结束。'" @sent="load" />

          <div v-else class="info-stack">
            <CaseTimeline :events="record.events" />
            <section v-if="history?.length" class="info-block">
              <h2 class="block-title">报告修改记录<span class="faint tiny">每次保存、AI 生成、发布和更正都会留档</span></h2>
              <details v-for="item in history" :key="item.version" class="version">
                <summary><strong>修改 #{{ item.version }}</strong><span>{{ HISTORY_ACTIONS[item.action] }}</span><time class="faint">{{ dateTime(item.created_at) }}</time></summary>
                <p v-if="item.reason" class="small muted">更正原因：{{ item.reason }}</p>
                <div v-for="field in REPORT_FIELDS" :key="field.key"><h3 class="label">{{ field.label }}</h3><p class="prewrap small">{{ item.content[field.key] || '未填写' }}</p></div>
                <p v-if="item.content.visit" class="small"><strong>线下就诊：</strong>{{ VISIT_FULL[item.content.visit] }}</p>
              </details>
            </section>
          </div>
        </section>

        <section class="workbench-report">
          <div v-if="record.status === 'pending'" class="report-placeholder">
            <Stethoscope :size="28" />
            <h2>接诊后开始撰写报告</h2>
            <p>先查看病情和档案。不适合由你处理时，可以转诊给其他医生或退回并说明原因。</p>
            <button v-if="can('accept')" class="btn btn-primary" :disabled="busy" @click="act('accept', {}, '已接诊，患者会收到通知')"><Check :size="18" />接诊</button>
          </div>
          <ReportEditor v-else-if="can('edit_draft') || amending" ref="editor" :record="record" :amend="amending" @updated="updated" @cancel="amending = false" />
          <template v-else-if="record.report">
            <ReportPaper :record="record" :report="record.report" />
            <p v-if="record.ai_edit_ratio !== null && record.ai_edit_ratio !== undefined" class="hint report-meta">
              <Sparkles :size="13" />由 AI 草稿起草，发布前修改了 {{ Math.round(record.ai_edit_ratio * 100) }}% 的内容
            </p>
            <div v-if="record.rating" class="after-card">
              <div><h3>患者评价</h3><StarRating :model-value="record.rating" readonly /><p v-if="record.review" class="small muted">{{ record.review }}</p></div>
            </div>
          </template>
          <div v-else class="report-placeholder"><p class="muted">这份病例没有发布报告。</p></div>
        </section>
      </div>
    </template>

    <AppDialog v-if="dialog === 'decline'" title="退回病例" :busy="busy" @close="dialog = null">
      <p class="muted small">患者会看到退回原因，并可以改投其他医生。</p>
      <label class="field"><span class="label">退回原因</span>
        <textarea v-model="input.reason" class="textarea" rows="3" maxlength="500" placeholder="例如：症状需要皮肤科医生面诊判断，建议改投皮肤科" /></label>
      <template #footer>
        <button class="btn btn-secondary" :disabled="busy" @click="dialog = null">取消</button>
        <button class="btn btn-danger" :disabled="busy || input.reason.trim().length < 4" @click="act('decline', { reason: input.reason }, '已退回，患者会收到通知')">退回病例</button>
      </template>
    </AppDialog>

    <AppDialog v-if="dialog === 'transfer'" title="转诊给其他医生" wide :busy="busy" @close="dialog = null">
      <p class="muted small">病例会回到“待接诊”交给对方，你的草稿不会转过去，转出后你将无法再查看。</p>
      <DoctorPicker v-model="input.doctor" :doctors="doctors" :exclude="[session.user.id]" name="transfer" />
      <label class="field"><span class="label">转诊原因</span>
        <input v-model="input.reason" class="input" maxlength="500" placeholder="对方和患者都会看到" /></label>
      <template #footer>
        <button class="btn btn-secondary" :disabled="busy" @click="dialog = null">取消</button>
        <button class="btn btn-primary" :disabled="busy || !input.doctor || input.reason.trim().length < 4"
                @click="act('transfer', { doctor_id: input.doctor, reason: input.reason }, '已转诊')">确认转诊</button>
      </template>
    </AppDialog>

    <AppDialog v-if="dialog === 'request_info'" title="请患者补充资料" :busy="busy" @close="dialog = null">
      <p class="muted small">病例会进入“待补充资料”，患者补充后自动回到评估中。期间可以继续写草稿。</p>
      <label class="field"><span class="label">需要补充什么</span>
        <textarea v-model="input.message" class="textarea" rows="4" maxlength="2000" placeholder="例如：请上传最近一次血常规报告，并说明发热时的最高体温" /></label>
      <template #footer>
        <button class="btn btn-secondary" :disabled="busy" @click="dialog = null">取消</button>
        <button class="btn btn-primary" :disabled="busy || input.message.trim().length < 5" @click="act('request-info', { message: input.message }, '已发送，等待患者补充')">发送请求</button>
      </template>
    </AppDialog>

    <AppDialog v-if="dialog === 'urgency'" title="调整紧急程度" :busy="busy" @close="dialog = null">
      <div class="chips" role="radiogroup" aria-label="紧急程度">
        <button v-for="(meta, level) in URGENCY" :key="level" class="chip" role="radio" :aria-checked="input.urgency === level" @click="input.urgency = level">
          {{ meta.label }}<span class="faint">{{ meta.hint }}</span></button>
      </div>
      <template #footer>
        <button class="btn btn-secondary" :disabled="busy" @click="dialog = null">取消</button>
        <button class="btn btn-primary" :disabled="busy || input.urgency === record.urgency" @click="act('urgency', { urgency: input.urgency }, '紧急程度已调整')">保存</button>
      </template>
    </AppDialog>
  </div>
</template>
