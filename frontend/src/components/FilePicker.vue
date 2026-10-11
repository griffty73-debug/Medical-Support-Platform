<script setup>
import { ref } from 'vue'
import { FileText, ImageIcon, Paperclip, Trash2 } from 'lucide-vue-next'
import { fileSize } from '../format'

const files = defineModel({ type: Array, default: () => [] })
const props = defineProps({ max: { type: Number, default: 5 }, label: { type: String, default: '添加检查报告或症状照片' }, compact: Boolean })
const problem = ref('')
const input = ref(null)
const MAX = 10 * 1024 * 1024

function add(event) {
  const picked = [...event.target.files]
  event.target.value = ''
  problem.value = ''
  if (files.value.length + picked.length > props.max) { problem.value = `最多添加 ${props.max} 个文件`; return }
  const bad = picked.find(file => !/\.(png|jpe?g|webp|pdf)$/i.test(file.name))
  if (bad) { problem.value = `“${bad.name}”不是支持的格式，请上传 PNG、JPG、WebP 或 PDF`; return }
  const large = picked.find(file => file.size > MAX)
  if (large) { problem.value = `“${large.name}”超过 10 MB，请压缩后再上传`; return }
  files.value = [...files.value, ...picked]
}

function remove(index) {
  files.value = files.value.filter((_, i) => i !== index)
}

defineExpose({ open: () => input.value?.click() })
</script>

<template>
  <div class="file-picker" :class="{ compact }">
    <label v-if="!compact" class="drop">
      <Paperclip :size="20" aria-hidden="true" />
      <span><strong>{{ label }}</strong><small>PNG、JPG、WebP 或 PDF，每个不超过 10 MB，最多 {{ max }} 个</small></span>
      <input ref="input" type="file" multiple accept=".png,.jpg,.jpeg,.webp,.pdf" @change="add" />
    </label>
    <input v-else ref="input" class="visually-hidden" type="file" multiple accept=".png,.jpg,.jpeg,.webp,.pdf" tabindex="-1" aria-hidden="true" @change="add" />
    <p v-if="problem" class="form-error" role="alert">{{ problem }}</p>
    <ul v-if="files.length" class="file-list">
      <li v-for="(file, index) in files" :key="file.name + index">
        <FileText v-if="/\.pdf$/i.test(file.name)" :size="18" /><ImageIcon v-else :size="18" />
        <span class="file-name">{{ file.name }}</span>
        <span class="faint small nowrap">{{ fileSize(file.size) }}</span>
        <button type="button" class="icon-btn" :aria-label="`移除 ${file.name}`" title="移除" @click="remove(index)"><Trash2 :size="16" /></button>
      </li>
    </ul>
  </div>
</template>
