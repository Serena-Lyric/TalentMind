<template>
  <div ref="chartRef" class="radar-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  data: {
    dimensions: string[]
    jobStandard: number[]
    personalAbility: number[]
  }
}>()

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

function render() {
  if (!chartRef.value || !props.data) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: {},
    legend: { data: ['岗位要求', '个人能力'], bottom: 0, textStyle: { fontSize: 11 } },
    radar: {
      indicator: props.data.dimensions.map(d => ({ name: d, max: 100 })),
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: '#8C8C8C', fontSize: 10 }
    },
    series: [{
      type: 'radar',
      data: [
        { name: '岗位要求', value: props.data.jobStandard, lineStyle: { color: '#E07B6D', width: 2 }, itemStyle: { color: '#E07B6D' }, areaStyle: { color: '#E07B6D20' } },
        { name: '个人能力', value: props.data.personalAbility, lineStyle: { color: '#66BB6A', width: 2 }, itemStyle: { color: '#66BB6A' }, areaStyle: { color: '#66BB6A20' } }
      ]
    }]
  })
}

watch(() => props.data, render, { deep: true })
onMounted(render)
onBeforeUnmount(() => chart?.dispose())
</script>

<style scoped>
.radar-chart { width: 100%; height: 280px; }
</style>
