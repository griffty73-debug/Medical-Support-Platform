<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ArrowDownToLine, ArrowLeft, CalendarClock, CircleAlert, LoaderCircle, ShieldCheck } from 'lucide-vue-next'
import { api, download } from '../../api'
import { URGENCY } from '../../constants'
import { dateTime, fullDay, untilText } from '../../format'
import { session, toast } from '../../session'
import { loadCases } from '../../store'
import AppDialog from '../../components/AppDialog.vue'
import AppLink from '../../components/AppLink.vue'
import AttachmentList from '../../components/AttachmentList.vue'
import CasePath from '../../components/CasePath.vue'
import CaseTimeline from '../../components/CaseTimeline.vue'
import DoctorPicker from '../../components/DoctorPicker.vue'
import FilePicker from '../../components/FilePicker.vue'
import MessageThread from '../../components/MessageThread.vue'
import ReportPaper from '../../components/ReportPaper.vue'
import StarRating from '../../components/StarRating.vue'
import StatusTag from '../../components/StatusTag.vue'

const props = defineProps({ id: { type: String, required: true } })
const record = ref(null)
const problem = ref('')
const tab = ref('messages')
const busy = ref(false)
const accessLog = ref(null)
const supplement = ref({ body: '', files: [] })
const review = ref({ rating: 0, text: '' })
const dialog = ref(null)
const doctors = ref([])
const reassignTo = ref(null)
const cancelReason = ref('')

const can = action => record.value?.actions.includes(action)
const request = computed(() => [...(record.value?.events || [])].reverse().find(e => e.kind === 'info_requested'))

async function load() {
  try { record.value = await api(`/cases/${props.id}`); problem.value = '' }
  catch (err) { problem.value = err.message }
}

async function act(path, body, message, options = {}) {
  busy.value = true
  try {
    record.value = await api(`/cases/${props.id}/${path}`, { method: 'POST', ...(options.form ? { form: body } : { body }) })
    dialog.value = null
    loadCases()
    toast(message)
    return true
  } catch (err) { toast(err.message, 'error'); return false }
  finally { busy.value = false }
}

async function sendSupplement() {
  const ok = await act('supplement', { body: supplement.value.body.trim(), attachments: supplement.value.files }, '已提交补充资料，医生会继续评估', { form: true })
  if (ok) supplement.value = { body: '', files: [] }
}

async function openReassign() {
  reassignTo.value = null
  dialog.value = 'reassign'
  try { doctors.value = await api('/doctors') } catch (err) { toast(err.message, 'error') }
}

async function loadAccess() {
  tab.value = 'records'
  if (!accessLog.value) accessLog.value = await api(`/cases/${props.id}/access-log`).catch(() => [])
}

async function getPdf() {
  try { await download(`/cases/${props.id}/report/pdf`, `${record.value.number}.pdf`) }
  catch (err) { toast(err.message, 'error') }
}

let timer
onMounted(() => { load(); timer = setInterval(() => { if (!document.hidden && !busy.value) load() }, 20000) })
onUnmounted(() => clearInterval(timer))
watch(() => session.activity, load)
</script>

<template>
  <div class="page case-page">
    <AppLink to="/cases" class="back-link"><ArrowLeft :size="16" />我的病例</AppLink>
    <p v-if="problem && !record" class="form-error"><CircleAlert :size="16" />{{ problem }}</p>
    <div v-else-if="!record" class="loading"><LoaderCircle class="spin" :size="20" /></div>

    <template v-else>
      <header class="case-head">
        <p class="case-head-meta">
          <span>{{ record.number }}</span>
          <span v-if="record.kind === 'followup'" class="tag tone-closed">复诊</span>
          <StatusTag :status="record.status" />
        </p>
        <h1 class="title-doc page-title">{{ record.title }}</h1>
        <p class="muted small">{{ record.doctor.name }}　{{ record.doctor.department }}　提交于 {{ dateTime(record.created_at) }}</p>
      </header>

      <CasePath :record="record" class="case-page-path" />

      <!-- What happens next -->
      <section v-if="record.status === 'pending'" class="next tone-pending">
        <div>
          <h2>等待{{ record.doctor.name }}接诊</h2>
          <p>预计 {{ untilText(record.due_at) }}回应<template v-if="record.urgency !== 'routine'">，你的病例已被标记为“{{ URGENCY[record.urgency].label }}”</template>。接诊前也可以在下方补充情况。</p>
        </div>
        <div class="next-actions">
          <button v-if="can('reassign')" class="btn btn-secondary btn-sm" @click="openReassign">更换医生</button>
          <button v-if="can('cancel')" class="btn btn-quiet btn-sm" @click="dialog = 'cancel'">撤回</button>
        </div>
      </section>

      <section v-else-if="record.status === 'processing'" class="next tone-processing">
        <div><h2>{{ record.doctor.name }}正在评估</h2><p>报告发布后会通知你。有新的情况可以随时在下方告诉医生。</p></div>
        <div class="next-actions"><button v-if="can('cancel')" class="btn btn-quiet btn-sm" @click="dialog = 'cancel'">撤回</button></div>
      </section>

      <section v-else-if="record.status === 'awaiting_info'" class="next tone-awaiting next-form">
        <div>
          <h2>医生请你补充资料</h2>
          <blockquote v-if="request?.detail" class="prewrap">{{ request.detail }}</blockquote>
        </div>
        <form class="supplement" @submit.prevent="sendSupplement">
          <label class="field"><span class="label">补充说明</span>
            <textarea v-model="supplement.body" class="textarea" rows="3" maxlength="2000" placeholder="回答医生的问题，或说明上传的资料" /></label>
          <FilePicker v-model="supplement.files" label="上传医生需要的检查报告或照片" />
          <div class="next-actions">
            <button v-if="can('cancel')" type="button" class="btn btn-quiet btn-sm" @click="dialog = 'cancel'">撤回病例</button>
            <button class="btn btn-primary" :disabled="busy || (!supplement.body.trim() && !supplement.files.length)">
              <LoaderCircle v-if="busy" class="spin" :size="16" />提交补充资料</button>
          </div>
        </form>
      </section>

      <section v-else-if="record.status === 'declined'" class="next tone-closed">
        <div><h2>{{ record.doctor.name }}退回了这份病例</h2><blockquote v-if="record.status_reason" class="prewrap">{{ record.status_reason }}</blockquote>
          <p>可以改投其他医生，病情资料会一并转过去，不需要重新填写。</p></div>
        <div class="next-actions">
          <button v-if="can('reassign')" class="btn btn-primary btn-sm" @click="openReassign">改投其他医生</button>
          <button v-if="can('cancel')" class="btn btn-quiet btn-sm" @click="dialog = 'cancel'">撤回</button>
        </div>
      </section>

      <section v-else-if="record.status === 'cancelled'" class="next tone-closed">
        <div><h2>你已撤回这份病例</h2><p v-if="record.status_reason">原因：{{ record.status_reason }}</p></div>
      </section>

      <!-- Report -->
      <section v-if="record.report && record.status === 'completed'" class="case-report">
        <div class="section-head">
          <h2 class="section-title">诊疗报告</h2>
          <button class="btn btn-secondary btn-sm" @click="getPdf"><ArrowDownToLine :size="16" />下载 PDF</button>
        </div>
        <ReportPaper :record="record" :report="record.report" />

        <div class="after-report">
          <div v-if="record.followup_due" class="after-card">
            <CalendarClock :size="20" />
            <div>
              <h3>随访</h3>
              <p v-if="record.followup_state === 'returned'">你已经发起了复诊。</p>
              <p v-else>建议在 {{ fullDay(record.followup_due) }} 前后复诊。到时候在这里发起，医生能看到这次的报告。</p>
              <AppLink v-if="can('followup')" :to="`/cases/new?parent=${record.id}`" class="btn btn-secondary btn-sm">发起复诊</AppLink>
            </div>
          </div>
          <div v-else-if="can('followup')" class="after-card">
            <CalendarClock :size="20" />
            <div><h3>症状没有好转？</h3><p>可以基于这份病例发起复诊。</p>
              <AppLink :to="`/cases/new?parent=${record.id}`" class="btn btn-secondary btn-sm">发起复诊</AppLink></div>
          </div>
          <div class="after-card">
            <div v-if="can('review')" class="review-form">
              <h3>这次问诊对你有帮助吗？</h3>
              <StarRating v-model="review.rating" />
              <textarea v-model="review.text" class="textarea" rows="2" maxlength="500" placeholder="想对医生说的话（选填）" />
              <button class="btn btn-secondary btn-sm" :disabled="!review.rating || busy" @click="act('review', { rating: review.rating, review: review.text }, '感谢你的评价')">提交评价</button>
            </div>
            <div v-else-if="record.rating">
              <h3>你的评价</h3>
              <StarRating :model-value="record.rating" readonly />
              <p v-if="record.review" class="muted small">{{ record.review }}</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Details -->
      <nav class="tabs" aria-label="病例内容">
        <button :aria-selected="tab === 'messages'" role="tab" @click="tab = 'messages'">与医生沟通<span v-if="record.unread" class="count">{{ record.unread }}</span></button>
        <button :aria-selected="tab === 'details'" role="tab" @click="tab = 'details'">病情资料</button>
        <button :aria-selected="tab === 'records'" role="tab" @click="loadAccess">处理记录</button>
      </nav>

      <MessageThread v-if="tab === 'messages'" :case-id="record.id" :can-send="can('message')" :until="record.message_until"
                     :closed-text="record.status === 'completed' ? '沟通期已结束。如果还有问题，可以发起复诊。' : '这份病例已关闭。'" @sent="load" />

      <section v-else-if="tab === 'details'" class="details">
        <dl class="review">
          <div><dt>描述</dt><dd class="prewrap">{{ record.description }}</dd></div>
          <div v-if="record.duration"><dt>持续时间</dt><dd>{{ record.duration }}</dd></div>
          <div v-for="item in record.answers" :key="item.q"><dt>{{ item.q }}</dt><dd>{{ item.a }}</dd></div>
          <div><dt>初步分级</dt><dd>{{ URGENCY[record.urgency].label }}<span v-if="record.triage.department" class="muted">　建议科室：{{ record.triage.department }}</span></dd></div>
          <div><dt>AI 辅助</dt><dd>{{ record.consent_ai ? '已同意' : '未同意，医生不会使用 AI 处理本病例' }}</dd></div>
        </dl>
        <h3 class="label">附件</h3>
        <AttachmentList v-if="record.attachments.length" :items="record.attachments" show-source />
        <p v-else class="faint small">没有附件</p>
      </section>

      <section v-else class="details">
        <CaseTimeline :events="record.events" />
        <h3 class="label access-title"><ShieldCheck :size="16" />谁查看过我的资料</h3>
        <ul v-if="accessLog?.length" class="access-log">
          <li v-for="(entry, index) in accessLog" :key="index"><span>{{ entry.name }}{{ entry.label }}</span><time class="faint">{{ dateTime(entry.created_at) }}</time></li>
        </ul>
        <p v-else class="faint small">只有你和接诊医生能看到这份病例。医生查看、下载资料都会记录在这里。</p>
      </section>
    </template>

    <AppDialog v-if="dialog === 'cancel'" title="撤回病例" :busy="busy" @close="dialog = null">
      <p class="muted">撤回后医生将不再处理这份病例，此操作无法恢复。</p>
      <label class="field"><span class="label">原因<span class="optional">选填</span></span>
        <input v-model="cancelReason" class="input" maxlength="500" placeholder="例如：已经去医院就诊" /></label>
      <template #footer>
        <button class="btn btn-secondary" :disabled="busy" @click="dialog = null">不撤回</button>
        <button class="btn btn-danger" :disabled="busy" @click="act('cancel', { reason: cancelReason }, '病例已撤回')">撤回病例</button>
      </template>
    </AppDialog>

    <AppDialog v-if="dialog === 'reassign'" title="选择其他医生" wide :busy="busy" @close="dialog = null">
      <p class="muted small">病情描述、附件和沟通记录会转给新医生，{{ record.doctor.name }}将不再能查看这份病例。</p>
      <DoctorPicker v-model="reassignTo" :doctors="doctors" :exclude="[record.doctor.id]" :suggested="record.triage.department || ''" />
      <template #footer>
        <button class="btn btn-secondary" :disabled="busy" @click="dialog = null">取消</button>
        <button class="btn btn-primary" :disabled="busy || !reassignTo" @click="act('reassign', { doctor_id: reassignTo }, '已改投新医生，等待接诊')">确认改投</button>
      </template>
    </AppDialog>
  </div>
</template>
