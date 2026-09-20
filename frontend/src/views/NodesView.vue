<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchNodes } from '@/api/nodes'
import StatusLight from '@/components/StatusLight.vue'
import { globalSearch } from '@/stores/theme'
import { decorateNodes } from '@/utils/nodes'
import { formatDateTime, formatPercent, isWindowsNode } from '@/utils/format'
import type { NodeInfo } from '@/api/types'

const router = useRouter()
const rawNodes = ref<NodeInfo[]>([])
const loading = ref(false)
const polling = ref(true)
let timer: number | null = null

const nodes = computed(() => decorateNodes(rawNodes.value, globalSearch.value))

async function loadNodes(silent = false) {
  if (!silent) loading.value = true
  try {
    const { data } = await fetchNodes()
    rawNodes.value = data
  } catch {
    if (!silent) ElMessage.error('加载节点失败')
  } finally {
    loading.value = false
  }
}

function goDetail(nodeId: string, tab = 'overview') {
  router.push({ name: 'node-detail', params: { node_id: nodeId }, query: { tab } })
}

function startTimer() {
  stopTimer()
  timer = window.setInterval(() => {
    if (polling.value) void loadNodes(true)
  }, 5000)
}

function stopTimer() {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
}

onMounted(() => {
  void loadNodes()
  startTimer()
})

onBeforeUnmount(stopTimer)
</script>

<template>
  <div class="ops-page">
    <div class="ops-card">
      <div class="ops-toolbar">
        <div>
          <strong>节点管理</strong>
          <span class="ops-muted" style="margin-left: 8px">
            共 {{ nodes.length }} 台 · 顶部搜索可过滤 hostname / IP
          </span>
        </div>
        <div class="toolbar-right">
          <span class="ops-muted">5s 轮询</span>
          <el-switch v-model="polling" />
          <el-button size="small" :loading="loading" @click="loadNodes()">刷新</el-button>
        </div>
      </div>

      <el-table :data="nodes" stripe v-loading="loading" style="width: 100%">
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <StatusLight :online="row.displayOnline" :abnormal="row.abnormal" />
          </template>
        </el-table-column>
        <el-table-column prop="node_id" label="Node ID" min-width="140" show-overflow-tooltip />
        <el-table-column prop="hostname" label="主机名" min-width="120" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP" min-width="120" />
        <el-table-column label="系统" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.os || '—' }}
            <el-tag v-if="isWindowsNode(row.os)" size="small" type="warning" style="margin-left: 4px">
              Windows
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="agent_version" label="Agent" width="90" />
        <el-table-column label="CPU" width="80">
          <template #default="{ row }">{{ formatPercent(row.cpu_percent) }}</template>
        </el-table-column>
        <el-table-column label="内存" width="80">
          <template #default="{ row }">{{ formatPercent(row.mem_percent) }}</template>
        </el-table-column>
        <el-table-column label="磁盘" width="80">
          <template #default="{ row }">{{ formatPercent(row.disk_percent) }}</template>
        </el-table-column>
        <el-table-column label="最后心跳" min-width="150">
          <template #default="{ row }">{{ formatDateTime(row.last_seen_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="goDetail(row.node_id, 'overview')">详情</el-button>
            <el-button size="small" text type="warning" @click="goDetail(row.node_id, 'resources')">运维</el-button>
            <el-button size="small" text type="info" @click="goDetail(row.node_id, 'logs')">日志</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
