<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { useThemeStore } from '@/stores/theme'
import type { MetricPoint } from '@/api/types'

const props = defineProps<{
  points: MetricPoint[]
  title?: string
  height?: number
}>()

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
const { isDark } = useThemeStore()

function render() {
  if (!el.value) return
  if (!chart) {
    chart = echarts.init(el.value)
  }
  const dark = isDark.value
  const axisColor = dark ? '#9ca3af' : '#6b7280'
  const splitColor = dark ? '#2a3441' : '#e5e7eb'
  const times = props.points.map((p) => {
    const d = new Date(p.timestamp)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  })
  chart.setOption(
    {
      backgroundColor: 'transparent',
      title: props.title
        ? {
            text: props.title,
            left: 0,
            top: 0,
            textStyle: { color: dark ? '#e5e7eb' : '#1f2937', fontSize: 14, fontWeight: 600 },
          }
        : undefined,
      tooltip: { trigger: 'axis' },
      legend: {
        data: ['CPU %', '内存 %'],
        top: props.title ? 28 : 0,
        textStyle: { color: axisColor },
      },
      grid: { left: 40, right: 16, top: props.title ? 64 : 36, bottom: 28 },
      xAxis: {
        type: 'category',
        data: times,
        axisLine: { lineStyle: { color: splitColor } },
        axisLabel: { color: axisColor },
      },
      yAxis: {
        type: 'value',
        max: 100,
        axisLine: { show: false },
        axisLabel: { color: axisColor },
        splitLine: { lineStyle: { color: splitColor } },
      },
      series: [
        {
          name: 'CPU %',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: props.points.map((p) => p.cpu_percent),
          itemStyle: { color: '#409eff' },
          areaStyle: { color: 'rgba(64,158,255,0.12)' },
        },
        {
          name: '内存 %',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: props.points.map((p) => p.mem_percent),
          itemStyle: { color: '#67c23a' },
          areaStyle: { color: 'rgba(103,194,58,0.12)' },
        },
      ],
    },
    true,
  )
}

function onResize() {
  chart?.resize()
}

onMounted(() => {
  render()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})

watch(() => props.points, render, { deep: true })
watch(isDark, render)
</script>

<template>
  <div
    ref="el"
    class="trend-chart"
    :style="{ height: `${height || 320}px` }"
  />
</template>

<style scoped>
.trend-chart {
  width: 100%;
}
</style>
