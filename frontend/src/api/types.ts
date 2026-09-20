export interface LoginPayload {
  username: string
  password: string
}

export interface LoginResult {
  access_token: string
  token_type: string
  must_change_password: boolean
}

export interface ChangePasswordPayload {
  old_password: string
  new_password: string
}

export interface NodeInfo {
  node_id: string
  hostname: string
  ip: string
  os: string
  agent_version: string
  status: string
  online: boolean
  last_seen_at: string | null
  created_at?: string | null
  cpu_percent: number | null
  mem_percent: number | null
  disk_percent: number | null
  load_avg: number | null
}

export interface MetricPoint {
  cpu_percent: number | null
  mem_percent: number | null
  disk_percent: number | null
  load_avg: number | null
  timestamp: string
}

export interface LogItem {
  id: number
  node_id: string
  level: string
  content: string
  timestamp: string
}

export interface CommandItem {
  id: number
  node_id: string
  action: string
  params: Record<string, unknown>
  status: string
  result: string | null
  created_at: string
  finished_at: string | null
}

export interface ContainerItem {
  name: string
  image: string
  status: string
}

export interface ImageItem {
  repository: string
  tag: string
  size: string
}

export interface ServiceItem {
  name: string
  active: string
  description: string
}

export interface ProjectItem {
  path: string
  name: string
}

export interface ResourceSnapshotBody {
  containers: ContainerItem[]
  images: ImageItem[]
  services: ServiceItem[]
  projects: ProjectItem[]
}

export interface ResourceSnapshotResp {
  node_id: string
  snapshot: Partial<ResourceSnapshotBody>
  timestamp: string | null
}

export interface HealthResp {
  ok: boolean
  project_deploy_enabled: boolean
}

export interface WsLogsMessage {
  type: string
  items?: LogItem[]
  detail?: string
}

export type MetricRange = '1h' | '6h' | '24h'
