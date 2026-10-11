export const STATUS = {
  pending: { label: '待接诊', tone: 'pending' },
  processing: { label: '评估中', tone: 'processing' },
  awaiting_info: { label: '待补充资料', tone: 'awaiting' },
  completed: { label: '已完成', tone: 'completed' },
  declined: { label: '已退回', tone: 'closed' },
  cancelled: { label: '已撤回', tone: 'closed' },
}

export const OPEN = ['pending', 'processing', 'awaiting_info']

export const URGENCY = {
  emergency: { label: '紧急', hint: '2 小时内响应' },
  urgent: { label: '尽快', hint: '12 小时内响应' },
  routine: { label: '常规', hint: '48 小时内响应' },
}

export const REPORT_FIELDS = [
  { key: 'summary', label: '初步评估', placeholder: '综合症状与资料，说明目前最可能的情况' },
  { key: 'basis', label: '判断依据', placeholder: '列出支持判断的症状、病史与检查结果' },
  { key: 'treatment', label: '处理建议', placeholder: '一般处理、用药注意事项或需要完善的检查' },
  { key: 'advice', label: '注意事项', placeholder: '需要观察的变化，以及出现哪些情况需要立即就医' },
]

export const VISIT = [
  { value: 'none', label: '暂不需要线下就诊' },
  { value: 'routine', label: '择期门诊' },
  { value: 'soon', label: '24 小时内就诊' },
  { value: 'emergency', label: '立即急诊' },
]
export const VISIT_FULL = {
  none: '暂不需要线下就诊',
  routine: '建议择期到门诊就诊',
  soon: '建议 24 小时内到医院就诊',
  emergency: '建议立即前往急诊',
}

export const FOLLOWUP = [
  { value: 0, label: '不需要' },
  { value: 3, label: '3 天' },
  { value: 7, label: '7 天' },
  { value: 14, label: '14 天' },
  { value: 30, label: '30 天' },
]

export const HISTORY_ACTIONS = {
  saved: '保存草稿', ai_generated: 'AI 生成草稿', published: '审核发布', amended: '更正发布',
}

export const DURATION_HINTS = ['今天', '1–3 天', '一周左右', '一个月左右', '更久']
