<script setup>
// Accessible modal dialog: focus moves in on open, Tab stays inside, Escape closes,
// and focus returns to the control that opened it.
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { X } from 'lucide-vue-next'

const props = defineProps({ title: { type: String, required: true }, wide: Boolean, busy: Boolean })
const emit = defineEmits(['close'])
const panel = ref(null)
const id = `dialog-${Math.random().toString(36).slice(2, 8)}`
let previous

function focusables() {
  return [...panel.value.querySelectorAll('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])')]
    .filter(el => el.offsetParent !== null)
}

function keydown(event) {
  if (event.key === 'Escape' && !props.busy) { event.stopPropagation(); emit('close') }
  if (event.key !== 'Tab') return
  const items = focusables()
  if (!items.length) return
  const first = items[0], last = items.at(-1)
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
}

onMounted(async () => {
  previous = document.activeElement
  document.body.classList.add('dialog-open')
  await nextTick()
  const target = panel.value.querySelector('[autofocus], textarea, input, select') || focusables()[0]
  target?.focus()
})
onUnmounted(() => {
  document.body.classList.remove('dialog-open')
  previous?.focus?.()
})
</script>

<template>
  <Teleport to="body">
    <div class="dialog-backdrop" @pointerdown.self="!busy && emit('close')" @keydown="keydown">
      <section ref="panel" class="dialog" :class="{ wide }" role="dialog" aria-modal="true" :aria-labelledby="id">
        <header class="dialog-head">
          <h2 :id="id">{{ title }}</h2>
          <button class="icon-btn" type="button" aria-label="关闭" title="关闭" :disabled="busy" @click="emit('close')"><X :size="20" /></button>
        </header>
        <div class="dialog-body"><slot /></div>
        <footer v-if="$slots.footer" class="dialog-foot"><slot name="footer" /></footer>
      </section>
    </div>
  </Teleport>
</template>
