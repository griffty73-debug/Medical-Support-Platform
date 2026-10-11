<script setup>
import { ArrowDownToLine, FileText, ImageIcon } from 'lucide-vue-next'
import { download } from '../api'
import { fileSize } from '../format'
import { toast } from '../session'

defineProps({ items: { type: Array, required: true }, showSource: Boolean })

async function get(item) {
  try { await download(`/attachments/${item.id}`, item.name) }
  catch (err) { toast(err.message, 'error') }
}
</script>

<template>
  <ul class="file-list attachments">
    <li v-for="item in items" :key="item.id">
      <FileText v-if="item.mime === 'application/pdf'" :size="18" /><ImageIcon v-else :size="18" />
      <button class="file-name link-like" :title="`下载 ${item.name}`" @click="get(item)">{{ item.name }}</button>
      <span v-if="showSource && item.message_id" class="tag tone-closed">{{ item.uploaded_by === 'doctor' ? '医生发送' : '后续补充' }}</span>
      <span class="faint small nowrap">{{ fileSize(item.size) }}</span>
      <button class="icon-btn" :aria-label="`下载 ${item.name}`" title="下载" @click="get(item)"><ArrowDownToLine :size="16" /></button>
    </li>
  </ul>
</template>
