<script setup lang="ts">
import { computed } from 'vue'
import type { DisplayNode } from '@/utils/nodes'

const props = defineProps<{
  nodes: DisplayNode[]
  title?: string
}>()

const stats = computed(() => {
  const total = props.nodes.length
  const online = props.nodes.filter((n) => n.displayOnline).length
  const offline = total - online
  const abnormal = props.nodes.filter((n) => n.abnormal).length
  return [
    { label: props.title ? `${props.title} · 总数` : '节点总数', value: total, type: 'info' as const },
    { label: '在线', value: online, type: 'success' as const },
    { label: '离线', value: offline, type: 'info' as const },
    { label: '异常', value: abnormal, type: 'warning' as const },
  ]
})
</script>

<template>
  <div class="stat-grid">
    <div v-for="item in stats" :key="item.label" class="ops-card stat-card">
      <div class="stat-label ops-muted">{{ item.label }}</div>
      <div class="stat-value" :class="item.type">{{ item.value }}</div>
    </div>
  </div>
</template>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 900px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.stat-card {
  padding: 16px 18px;
}

.stat-label {
  font-size: 13px;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
}

.stat-value.success {
  color: #67c23a;
}

.stat-value.warning {
  color: #e6a23c;
}

.stat-value.info {
  color: var(--ops-text);
}
</style>
