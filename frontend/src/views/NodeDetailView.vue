<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createCommand, fetchCommands, fetchNode, fetchNodeLogs, fetchNodeResources } from '@/api/nodes'
import { buildWsLogsUrl, isProjectDeployEnabled } from '@/api/http'
import type { CommandItem, LogItem, NodeInfo, ResourceSnapshotBody } from '@/api/types'
import MetricGauge from '@/components/MetricGauge.vue'
import StatusLight from '@/components/StatusLight.vue'
import { formatDateTime, formatPercent, isAbnormalMetric, isWindowsNode } from '@/utils/format'
import { offlineDebouncer } from '@/utils/offline'

const route = useRoute()
const nodeId = computed(() => String(route.params.node_id || ''))

const node = ref<NodeInfo | null>(null)
const snapshot = ref<Partial<ResourceSnapshotBody>>({})
const snapshotAt = ref<string | null>(null)
const logsPreview = ref<LogItem[]>([])
const commands = ref<CommandItem[]>([])
const loading = ref(false)
const activeTab = ref('overview')
const resourceTab = ref('containers')
const deployEnabled = isProjectDeployEnabled()

const liveLogs = ref<LogItem[]>([])
const liveLevel = ref<'all' | 'info' | 'warn' | 'error'>('all')
const livePaused = ref(false)
const autoScroll = ref(true)
let ws: WebSocket | null = null
const logBox = ref<HTMLElement | null>(null)

const windowsNode = computed(() => isWindowsNode(node.value?.os))
const displayOnline = computed(() => {
  const n = node.value
  if (!n) return false
  return offlineDebouncer.update(n.node_id, !!n.online)
})
const abnormal = computed(() => {
  const n = node.value
  if (!n) return false
  return (
    isAbnormalMetric(n.cpu_percent) ||
    isAbnormalMetric(n.mem_percent) ||
    isAbnormalMetric(n.disk_percent)
  )
})

const containers = computed(() => snapshot.value.containers || [])
const images = computed(() => snapshot.value.images || [])
const services = computed(() => snapshot.value.services || [])
const projects = computed(() => snapshot.value.projects || [])

const filteredLiveLogs = computed(() => {
  if (liveLevel.value === 'all') return liveLogs.value
  return liveLogs.value.filter((l) => l.level === liveLevel.value)
})

async function loadAll() {
  if (!nodeId.value) return
  loading.value = true
  try {
    const [nodeRes, resRes, logsRes, cmdRes] = await Promise.all([
      fetchNode(nodeId.value),
      fetchNodeResources(nodeId.value),
      fetchNodeLogs(nodeId.value, 20),
      fetchCommands(nodeId.value, 50),
    ])
    node.value = nodeRes.data
    snapshot.value = resRes.data.snapshot || {}
    snapshotAt.value = resRes.data.timestamp
    logsPreview.value = logsRes.data
    commands.value = cmdRes.data
  } catch {
    ElMessage.error('加载节点详情失败')
  } finally {
    loading.value = false
  }
}

async function refreshCommands() {
  try {
    const { data } = await fetchCommands(nodeId.value, 50)
    commands.value = data
  } catch {
    // toast via interceptor
  }
}

async function refreshResources() {
  try {
    const { data } = await fetchNodeResources(nodeId.value)
    snapshot.value = data.snapshot || {}
    snapshotAt.value = data.timestamp
  } catch {
    // interceptor
  }
}

async function sendCommand(action: string, params: Record<string, unknown> = {}, danger = false) {
  if (danger) {
    const paramText = Object.keys(params).length ? ` ${JSON.stringify(params)}` : ''
    try {
      await ElMessageBox.confirm(`确认执行危险操作 ${action}${paramText}？`, '二次确认', {
        type: 'warning',
        confirmButtonText: '确认执行',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
  }
  try {
    await createCommand(nodeId.value, action, params)
    ElMessage.success(`指令已下发: ${action}`)
    await refreshCommands()
  } catch {
    // interceptor
  }
}

function onResourceTab(name: string | number) {
  const tab = String(name)
  if (tab === 'services' && windowsNode.value) return
  resourceTab.value = tab
}

function connectWs() {
  closeWs()
  if (!nodeId.value) return
  try {
    ws = new WebSocket(buildWsLogsUrl(nodeId.value))
    ws.onmessage = (ev) => {
      if (livePaused.value) return
      try {
        const msg = JSON.parse(ev.data as string)
        if (msg.type === 'logs' && Array.isArray(msg.items)) {
          liveLogs.value = [...liveLogs.value, ...msg.items].slice(-500)
          if (autoScroll.value) {
            void scrollLogs()
          }
        }
      } catch {
        // ignore malformed frames
      }
    }
    ws.onerror = () => {
      // fallback silently; REST preview still available
    }
  } catch {
    ws = null
  }
}

function closeWs() {
  if (ws) {
    try {
      ws.close()
    } catch {
      // ignore
    }
    ws = null
  }
}

async function scrollLogs() {
  await Promise.resolve()
  if (logBox.value) {
    logBox.value.scrollTop = logBox.value.scrollHeight
  }
}

async function loadInitialLiveLogs() {
  try {
    const { data } = await fetchNodeLogs(nodeId.value, 200)
    liveLogs.value = data
    if (autoScroll.value) void scrollLogs()
  } catch {
    // interceptor
  }
}

function onTabChange(name: string | number) {
  activeTab.value = String(name)
  if (activeTab.value === 'logs') {
    void loadInitialLiveLogs()
    connectWs()
  } else {
    closeWs()
  }
  if (activeTab.value === 'commands') {
    void refreshCommands()
  }
}

watch(
  () => route.query.tab,
  (tab) => {
    if (typeof tab === 'string' && tab) {
      activeTab.value = tab
      onTabChange(tab)
    }
  },
  { immediate: true },
)

watch(nodeId, () => {
  void loadAll()
  liveLogs.value = []
  if (activeTab.value === 'logs') {
    void loadInitialLiveLogs()
    connectWs()
  }
})

onMounted(() => {
  void loadAll()
  const q = route.query.tab
  if (typeof q === 'string' && q) {
    activeTab.value = q
  }
  if (activeTab.value === 'logs') {
    void loadInitialLiveLogs()
    connectWs()
  }
})

onBeforeUnmount(() => {
  closeWs()
})
</script>

<template>
  <div class="ops-page" v-loading="loading">
    <div class="ops-card detail-head">
      <div class="head-left">
        <StatusLight :online="displayOnline" :abnormal="abnormal" />
        <div>
          <div class="node-title">{{ node?.hostname || nodeId }}</div>
          <div class="ops-muted">
            {{ node?.ip || '—' }} · {{ node?.os || '—' }} · agent {{ node?.agent_version || '—' }}
          </div>
        </div>
      </div>
      <div class="head-right">
        <el-tag v-if="windowsNode" type="warning">Windows 节点</el-tag>
        <el-tag v-if="abnormal" type="danger">资源异常</el-tag>
        <el-button size="small" @click="loadAll">刷新</el-button>
      </div>
    </div>

    <div class="ops-card">
      <el-tabs :model-value="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="概览" name="overview">
          <div class="overview-grid">
            <div class="ops-card inner-card">
              <h3>基本信息</h3>
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="Node ID">{{ node?.node_id || '—' }}</el-descriptions-item>
                <el-descriptions-item label="主机名">{{ node?.hostname || '—' }}</el-descriptions-item>
                <el-descriptions-item label="IP">{{ node?.ip || '—' }}</el-descriptions-item>
                <el-descriptions-item label="系统">{{ node?.os || '—' }}</el-descriptions-item>
                <el-descriptions-item label="Agent 版本">{{ node?.agent_version || '—' }}</el-descriptions-item>
                <el-descriptions-item label="状态">{{ node?.online ? '在线' : '离线' }}</el-descriptions-item>
                <el-descriptions-item label="最后心跳">{{ formatDateTime(node?.last_seen_at) }}</el-descriptions-item>
                <el-descriptions-item label="负载">{{ node?.load_avg ?? '—' }}</el-descriptions-item>
              </el-descriptions>
            </div>

            <div class="ops-card inner-card">
              <h3>资源仪表盘</h3>
              <div class="ops-gauge-row">
                <MetricGauge :value="node?.cpu_percent" label="CPU" />
                <MetricGauge :value="node?.mem_percent" label="内存" />
                <MetricGauge :value="node?.disk_percent" label="磁盘" />
              </div>
              <div class="ops-muted gauge-hint">
                CPU {{ formatPercent(node?.cpu_percent) }} ·
                内存 {{ formatPercent(node?.mem_percent) }} ·
                磁盘 {{ formatPercent(node?.disk_percent) }}
              </div>
            </div>

            <div class="ops-card inner-card log-preview-card">
              <div class="ops-toolbar">
                <h3>日志预览</h3>
                <el-button size="small" text type="primary" @click="onTabChange('logs')">查看实时日志</el-button>
              </div>
              <div v-if="logsPreview.length" class="ops-terminal preview">
                <div
                  v-for="item in logsPreview"
                  :key="item.id"
                  class="ops-log-line"
                  :class="item.level"
                >
                  <span class="ts">{{ formatDateTime(item.timestamp) }}</span>
                  <span class="lv">[{{ item.level }}]</span>
                  <span>{{ item.content }}</span>
                </div>
              </div>
              <el-empty v-else description="暂无日志" :image-size="60" />
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="资源运维" name="resources">
          <div class="ops-toolbar" style="margin-bottom: 12px">
            <div class="ops-muted">
              快照时间：{{ formatDateTime(snapshotAt) }}
            </div>
            <div>
              <el-button size="small" @click="refreshResources">刷新快照</el-button>
              <el-button size="small" type="primary" @click="sendCommand('agent_status')">Agent 状态</el-button>
              <el-button size="small" type="warning" @click="sendCommand('restart_agent', {}, true)">重启 Agent</el-button>
              <el-button size="small" type="danger" @click="sendCommand('image_prune', {}, true)">镜像清理</el-button>
              <el-button
                v-if="deployEnabled"
                size="small"
                type="danger"
                @click="sendCommand('project_deploy', { path: projects[0]?.path || '/opt/projects/demo' }, true)"
              >
                项目部署
              </el-button>
            </div>
          </div>

          <el-tabs v-model="resourceTab" @tab-change="onResourceTab">
            <el-tab-pane label="容器" name="containers">
              <el-table :data="containers" stripe>
                <el-table-column prop="name" label="名称" min-width="140" />
                <el-table-column prop="image" label="镜像" min-width="160" show-overflow-tooltip />
                <el-table-column prop="status" label="状态" min-width="120" />
                <el-table-column label="操作" width="260" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" text type="warning" @click="sendCommand('container_restart', { name: row.name }, true)">重启</el-button>
                    <el-button size="small" text type="danger" @click="sendCommand('container_stop', { name: row.name }, true)">停止</el-button>
                    <el-button size="small" text type="success" @click="sendCommand('container_start', { name: row.name })">启动</el-button>
                    <el-button size="small" text type="info" @click="sendCommand('container_logs', { name: row.name, lines: 200 })">日志</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!containers.length" description="暂无容器数据" :image-size="60" />
            </el-tab-pane>

            <el-tab-pane label="镜像" name="images">
              <el-table :data="images" stripe>
                <el-table-column prop="repository" label="仓库" min-width="140" show-overflow-tooltip />
                <el-table-column prop="tag" label="Tag" width="100" />
                <el-table-column prop="size" label="大小" width="100" />
                <el-table-column label="操作" width="140">
                  <template #default>
                    <el-button size="small" text type="danger" @click="sendCommand('image_prune', {}, true)">清理 &lt;none&gt;</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!images.length" description="暂无镜像数据" :image-size="60" />
            </el-tab-pane>

            <el-tab-pane label="服务" name="services" :disabled="windowsNode">
              <el-alert
                v-if="windowsNode"
                type="info"
                :closable="false"
                title="该节点不支持"
                description="Windows 节点无 systemd，服务运维不可用。"
                show-icon
              />
              <template v-else>
                <el-table :data="services" stripe>
                  <el-table-column prop="name" label="服务" min-width="160" />
                  <el-table-column prop="active" label="状态" width="100" />
                  <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
                  <el-table-column label="操作" width="220" fixed="right">
                    <template #default="{ row }">
                      <el-button size="small" text type="warning" @click="sendCommand('service_restart', { name: row.name }, true)">重启</el-button>
                      <el-button size="small" text type="danger" @click="sendCommand('service_stop', { name: row.name }, true)">停止</el-button>
                      <el-button size="small" text type="info" @click="sendCommand('service_status', { name: row.name })">状态</el-button>
                    </template>
                  </el-table-column>
                </el-table>
                <el-empty v-if="!services.length" description="暂无服务数据" :image-size="60" />
              </template>
            </el-tab-pane>

            <el-tab-pane label="项目" name="projects">
              <el-table :data="projects" stripe>
                <el-table-column prop="name" label="名称" min-width="120" />
                <el-table-column prop="path" label="路径" min-width="220" show-overflow-tooltip />
                <el-table-column label="操作" width="140">
                  <template #default="{ row }">
                    <el-button
                      v-if="deployEnabled"
                      size="small"
                      text
                      type="danger"
                      @click="sendCommand('project_deploy', { path: row.path }, true)"
                    >
                      部署
                    </el-button>
                    <span v-else class="ops-muted">部署默认关闭</span>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!projects.length" description="暂无项目数据" :image-size="60" />
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>

        <el-tab-pane label="实时日志" name="logs">
          <div class="ops-toolbar" style="margin-bottom: 12px">
            <div class="log-controls">
              <el-radio-group v-model="liveLevel" size="small">
                <el-radio-button value="all">全部</el-radio-button>
                <el-radio-button value="info">info</el-radio-button>
                <el-radio-button value="warn">warn</el-radio-button>
                <el-radio-button value="error">error</el-radio-button>
              </el-radio-group>
              <el-switch v-model="livePaused" active-text="暂停" />
              <el-switch v-model="autoScroll" active-text="自动滚动" />
            </div>
            <div>
              <el-button size="small" @click="loadInitialLiveLogs">加载最近</el-button>
              <el-button size="small" @click="connectWs">重连 WS</el-button>
              <el-button size="small" @click="liveLogs = []">清空</el-button>
            </div>
          </div>
          <div ref="logBox" class="ops-terminal">
            <div
              v-for="item in filteredLiveLogs"
              :key="item.id"
              class="ops-log-line"
              :class="item.level"
            >
              <span class="ts">{{ formatDateTime(item.timestamp) }}</span>
              <span class="lv">[{{ item.level }}]</span>
              <span>{{ item.content }}</span>
            </div>
            <div v-if="!filteredLiveLogs.length" class="ops-muted">等待日志…</div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="指令历史" name="commands">
          <div class="ops-toolbar" style="margin-bottom: 12px">
            <span class="ops-muted">最近指令</span>
            <el-button size="small" @click="refreshCommands">刷新</el-button>
          </div>
          <el-table :data="commands" stripe>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="action" label="Action" min-width="140" />
            <el-table-column label="参数" min-width="160">
              <template #default="{ row }">
                <code>{{ JSON.stringify(row.params || {}) }}</code>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag
                  size="small"
                  :type="row.status === 'done' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'"
                >
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="result" label="结果" min-width="200" show-overflow-tooltip />
            <el-table-column label="创建时间" min-width="150">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="完成时间" min-width="150">
              <template #default="{ row }">{{ formatDateTime(row.finished_at) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!commands.length" description="暂无指令" :image-size="60" />
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<style scoped>
.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.head-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-title {
  font-size: 18px;
  font-weight: 700;
}

.overview-grid {
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 12px;
}

.log-preview-card {
  grid-column: 1 / -1;
}

.inner-card {
  box-shadow: none;
}

.inner-card h3 {
  margin: 0 0 12px;
  font-size: 14px;
}

.gauge-hint {
  margin-top: 8px;
  text-align: center;
  font-size: 12px;
}

.ops-terminal.preview {
  min-height: 120px;
  max-height: 220px;
}

.log-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

@media (max-width: 900px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .detail-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
