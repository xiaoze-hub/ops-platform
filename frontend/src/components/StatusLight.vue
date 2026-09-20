<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  online: boolean
  abnormal?: boolean
}>()

const cls = computed(() => {
  if (props.abnormal) return 'abnormal'
  return props.online ? 'online' : 'offline'
})

const text = computed(() => {
  if (props.abnormal) return '异常'
  return props.online ? '在线' : '离线'
})
</script>

<template>
  <span class="status-wrap">
    <span class="ops-status-dot" :class="cls" />
    <span>{{ text }}</span>
  </span>
</template>

<style scoped>
.status-wrap {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}
</style>
