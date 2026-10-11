<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { CircleAlert, LoaderCircle, Save, Sparkles } from 'lucide-vue-next'
import { api } from '../api'
import { FOLLOWUP, REPORT_FIELDS, VISIT, VISIT_FULL } from '../constants'
import { dateTime } from '../format'
import { setLeaveGuard } from '../router'
import { toast } from '../session'
import AppDialog from './AppDialog.vue'
import ReportPaper from './ReportPaper.vue'

const props = defineProps({ record: { type: Object, required: true }, amend: Boolean })
const emit = defineEmits(['updated', 'cancel'])

const blank = () => ({ summary: '', basis: '', treatment: '', advice: '', visit: null, followup_days: null })
const report = reactive(blank())
const view = ref('edit')
const busy = ref(false)
const aiBusy = ref(false)
const confirming = ref(false)
const checked = ref(false)
const reason = ref('')
const savedAt = ref(null)

const source = computed(() => (props.amend ? props.record.report : props.record.draft) || blank())
const normalized = value => JSON.stringify({ ...blank(), ...value, ...Object.fromEntries(REPORT_FIELDS.map(f => [f.key, (value?.[f.key] || '').trim()])) })
const dirty = computed(() => normalized(report) !== normalized(source.value))
const missing = computed(() => [
  ...REPORT_FIELDS.filter(f => !report[f.key].trim()).map(f => f.label),
  ...(report.visit ? [] : ['线下就诊建议']),
  ...(report.followup_days === null ? ['随访安排'] : []),
])
const canPublish = computed(() => props.amend || props.record.actions.includes('publish'))
const canAi = computed(() => !props.amend && props.record.actions.includes('ai_draft'))

function reset() { Object.assign(report, blank(), source.value) }

async function save(quiet = false) {
  if (props.amend) return
  busy.value = true
  try {
    const record = await api(`/cases/${props.record.id}/draft`, { method: 'PUT', body: { version: props.record.report_version, report: { ...report } } })
    savedAt.value = new Date()
    emit('updated', record)
    if (!quiet) toast('草稿已保存')
  } catch (err) { toast(err.message, 'error') }
  finally { busy.value = false }
}

async function generate() {
  if ((dirty.value || REPORT_FIELDS.some(f => report[f.key])) && !window.confirm('AI 草稿会替换当前编辑框中的内容（旧版本保留在修改记录中），确认继续？')) return
  aiBusy.value = true
  try {
    const record = await api(`/cases/${props.record.id}/ai`, { method: 'POST', body: { version: props.record.report_version } })
    emit('updated', record)
    toast('AI 草稿已生成，请逐项核对后再发布')
  } catch (err) { toast(err.message, 'error') }
  finally { aiBusy.value = false }
}

function openConfirm() {
  checked.value = false
  confirming.value = true
}

async function publish() {
  busy.value = true
  try {
    const record = props.amend
      ? await api(`/cases/${props.record.id}/amend`, { method: 'POST', body: { published_version: props.record.published_version, report: { ...report }, reason: reason.value, confirmed: true } })
      : await api(`/cases/${props.record.id}/publish`, { method: 'POST', body: { version: props.record.report_version, report: { ...report }, confirmed: true } })
    confirming.value = false
    emit('updated', record)
    toast(props.amend ? '更正已发布，患者会收到通知' : '报告已发布，患者会收到通知')
  } catch (err) { toast(err.message, 'error') }
  finally { busy.value = false }
}

function keydown(event) {
  if ((event.metaKey || event.ctrlKey) && event.key === 's') { event.preventDefault(); if (dirty.value && !busy.value) save() }
}
function beforeUnload(event) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }

watch(source, (value, old) => { if (normalized(value) !== normalized(old)) reset() })
onMounted(() => {
  reset()
  setLeaveGuard(() => !dirty.value || window.confirm('报告有未保存的修改，确认离开？'))
  window.addEventListener('keydown', keydown)
  window.addEventListener('beforeunload', beforeUnload)
})
onUnmounted(() => {
  setLeaveGuard(null)
  window.removeEventListener('keydown', keydown)
  window.removeEventListener('beforeunload', beforeUnload)
})
defineExpose({ dirty })
</script>

<template>
  <section class="editor" :aria-label="amend ? '更正报告' : '诊疗报告'">
    <header class="editor-head">
      <div>
        <h2 class="section-title">{{ amend ? `更正报告（将发布第 ${record.published_version + 1} 版）` : '诊疗报告' }}</h2>
        <p class="tiny" :class="dirty ? 'unsaved' : 'faint'">
          <template v-if="amend">修改后填写更正原因再发布，患者会看到更正说明。</template>
          <template v-else-if="dirty">有未保存的修改</template>
          <template v-else-if="record.report_version">草稿已保存（第 {{ record.report_version }} 次修改）<template v-if="savedAt">　{{ dateTime(savedAt) }}</template></template>
          <template v-else>尚未保存</template>
        </p>
      </div>
      <div class="editor-tools">
        <div class="segmented" role="tablist" aria-label="编辑或预览">
          <button role="tab" :aria-selected="view === 'edit'" @click="view = 'edit'">编辑</button>
          <button role="tab" :aria-selected="view === 'preview'" @click="view = 'preview'">预览</button>
        </div>
      </div>
    </header>

    <div v-if="canAi" class="ai-bar">
      <Sparkles :size="18" />
      <p><strong>AI 起草</strong><span>结合档案、描述、补充资料和附件生成草稿{{ record.ai_model ? `，上次使用 ${record.ai_model}` : '' }}。内容需要你逐项核对。</span></p>
      <button class="btn btn-secondary btn-sm" :disabled="aiBusy || busy" @click="generate">
        <LoaderCircle v-if="aiBusy" class="spin" :size="16" /><Sparkles v-else :size="16" />{{ aiBusy ? '生成中，约需半分钟' : '生成草稿' }}
      </button>
    </div>
    <p v-else-if="!amend && !record.consent_ai" class="hint editor-note">患者未授权 AI 辅助，本病例只能人工撰写。</p>

    <form v-show="view === 'edit'" class="editor-form" @submit.prevent>
      <label v-for="field in REPORT_FIELDS" :key="field.key" class="field">
        <span class="label">{{ field.label }}</span>
        <textarea v-model="report[field.key]" class="textarea" rows="4" maxlength="15000" :placeholder="field.placeholder" :disabled="aiBusy" />
      </label>
      <div class="field">
        <span class="label" id="visit-label">线下就诊建议</span>
        <div class="chips" role="radiogroup" aria-labelledby="visit-label">
          <button v-for="option in VISIT" :key="option.value" type="button" class="chip" role="radio"
                  :aria-checked="report.visit === option.value" :class="{ danger: option.value === 'emergency' }"
                  @click="report.visit = option.value">{{ option.label }}</button>
        </div>
      </div>
      <div class="field">
        <span class="label" id="followup-label">随访安排</span>
        <div class="chips" role="radiogroup" aria-labelledby="followup-label">
          <button v-for="option in FOLLOWUP" :key="option.value" type="button" class="chip" role="radio"
                  :aria-checked="report.followup_days === option.value" @click="report.followup_days = option.value">{{ option.label }}</button>
        </div>
        <span class="hint">选择天数后，患者会在到期前收到复诊提醒。</span>
      </div>
      <label v-if="amend" class="field">
        <span class="label">更正原因</span>
        <input v-model="reason" class="input" maxlength="500" placeholder="例如：补充用药注意事项" />
      </label>
    </form>
    <ReportPaper v-show="view === 'preview'" :record="record" :report="report" draft />

    <footer class="editor-foot">
      <p v-if="record.status === 'awaiting_info' && !amend" class="hint">正在等待患者补充资料，结束等待后才能发布。</p>
      <p v-else-if="missing.length" class="hint">发布前还需填写：{{ missing.join('、') }}</p>
      <div class="editor-actions">
        <button v-if="amend" class="btn btn-quiet" :disabled="busy" @click="emit('cancel')">取消更正</button>
        <button v-else class="btn btn-secondary" :disabled="busy || aiBusy || !dirty" @click="save()"><Save :size="16" />保存草稿</button>
        <button class="btn btn-primary" :disabled="busy || aiBusy || !canPublish || missing.length > 0 || (amend && reason.trim().length < 4)" @click="openConfirm">
          {{ amend ? '发布更正' : '审核并发布' }}
        </button>
      </div>
    </footer>

    <AppDialog v-if="confirming" :title="amend ? '确认发布更正' : '确认发布报告'" :busy="busy" @close="confirming = false">
      <p class="muted">发布后{{ record.profile.name }}会立即看到报告。{{ amend ? '原版本会保留在修改记录中。' : '已发布的报告只能通过“更正”修改，并会通知患者。' }}</p>
      <dl class="review compact">
        <div><dt>线下就诊</dt><dd :class="{ 'text-danger': ['soon', 'emergency'].includes(report.visit) }">{{ VISIT_FULL[report.visit] }}</dd></div>
        <div><dt>随访</dt><dd>{{ report.followup_days ? `${report.followup_days} 天后复诊` : '无需随访' }}</dd></div>
        <div v-if="amend"><dt>更正原因</dt><dd>{{ reason }}</dd></div>
      </dl>
      <p v-if="record.ai_generated_at && !amend" class="notice-inline"><CircleAlert :size="16" />本报告由 AI 草稿起草，系统会记录你对草稿的修改比例。</p>
      <label class="check"><input v-model="checked" type="checkbox" />我已逐项核对报告内容，并对发布的结论负责</label>
      <template #footer>
        <button class="btn btn-secondary" :disabled="busy" @click="confirming = false">继续修改</button>
        <button class="btn btn-primary" :disabled="busy || !checked" @click="publish"><LoaderCircle v-if="busy" class="spin" :size="16" />{{ amend ? '发布更正' : '发布报告' }}</button>
      </template>
    </AppDialog>
  </section>
</template>
