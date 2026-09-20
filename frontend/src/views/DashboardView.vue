<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchNodeMetrics, fetchNodes } from '@/api/nodes'
import type { MetricPoint, MetricRange } from '@/api/types'
import StatCards from '@/components/StatCards.vue'
import MetricTrendChart from '@/components/MetricTrendChart.vue'
import StatusLight from '@/components/StatusLight.vue'
import { globalSearch } from '@/stores/theme'
import { decorateNodes } from '@/utils/nodes'
import { formatDateTime, formatPercent } from '@/utils/format'
import type { NodeInfo } from '@/api/types'

const router = useRouter()
const rawNodes = ref<NodeInfo[]>([])
const loading = ref(false)
const polling = ref(true)
const range = ref<MetricRange>('1h')
const selectedNodeId = ref('')
const trendPoints = ref<MetricPoint[]>([])
const trendLoading = ref(false)

let timer: number | null = null

const nodes = computed(() => decorateNodes(rawNodes.value, globalSearch.value))

const nodeOptions = computed(() =>
  rawNodes.value.map((n) => ({
    label: `${n.hostname || n.node_id} (${n.ip || n.node_id})`,
    value: n.node_id,
  })),
)

async function loadNodes(silent = false) {
  if (!silent) loading.value = true
  try {
    const { data } = await fetchNodes()
    rawNodes.value = data
    if (!selectedNodeId.value && data.length) {
      selectedNodeId.value = data[0].node_id
      void loadTrend()
    }
  } catch {
    if (!silent) ElMessage.error('加载节点列表失败')
  } finally {
    loading.value = false
  }
}

async function loadTrend() {
  if (!selectedNodeId.value) {
    trendPoints.value = []
    return
  }
  trendLoading.value = true
  try {
    const { data } = await fetchNodeMetrics(selectedNodeId.value, range.value)
    trendPoints.value = data
  } catch {
    trendPoints.value = []
  } finally {
    trendLoading.value = false
  }
}

function startTimer() {
  stopTimer()
  timer = window.setInterval(() => {
    if (!polling.value) return
    void loadNodes(true)
    if (selectedNodeId.value) void loadTrend()
  }, 5000)
}

function stopTimer() {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
}

function onPollingChange(val: boolean | string | number) {
  polling.value = Boolean(val)
  if (polling.value) startTimer()
}

function goDetail(nodeId: string, tab = 'overview') {
  router.push({ name: 'node-detail', params: { node_id: nodeId }, query: { tab } })
}

onMounted(() => {
  void loadNodes()
  startTimer()
})

onBeforeUnmount(() => {
  stopTimer()
})
</script>

<template>
  <div class="ops-page">
    <StatCards :nodes="nodes" />

    <div class="ops-card">
      <div class="ops-toolbar">
        <div class="toolbar-left">
          <span class="ops-muted">集群趋势</span>
          <el-select
            v-model="selectedNodeId"
            class="node-select"
            placeholder="选择节点"
            filterable
            @change="loadTrend"
          >
            <el-option
              v-for="opt in nodeOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
          <el-radio-group v-model="range" size="small" @change="loadTrend">
            <el-radio-button value="1h">1h</el-radio-button>
            <el-radio-button value="6h">6h</el-radio-button>
            <el-radio-button value="24h">24h</el-radio-button>
          </el-radio-group>
        </div>
        <div class="toolbar-right">
          <span class="ops-muted">5s 轮询</span>
          <el-switch :model-value="polling" @change="onPollingChange" />
        </div>
      </div>
      <MetricTrendChart :points="trendPoints" :title="selectedNodeId ? `节点 ${selectedNodeId} CPU/内存` : 'CPU/内存趋势'" />
    </div>

    <div class="ops-card">
      <div class="ops-toolbar">
        <span class="ops-muted">节点列表</span>
        <el-button size="small" :loading="loading" @click="loadNodes()">刷新</el-button>
      </div>
      <el-table :data="nodes" stripe style="width: 100%" v-loading="loading">
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <StatusLight :online="row.displayOnline" :abnormal="row.abnormal" />
          </template>
        </el-table-column>
        <el-table-column prop="hostname" label="主机名" min-width="120" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP" min-width="120" show-overflow-tooltip />
        <el-table-column prop="os" label="系统" min-width="120" show-overflow-tooltip />
        <el-table-column prop="agent_version" label="版本" width="90" />
        <el-table-column label="CPU" width="80">
          <template #default="{ row }">
            <span :class="{ 'ops-danger': (row.cpu_percent ?? 0) >= 90 }">
              {{ formatPercent(row.cpu_percent) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="内存" width="80">
          <template #default="{ row }">
            <span :class="{ 'ops-danger': (row.mem_percent ?? 0) >= 90 }">
              {{ formatPercent(row.mem_percent) }}
            </span>
          </template>
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
.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.node-select {
  width: 240px;
}

@media (max-width: 720px) {
  .node-select {
    width: 160px;
  }
}
</style>
