<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchNodeLogs, fetchNodes } from '@/api/nodes'
import type { LogItem } from '@/api/types'
import { formatDateTime } from '@/utils/format'

const nodes = ref<{ node_id: string; hostname: string }[]>([])
const selectedNode = ref('')
const keyword = ref('')
const level = ref<'all' | 'info' | 'warn' | 'error'>('all')
const logs = ref<LogItem[]>([])
const loading = ref(false)

const filtered = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return logs.value.filter((item) => {
    if (level.value !== 'all' && item.level !== level.value) return false
    if (!q) return true
    return item.content.toLowerCase().includes(q)
  })
})

async function loadNodes() {
  try {
    const { data } = await fetchNodes()
    nodes.value = data.map((n) => ({ node_id: n.node_id, hostname: n.hostname || n.node_id }))
    if (!selectedNode.value && nodes.value.length) {
      selectedNode.value = nodes.value[0].node_id
    }
  } catch {
    // interceptor
  }
}

async function loadLogs() {
  if (!selectedNode.value) {
    ElMessage.warning('请先选择节点')
    return
  }
  loading.value = true
  try {
    const { data } = await fetchNodeLogs(selectedNode.value, 200)
    logs.value = data
  } catch {
    logs.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadNodes()
  if (selectedNode.value) await loadLogs()
})
</script>

<template>
  <div class="ops-page">
    <div class="ops-card">
      <div class="ops-toolbar" style="margin-bottom: 12px">
        <div class="filters">
          <el-select v-model="selectedNode" class="node-select" placeholder="选择节点" filterable>
            <el-option
              v-for="n in nodes"
              :key="n.node_id"
              :label="`${n.hostname} (${n.node_id})`"
              :value="n.node_id"
            />
          </el-select>
          <el-select v-model="level" class="level-select" placeholder="级别">
            <el-option label="全部级别" value="all" />
            <el-option label="info" value="info" />
            <el-option label="warn" value="warn" />
            <el-option label="error" value="error" />
          </el-select>
          <el-input
            v-model="keyword"
            class="kw-input"
            placeholder="搜索日志内容"
            clearable
          />
          <el-button type="primary" :loading="loading" @click="loadLogs">检索</el-button>
        </div>
        <span class="ops-muted">{{ filtered.length }} 条</span>
      </div>

      <div v-if="filtered.length" class="ops-terminal">
        <div
          v-for="item in filtered"
          :key="item.id"
          class="ops-log-line"
          :class="item.level"
        >
          <span class="ts">{{ formatDateTime(item.timestamp) }}</span>
          <span class="lv">[{{ item.level }}]</span>
          <span>{{ item.content }}</span>
        </div>
      </div>
      <el-empty v-else description="无匹配日志" />
    </div>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.node-select {
  width: 240px;
}

.level-select {
  width: 130px;
}

.kw-input {
  width: 220px;
}

@media (max-width: 720px) {
  .node-select,
  .kw-input {
    width: 160px;
  }
}
</style>
