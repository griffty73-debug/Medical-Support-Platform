<script setup>
import { computed, onMounted, ref } from 'vue'
import { Files, LoaderCircle, Search } from 'lucide-vue-next'
import { STATUS } from '../../constants'
import { caseStore, loadCases } from '../../store'
import CaseRow from '../../components/CaseRow.vue'
import EmptyState from '../../components/EmptyState.vue'

const status = ref('all')
const query = ref('')
const options = [['all', '全部'], ...Object.entries(STATUS).map(([key, meta]) => [key, meta.label])]
const counts = computed(() => Object.fromEntries(options.map(([key]) => [key, key === 'all' ? caseStore.list.length : caseStore.list.filter(c => c.status === key).length])))
const shown = computed(() => {
  const text = query.value.trim().toLowerCase()
  return [...caseStore.list]
    .filter(c => (status.value === 'all' || c.status === status.value)
      && (!text || `${c.title} ${c.number} ${c.patient.name}`.toLowerCase().includes(text)))
    .sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
})
onMounted(loadCases)
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div><h1 class="title-doc page-title">全部病例</h1><p>按最近更新排序，包括已完成和已关闭的病例。</p></div>
    </header>
    <div class="toolbar">
      <div class="chips" role="radiogroup" aria-label="按状态筛选">
        <button v-for="[key, label] in options" :key="key" class="chip" role="radio" :aria-checked="status === key"
                v-show="key === 'all' || counts[key]" @click="status = key">{{ label }}<span class="faint">{{ counts[key] }}</span></button>
      </div>
      <label class="search"><Search :size="16" /><input v-model="query" type="search" placeholder="搜索患者、标题或编号" aria-label="搜索病例" /></label>
    </div>
    <div v-if="!caseStore.loaded" class="loading"><LoaderCircle class="spin" :size="20" /></div>
    <div v-else-if="shown.length" class="case-list"><CaseRow v-for="item in shown" :key="item.id" :item="item" /></div>
    <EmptyState v-else :icon="Files" :title="query ? '没有找到匹配的病例' : '还没有病例'" :text="query ? '换个关键词试试。' : '患者向你提交的病例会出现在这里。'" />
  </div>
</template>
