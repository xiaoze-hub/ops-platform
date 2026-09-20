import { http } from './http'
import type {
  CommandItem,
  LogItem,
  MetricPoint,
  MetricRange,
  NodeInfo,
  ResourceSnapshotResp,
} from './types'

export function fetchNodes() {
  return http.get<NodeInfo[]>('/nodes')
}

export function fetchNode(nodeId: string) {
  return http.get<NodeInfo>(`/nodes/${encodeURIComponent(nodeId)}`)
}

export function fetchNodeResources(nodeId: string) {
  return http.get<ResourceSnapshotResp>(`/nodes/${encodeURIComponent(nodeId)}/resources`)
}

export function fetchNodeMetrics(nodeId: string, range: MetricRange = '1h') {
  return http.get<MetricPoint[]>(`/nodes/${encodeURIComponent(nodeId)}/metrics`, {
    params: { range },
  })
}

export function fetchNodeLogs(nodeId: string, limit = 200) {
  return http.get<LogItem[]>(`/nodes/${encodeURIComponent(nodeId)}/logs`, {
    params: { limit },
  })
}

export function createCommand(nodeId: string, action: string, params: Record<string, unknown> = {}) {
  return http.post<CommandItem>(`/nodes/${encodeURIComponent(nodeId)}/commands`, {
    action,
    params,
  })
}

export function fetchCommands(nodeId: string, limit = 100) {
  return http.get<CommandItem[]>(`/nodes/${encodeURIComponent(nodeId)}/commands`, {
    params: { limit },
  })
}
