<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { LoaderCircle, Paperclip, Send } from 'lucide-vue-next'
import { api, isDoctor } from '../api'
import { dateTime, day } from '../format'
import { refreshSummary, session, toast } from '../session'
import AttachmentList from './AttachmentList.vue'
import FilePicker from './FilePicker.vue'

const props = defineProps({
  caseId: { type: Number, required: true },
  canSend: Boolean,
  closedText: { type: String, default: '' },
  until: { type: String, default: null },
})
const emit = defineEmits(['sent'])
const messages = ref([])
const loaded = ref(false)
const text = ref('')
const files = ref([])
const sending = ref(false)
const picker = ref(null)
const list = ref(null)

const KIND = { info_request: '请求补充资料', supplement: '补充资料' }

async function load() {
  try {
    const before = messages.value.length
    messages.value = await api(`/cases/${props.caseId}/messages`)
    loaded.value = true
    if (messages.value.length !== before) scrollToEnd()
    refreshSummary()
  } catch (err) { if (!loaded.value) toast(err.message, 'error') }
}

async function scrollToEnd() {
  await nextTick()
  if (list.value) list.value.scrollTop = list.value.scrollHeight
}

async function send() {
  if (!text.value.trim() && !files.value.length) return
  sending.value = true
  try {
    const message = await api(`/cases/${props.caseId}/messages`, { method: 'POST', form: { body: text.value.trim(), attachments: files.value } })
    messages.value.push(message)
    text.value = ''
    files.value = []
    scrollToEnd()
    emit('sent')
  } catch (err) { toast(err.message, 'error') }
  finally { sending.value = false }
}

function keydown(event) {
  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) send()
}

let timer
onMounted(() => { load(); timer = setInterval(() => { if (!document.hidden) load() }, 15000) })
onUnmounted(() => clearInterval(timer))
watch(() => session.activity, load)
watch(() => props.caseId, () => { messages.value = []; loaded.value = false; load() })
defineExpose({ reload: load })
</script>

<template>
  <section class="thread" aria-label="医患沟通">
    <div ref="list" class="thread-list" aria-live="polite">
      <p v-if="loaded && !messages.length && canSend" class="thread-empty">
        {{ isDoctor ? '还没有消息。可以在这里向患者追问细节或解释报告。' : '还没有消息。有新的情况或疑问，可以在这里告诉医生。' }}
      </p>
      <article v-for="message in messages" :key="message.id" class="bubble" :class="{ mine: message.mine, [message.kind]: true }">
        <header>
          <strong>{{ message.mine ? '我' : message.sender.role === 'doctor' ? message.sender.name : '患者' }}</strong>
          <span v-if="KIND[message.kind]" class="bubble-kind">{{ KIND[message.kind] }}</span>
          <time>{{ dateTime(message.created_at) }}</time>
        </header>
        <p class="prewrap">{{ message.body }}</p>
        <AttachmentList v-if="message.attachments.length" :items="message.attachments" />
      </article>
    </div>
    <form v-if="canSend" class="composer" @submit.prevent="send">
      <label class="visually-hidden" :for="`composer-${caseId}`">输入消息</label>
      <textarea :id="`composer-${caseId}`" v-model="text" class="textarea" rows="2" maxlength="2000"
                :placeholder="isDoctor ? '给患者发消息' : '给医生发消息，例如症状的新变化'" @keydown="keydown" />
      <FilePicker ref="picker" v-model="files" compact />
      <div class="composer-actions">
        <button type="button" class="btn btn-quiet btn-sm" @click="picker.open()"><Paperclip :size="16" />添加附件</button>
        <span v-if="until" class="faint tiny">沟通开放至 {{ day(until) }}</span>
        <button class="btn btn-primary btn-sm" :disabled="sending || (!text.trim() && !files.length)">
          <LoaderCircle v-if="sending" class="spin" :size="16" /><Send v-else :size="16" />发送
        </button>
      </div>
    </form>
    <p v-else-if="closedText" class="thread-closed">{{ closedText }}</p>
  </section>
</template>
