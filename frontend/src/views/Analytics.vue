<template>
  <section class="page analytics-page" v-loading="loading">
    <div class="page-title"><div class="title-left"><div class="module-mark analytics-mark"><el-icon><DataAnalysis /></el-icon></div><div><h1>数据分析中心</h1><p>用真实岗位、技能与技术信号观察系统当前数据状态</p></div></div><el-button class="btn-soft" @click="loadData"><el-icon><RefreshRight /></el-icon>刷新数据</el-button></div>

    <div class="analytics-kpi-grid">
      <article v-for="card in kpiCards" :key="card.label" class="analytics-kpi"><div class="kpi-icon" :class="card.tone"><el-icon><component :is="card.icon" /></el-icon></div><div><small>{{ card.label }}</small><strong>{{ card.value }}</strong><span>{{ card.note }}</span></div></article>
    </div>

    <div class="analytics-grid">
      <section class="panel chart-panel chart-wide"><div class="section-heading"><div><h2>技术信号趋势</h2><p>按 signal 表中真实 captured_at 聚合</p></div><el-tag v-if="!trend.series.length" effect="plain">暂无数据</el-tag></div><div v-if="trend.series.length" ref="trendRef" class="chart"></div><div v-else class="chart-empty"><el-icon><TrendCharts /></el-icon><span>暂无可展示的时序信号</span></div></section>
      <section class="panel chart-panel"><div class="section-heading"><div><h2>热门技能需求</h2><p>来自 job_skill 技能明细</p></div></div><div v-if="skills.length" ref="skillsRef" class="chart"></div><div v-else class="chart-empty"><el-icon><DataAnalysis /></el-icon><span>暂无技能统计</span></div></section>
      <section class="panel source-panel"><div class="section-heading"><div><h2>数据状态</h2><p>当前接口不编造不可计算指标</p></div></div><div class="truth-list"><div><span>岗位定义</span><strong>{{ overview.totalJobs }}</strong><small>job_definition</small></div><div><span>解析简历</span><strong>{{ overview.totalResumes }}</strong><small>resume</small></div><div><span>匹配成功</span><strong>{{ overview.matchSuccess }}</strong><small>暂无持久化统计</small></div><div><span>技能缺口</span><strong>{{ overview.skillGaps }}</strong><small>暂无持久化统计</small></div></div><div class="honest-note"><el-icon><InfoFilled /></el-icon><span>准确率、薪资与新兴岗位数量暂未接入可信数据源，因此不在此页展示演示数字。</span></div></section>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import * as echarts from 'echarts'
import { DataAnalysis, InfoFilled, RefreshRight, TrendCharts } from '@element-plus/icons-vue'
import { getDashboardOverview, getDashboardTrend, getSkillDistribution, type DashboardOverview, type SkillDistItem } from '../api/dashboard'

interface TrendData { months: string[]; series: { name: string; color?: string; data: number[] }[] }
const loading = ref(false)
const overview = ref<DashboardOverview>({ totalJobs: 0, totalResumes: 0, matchSuccess: 0, skillGaps: 0, coralBlocks: [] })
const trend = ref<TrendData>({ months: [], series: [] })
const skills = ref<SkillDistItem[]>([])
const trendRef = ref<HTMLElement | null>(null)
const skillsRef = ref<HTMLElement | null>(null)
let trendChart: echarts.ECharts | null = null
let skillsChart: echarts.ECharts | null = null
const kpiCards = computed(() => [
  { label: '岗位总数', value: formatNumber(overview.value.totalJobs), note: '结构化岗位定义', icon: DataAnalysis, tone: 'coral' },
  { label: '解析简历', value: formatNumber(overview.value.totalResumes), note: '已持久化解析结果', icon: TrendCharts, tone: 'green' },
  { label: '技能种类', value: formatNumber(skills.value.length), note: '当前返回 Top 技能项', icon: DataAnalysis, tone: 'blue' },
  { label: '技术信号天数', value: formatNumber(trend.value.months.length), note: '按日期聚合', icon: TrendCharts, tone: 'orange' },
])
function formatNumber(value: number) { return new Intl.NumberFormat('zh-CN').format(value || 0) }
function initCharts() {
  trendChart?.dispose(); skillsChart?.dispose(); trendChart = null; skillsChart = null
  if (trendRef.value && trend.value.series.length) {
    trendChart = echarts.init(trendRef.value)
    trendChart.setOption({ color: ['#df8d70', '#83bc9a', '#6c9ac4', '#d6a15f', '#aa8fc4'], tooltip: { trigger: 'axis' }, legend: { top: 0, textStyle: { color: '#8f8985', fontSize: 11 } }, grid: { left: 42, right: 20, top: 38, bottom: 30 }, xAxis: { type: 'category', data: trend.value.months, axisLine: { lineStyle: { color: '#eee9e3' } }, axisLabel: { color: '#aaa39e', fontSize: 10 } }, yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f0ebe6' } }, axisLabel: { color: '#aaa39e', fontSize: 10 } }, series: trend.value.series.map(item => ({ name: item.name, type: 'line', smooth: true, symbol: 'circle', symbolSize: 5, data: item.data, lineStyle: { width: 2, color: item.color }, itemStyle: { color: item.color } })) })
  }
  if (skillsRef.value && skills.value.length) {
    skillsChart = echarts.init(skillsRef.value)
    const items = skills.value.slice(0, 10).reverse()
    skillsChart.setOption({ tooltip: { trigger: 'axis' }, grid: { left: 80, right: 24, top: 14, bottom: 28 }, xAxis: { type: 'value', splitLine: { lineStyle: { color: '#f0ebe6' } }, axisLabel: { color: '#aaa39e', fontSize: 10 } }, yAxis: { type: 'category', data: items.map(item => item.name), axisLabel: { color: '#7e7874', fontSize: 11 } }, series: [{ type: 'bar', data: items.map(item => item.count), barWidth: 12, itemStyle: { color: '#83bc9a', borderRadius: [0, 6, 6, 0] } }] })
  }
}
function resizeCharts() { trendChart?.resize(); skillsChart?.resize() }
async function loadData() { loading.value = true; try { const [o, t, s] = await Promise.all([getDashboardOverview(), getDashboardTrend(), getSkillDistribution()]); overview.value = o; trend.value = t || { months: [], series: [] }; skills.value = Array.isArray(s) ? s : []; await nextTick(); initCharts() } finally { loading.value = false } }
onMounted(() => { loadData(); window.addEventListener('resize', resizeCharts) })
onUnmounted(() => { window.removeEventListener('resize', resizeCharts); trendChart?.dispose(); skillsChart?.dispose() })
</script>
<style scoped>
.module-mark { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 14px; font-size: 23px; }.analytics-mark { color: #df8d70; background: #fbedE8; }.analytics-kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 16px; }.analytics-kpi { display: flex; align-items: center; gap: 14px; min-height: 106px; padding: 20px; background: #fff; border: 1px solid rgba(241,235,228,.8); border-radius: 16px; box-shadow: var(--shadow); }.kpi-icon { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 50%; font-size: 20px; }.kpi-icon.coral { color: #df8d70; background: #fbedE8; }.kpi-icon.green { color: #78b58f; background: #eaf6ee; }.kpi-icon.blue { color: #6c9ac4; background: #edf4fb; }.kpi-icon.orange { color: #d19c5b; background: #fff5e7; }.analytics-kpi small, .analytics-kpi span { display: block; color: #a29d99; font-size: 11px; }.analytics-kpi strong { display: block; margin: 4px 0; color: var(--text); font-size: 23px; }.analytics-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; }.chart-wide { min-height: 360px; }.chart-panel { min-height: 360px; }.source-panel { min-height: 360px; }.chart { width: 100%; height: 270px; }.chart-empty { display: flex; height: 270px; align-items: center; justify-content: center; gap: 8px; color: #aaa39e; font-size: 12px; }.chart-empty .el-icon { color: #d4c9c1; font-size: 25px; }.truth-list { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.truth-list > div { padding: 15px; border-radius: 12px; background: var(--card-soft); }.truth-list span, .truth-list strong, .truth-list small { display: block; }.truth-list span { color: #9d9793; font-size: 11px; }.truth-list strong { margin: 5px 0; color: var(--text); font-size: 23px; }.truth-list small { color: #b4ada8; font-size: 10px; }.honest-note { display: flex; gap: 7px; margin-top: 16px; padding: 11px 12px; border-radius: 10px; background: #fff8ed; color: #a17b45; font-size: 11px; line-height: 1.6; }.honest-note .el-icon { flex: 0 0 auto; margin-top: 2px; }
@media (max-width: 1100px) { .analytics-kpi-grid { grid-template-columns: repeat(2, 1fr); }.analytics-grid { grid-template-columns: 1fr; } } @media (max-width: 620px) { .analytics-kpi-grid, .truth-list { grid-template-columns: 1fr; }.analytics-kpi { min-height: 88px; }.chart { height: 240px; } }
</style>