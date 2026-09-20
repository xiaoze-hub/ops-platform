<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { useThemeStore } from '@/stores/theme'

const props = defineProps<{
  value: number | null | undefined
  label: string
  color?: string
}>()

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
const { isDark } = useThemeStore()

function render() {
  if (!el.value) return
  if (!chart) chart = echarts.init(el.value)
  const val = props.value ?? 0
  const dark = isDark.value
  const color = props.color || (val >= 90 ? '#f56c6c' : val >= 70 ? '#e6a23c' : '#67c23a')
  chart.setOption(
    {
      series: [
        {
          type: 'gauge',
          startAngle: 90,
          endAngle: -270,
          pointer: { show: false },
          progress: {
            show: true,
            overlap: false,
            roundCap: true,
            width: 12,
            itemStyle: { color },
          },
          axisLine: {
            lineStyle: {
              width: 12,
              color: [[1, dark ? '#2a3441' : '#eef0f3']],
            },
          },
          splitLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          data: [
            {
              value: Math.round(val),
              name: props.label,
              title: {
                color: dark ? '#9ca3af' : '#6b7280',
                fontSize: 12,
                offsetCenter: [0, '30%'],
              },
              detail: {
                valueAnimation: true,
                fontSize: 22,
                fontWeight: 700,
                color: dark ? '#e5e7eb' : '#1f2937',
                formatter: '{value}%',
                offsetCenter: [0, '0%'],
              },
            },
          ],
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

watch(() => [props.value, props.label], render)
watch(isDark, render)
</script>

<template>
  <div ref="el" class="gauge" />
</template>

<style scoped>
.gauge {
  width: 100%;
  height: 180px;
}
</style>
