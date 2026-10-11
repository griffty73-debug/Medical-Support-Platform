<script setup>
import { computed } from 'vue'
import { Eye, EyeOff } from 'lucide-vue-next'

const props = defineProps({ profile: { type: Object, required: true }, revealed: String, canReveal: Boolean })
const emit = defineEmits(['reveal', 'hide'])
const allergic = computed(() => props.profile.allergies && !/^(无|没有|否认)$/.test(props.profile.allergies.trim()))
</script>

<template>
  <div class="facts">
    <dl class="facts-identity">
      <div><dt>姓名</dt><dd>{{ profile.name }}</dd></div>
      <div><dt>性别年龄</dt><dd>{{ profile.gender }}，{{ profile.age }} 岁</dd></div>
      <div v-if="profile.phone"><dt>手机</dt><dd>{{ profile.phone }}</dd></div>
      <div>
        <dt>身份证号
          <button v-if="canReveal" class="icon-btn reveal" type="button" :aria-label="revealed ? '隐藏身份证号' : '查看完整身份证号（将被记录）'"
                  :title="revealed ? '隐藏' : '查看完整号码，此操作会被记录'" @click="revealed ? emit('hide') : emit('reveal')">
            <EyeOff v-if="revealed" :size="14" /><Eye v-else :size="14" />
          </button>
        </dt>
        <dd class="nowrap">{{ revealed || profile.national_id_masked || '未填写' }}</dd>
      </div>
    </dl>
    <dl class="facts-health">
      <div :class="{ allergy: allergic }"><dt>过敏史</dt><dd class="prewrap">{{ profile.allergies || '未填写' }}</dd></div>
      <div><dt>当前用药</dt><dd class="prewrap">{{ profile.medications || '未填写' }}</dd></div>
      <div><dt>既往病史</dt><dd class="prewrap">{{ profile.history || '未填写' }}</dd></div>
    </dl>
  </div>
</template>
