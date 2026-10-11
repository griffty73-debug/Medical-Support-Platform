<script setup>
import { linkHandler } from '../router'
defineProps({ to: { type: String, required: true } })
</script>

<template>
  <a :href="to" @click="linkHandler($event, to)"><slot /></a>
</template>
