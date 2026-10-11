<script setup>
import { computed, onMounted, ref } from 'vue'
import { ClipboardList, LoaderCircle, Plus, Search } from 'lucide-vue-next'
import { OPEN } from '../../constants'
import { caseStore, loadCases } from '../../store'
import AppLink from '../../components/AppLink.vue'
import CaseRow from '../../components/CaseRow.vue'
import EmptyState from '../../components/EmptyState.vue'

const filter = ref('all')
const query = ref('')
const filters = [
  { key: 'all', label: '全部', test: () => true },
  { key: 'open', label: '进行中', test: c => OPEN.includes(c.status) || c.status === 'declined' },
  { key: 'completed', label: '已完成', test: c => c.status === 'completed' },
  { key: 'closed', label: '已撤回', test: c => c.status === 'cancelled' },
]
const counts = computed(() => Object.fromEntries(filters.map(f => [f.key, caseStore.list.filter(f.test).length])))
const shown = computed(() => {
  const test = filters.find(f => f.key === filter.value).test
  const text = query.value.trim().toLowerCase()
  return caseStore.list.filter(c => test(c) && (!text || `${c.title} ${c.number} ${c.doctor.name}`.toLowerCase().includes(text)))
})
onMounted(loadCases)
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div><h1 class="title-doc page-title">我的病例</h1><p>每份病例的进度、报告和与医生的沟通都在这里。</p></div>
      <AppLink to="/cases/new" class="btn btn-primary"><Plus :size="18" />描述新的症状</AppLink>
    </header>
    <div class="toolbar">
      <div class="chips" role="radiogroup" aria-label="筛选病例">
        <button v-for="f in filters" :key="f.key" class="chip" role="radio" :aria-checked="filter === f.key" @click="filter = f.key">
          {{ f.label }}<span class="faint">{{ counts[f.key] }}</span>
        </button>
      </div>
      <label class="search"><Search :size="16" /><input v-model="query" type="search" placeholder="搜索标题、编号或医生" aria-label="搜索病例" /></label>
    </div>
    <div v-if="!caseStore.loaded" class="loading"><LoaderCircle class="spin" :size="20" /></div>
    <div v-else-if="shown.length" class="case-list"><CaseRow v-for="item in shown" :key="item.id" :item="item" /></div>
    <EmptyState v-else :icon="ClipboardList" :title="query ? '没有找到匹配的病例' : '这里还没有病例'"
                :text="query ? '换个关键词，或切换上方的筛选。' : '描述症状后，病例和医生的报告会出现在这里。'">
      <AppLink v-if="!query" to="/cases/new" class="btn btn-secondary">描述新的症状</AppLink>
    </EmptyState>
  </div>
</template>
