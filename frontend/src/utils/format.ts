export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toFixed(digits)}%`
}

export function isWindowsNode(os: string | null | undefined): boolean {
  return (os || '').toLowerCase().includes('windows')
}

export function isAbnormalMetric(value: number | null | undefined, threshold = 90): boolean {
  return value !== null && value !== undefined && value >= threshold
}
