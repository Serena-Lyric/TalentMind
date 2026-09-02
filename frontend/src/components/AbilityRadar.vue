<template>
  <div v-if="hasData" ref="chartRef" class="radar-chart"></div>
  <div v-else class="radar-empty">暂无能力维度数据</div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  data: {
    dimensions: string[]
    jobStandard: number[]
    personalAbility: number[]
  }
}>()

const hasData = computed(() =>
  !!props.data &&
  Array.isArray(props.data.dimensions) && props.data.dimensions.length > 0 &&
  Array.isArray(props.data.jobStandard) && props.data.jobStandard.length > 0 &&
  Array.isArray(props.data.personalAbility) && props.data.personalAbility.length > 0
)

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

function render() {
  // 空数据只显示空态，不初始化 ECharts（避免 radarLayout 读取空 indicator 崩溃）
  if (!chartRef.value || !hasData.value) {
    if (chart) { chart.dispose(); chart = null }
    return
  }
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

watch(() => props.data, async () => {
  if (hasData.value) { await nextTick(); render() }
  else render()
}, { deep: true })
onMounted(render)
onBeforeUnmount(() => chart?.dispose())
</script>

<style scoped>
.radar-chart { width: 100%; height: 280px; }
.radar-empty {
  width: 100%;
  height: 280px;
  display: grid;
  place-items: center;
  color: #B0B0B0;
  font-size: 13px;
  background: #FDFBF7;
}
</style>
