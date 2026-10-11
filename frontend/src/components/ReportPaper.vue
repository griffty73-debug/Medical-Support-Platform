<script setup>
// The report rendered as a printed record: Song typeface, ruled header, and the
// reviewing doctor's seal once it is published.
import { computed } from 'vue'
import { REPORT_FIELDS, VISIT_FULL } from '../constants'
import { fullDay } from '../format'

const props = defineProps({ record: { type: Object, required: true }, report: { type: Object, required: true }, draft: Boolean })
const issued = computed(() => props.record.amended_at || props.record.published_at)
const edition = computed(() => props.record.published_version > 1 ? `第 ${props.record.published_version} 版` : '')
</script>

<template>
  <article class="paper" :class="{ draft }">
    <p v-if="draft" class="paper-draft">未发布草稿，患者不可见</p>
    <header class="paper-head">
      <h2>诊疗评估报告</h2>
      <p>
        <span>编号 {{ record.number }}</span>
        <span v-if="edition">{{ edition }}</span>
        <span>{{ record.kind === 'followup' ? '复诊' : '初诊' }}</span>
      </p>
    </header>
    <dl class="paper-meta">
      <div><dt>姓名</dt><dd>{{ record.profile.name }}</dd></div>
      <div><dt>性别年龄</dt><dd>{{ record.profile.gender }}，{{ record.profile.age }} 岁</dd></div>
      <div><dt>医生</dt><dd>{{ record.doctor.name }}</dd></div>
      <div><dt>科室</dt><dd>{{ record.doctor.department }}</dd></div>
    </dl>
    <p class="paper-subject"><span>主诉</span>{{ record.title }}</p>
    <section v-for="field in REPORT_FIELDS" :key="field.key" class="paper-section">
      <h3>{{ field.label }}</h3>
      <p :class="{ empty: !report[field.key] }" class="prewrap">{{ report[field.key] || '尚未填写' }}</p>
    </section>
    <section v-if="report.visit || report.followup_days" class="paper-orders">
      <div v-if="report.visit" :class="`visit-${report.visit}`"><h3>线下就诊</h3><p>{{ VISIT_FULL[report.visit] }}</p></div>
      <div v-if="report.followup_days !== null && report.followup_days !== undefined">
        <h3>随访</h3>
        <p v-if="report.followup_days">{{ report.followup_days }} 天后复诊<template v-if="record.followup_due && !draft">（{{ fullDay(record.followup_due) }}前后）</template></p>
        <p v-else>无需随访</p>
      </div>
    </section>
    <p v-if="!draft && record.published_version > 1 && record.status_reason" class="paper-amend">更正说明：{{ record.status_reason }}</p>
    <footer class="paper-foot">
      <div class="signature">
        <span>审核医生</span>
        <strong>{{ record.doctor.name }}</strong>
        <span>{{ record.doctor.title }}</span>
        <span v-if="!draft && issued">{{ fullDay(issued) }}</span>
      </div>
      <div v-if="!draft && issued" class="seal" aria-label="医生已审核签发"><span>审核</span><span>签发</span></div>
    </footer>
    <p class="paper-note">本报告基于线上提交的资料形成，不能替代线下面诊与必要检查。出现急症请立即拨打 120 或前往急诊。</p>
  </article>
</template>
