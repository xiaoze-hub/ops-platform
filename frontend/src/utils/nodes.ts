import { computed } from 'vue'
import { isProjectDeployEnabled } from '@/api/http'
import { isAbnormalMetric } from '@/utils/format'
import type { NodeInfo } from '@/api/types'
import { offlineDebouncer } from '@/utils/offline'

export interface DisplayNode extends NodeInfo {
  displayOnline: boolean
  abnormal: boolean
}

export function decorateNodes(raw: NodeInfo[], search = ''): DisplayNode[] {
  const q = search.trim().toLowerCase()
  return raw
    .map((n) => {
      const displayOnline = offlineDebouncer.update(n.node_id, n.online)
      const abnormal =
        displayOnline &&
        (isAbnormalMetric(n.cpu_percent) ||
          isAbnormalMetric(n.mem_percent) ||
          isAbnormalMetric(n.disk_percent) ||
          n.status === 'abnormal')
      return { ...n, displayOnline, abnormal }
    })
    .filter((n) => {
      if (!q) return true
      return (
        n.hostname.toLowerCase().includes(q) ||
        n.ip.toLowerCase().includes(q) ||
        n.node_id.toLowerCase().includes(q)
      )
    })
}

export function summarize(nodes: DisplayNode[]) {
  const total = nodes.length
  const online = nodes.filter((n) => n.displayOnline).length
  const offline = total - online
  const abnormal = nodes.filter((n) => n.abnormal).length
  return { total, online, offline, abnormal }
}

export function useDeployEnabled() {
  return computed(() => isProjectDeployEnabled())
}
