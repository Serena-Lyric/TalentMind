<template>
  <div class="dashboard">

    <header class="welcome-bar">
      <div class="welcome-left">
        <h1>岗位人才数据总览</h1>
        <p class="welcome-sub">统一采集全渠道JD岗位与简历数据，可视化分析岗位技能需求、人才匹配缺口</p>
      </div>
      <div class="welcome-right">
        <div class="time-pills">
          <button v-for="opt in timeOptions" :key="opt.value" class="pill-btn" :class="{ active: timeRange === opt.value }" @click="timeRange = opt.value">{{ opt.label }}</button>
        </div>
      </div>
    </header>

    <section class="stats-row" v-loading="dashboardLoading" element-loading-text="加载中...">
      <div v-for="(card, i) in statCards" :key="card.title" class="stat-card warm-card blueprint-card">
        <div class="stat-icon-circle" :style="{ background: card.iconBg }">
          <svg v-if="i===0" width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="3" y="8" width="16" height="12" rx="2" stroke="#247CA2" stroke-width="1.4" fill="none"/><path d="M7 8 V6 Q7 3 11 3 Q15 3 15 6 V8" stroke="#247CA2" stroke-width="1.4" fill="none"/><circle cx="11" cy="14" r="2" stroke="#247CA2" stroke-width="1" fill="#E6F1F5"/></svg>
          <svg v-else-if="i===1" width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="4" y="2" width="14" height="18" rx="2" stroke="#55B88D" stroke-width="1.4" fill="none"/><line x1="7" y1="7" x2="15" y2="7" stroke="#55B88D" stroke-width="1" opacity="0.6"/><line x1="7" y1="10" x2="13" y2="10" stroke="#55B88D" stroke-width="1" opacity="0.4"/><circle cx="11" cy="5" r="1.5" fill="#E7F5EF" stroke="#55B88D" stroke-width="0.8"/></svg>
          <svg v-else-if="i===2" width="22" height="22" viewBox="0 0 22 22" fill="none"><circle cx="8" cy="11" r="5" stroke="#D58A3D" stroke-width="1.4" fill="none"/><circle cx="14" cy="11" r="5" stroke="#D58A3D" stroke-width="1.4" fill="none"/><circle cx="11" cy="11" r="1.5" fill="#FFF3E5"/></svg>
          <svg v-else width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M11 3 L3 19 L19 19 Z" stroke="#D25B5B" stroke-width="1.4" fill="none" stroke-linejoin="round"/><line x1="11" y1="9" x2="11" y2="13" stroke="#D25B5B" stroke-width="1.4" stroke-linecap="round"/><circle cx="11" cy="16" r="1" fill="#D25B5B"/></svg>
        </div>
        <div class="stat-info"><span class="stat-label">{{ card.title }}</span><span class="stat-value">{{ animatedNums[i] }}</span></div>
        <span class="stat-badge" :style="{ background: card.badgeBg, color: card.badgeColor }">{{ card.trend }}</span>

      </div>
    </section>

    <!-- 珊瑚粉色块统计 - 横向排列 -->
    <section class="stat-blocks-row">
        <div class="coral-block" v-for="block in coralBlocks" :key="block.label"><span class="coral-num">{{ block.value }}</span><span class="coral-label">{{ block.label }}</span></div>
    </section>

    <section class="charts-row">
      <div class="warm-card chart-card">
        <div class="card-head"><div><h3>岗位能力趋势</h3><p>近6个月各岗位需求指数变化</p></div>
          <div class="metric-pills"><button v-for="m in metricOptions" :key="m.value" class="pill-btn sm" :class="{ active: lineMetric === m.value }" @click="lineMetric = m.value">{{ m.label }}</button></div>
        </div>
        <div ref="lineChartRef" class="chart-box"></div>
      </div>
      <div class="warm-card chart-card">
        <div class="card-head"><div><h3>岗位技能分布</h3><p>Top 8 核心技能覆盖率</p></div></div>
        <div ref="barChartRef" class="chart-box"></div>
      </div>
    </section>

    <section class="bottom-row">
      <div class="warm-card table-card">
        <div class="card-head"><div><h3>岗位列表</h3><p>共 {{ filteredJobs.length }} 个在招岗位</p></div><el-input v-model="jobSearch" placeholder="搜索岗位名称..." :prefix-icon="Search" clearable style="width:200px" size="small" /></div>
        <el-table :data="pagedJobs" style="width:100%" :header-cell-style="tblHeaderStyle" :cell-style="{ padding:'12px 0' }">
          <el-table-column prop="name" label="岗位名称" min-width="150"><template #default="{ row }"><span class="job-name">{{ row.name }}</span></template></el-table-column>
          <el-table-column prop="dept" label="部门" width="110" />
          <el-table-column prop="count" label="需求人数" width="90" align="center"><template #default="{ row }"><span class="count-badge" :class="row.count>=10?'hot':row.count>=5?'warm':'cool'">{{ row.count ? row.count + '人' : '—' }}</span></template></el-table-column>
          <el-table-column prop="salary" label="薪资范围" width="120" />
          <el-table-column prop="status" label="状态" width="90" align="center"><template #default="{ row }"><span class="status-dot" :class="row.status==='急聘'?'urgent':row.status==='招聘中'?'open':'pending'"></span>{{ row.status }}</template></el-table-column>
          <el-table-column prop="updateTime" label="更新时间" width="110" />
        </el-table>
        <div class="tbl-pagination"><el-pagination v-model:current-page="currentPage" :page-size="pageSize" :total="filteredJobs.length" layout="total, prev, pager, next" small /></div>
      </div>

      <div class="side-panels">
        <div class="warm-card side-card">
          <div class="card-head"><h3>待办日程</h3><span class="card-count">{{ scheduleItems.length }}</span></div>
          <div class="sched-list">
            <div v-for="item in scheduleItems" :key="item.id" class="sched-item" :class="item.level">
              <div class="sched-dot" :class="item.level"></div>
              <div class="sched-body"><span class="sched-title">{{ item.title }}</span><span class="sched-time">{{ item.time }}</span></div>
              <span class="sched-tag" :class="item.level">{{ item.tag }}</span>
            </div>
          </div>
        </div>
        <div class="warm-card side-card">
          <div class="card-head"><h3>待分析任务</h3><span class="card-count">{{ pendingCount }}</span></div>
          <div class="task-list">
            <div v-for="task in taskItems" :key="task.id" class="task-item"><el-checkbox v-model="task.done" /><div class="task-body"><span :class="{ done: task.done }">{{ task.title }}</span><span class="task-deadline">{{ task.deadline }}</span></div></div>
          </div>
        </div>
        <div class="create-card" @click="$router.push('/jobs')">
          <div class="create-inner">
            <div class="create-icon-wrap"><el-icon :size="24"><Plus /></el-icon></div>
            <span>创建新岗位分析</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, reactive } from 'vue'
import { Search, User, Document, DataAnalysis, Trophy, Plus } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getDashboardOverview, getDashboardTrend, getSkillDistribution } from '../api/dashboard'
import { getJobList } from '../api/jobs'

const dashboardLoading = ref(true)
const timeRange = ref<'day' | 'week' | 'month'>('month')
const lineMetric = ref<'demand' | 'salary'>('demand')
const jobSearch = ref('')
const currentPage = ref(1)
const pageSize = 8
const timeOptions = [{ label: '日', value: 'day' as const }, { label: '周', value: 'week' as const }, { label: '月', value: 'month' as const }]
const metricOptions = [{ label: '需求指数', value: 'demand' as const }, { label: '薪资水平', value: 'salary' as const }]
const statCards = reactive([
  { title: '岗位总数', value: 0, trend: '—', iconBg: '#E6F1F5', iconColor: '#247CA2', icon: DataAnalysis, badgeBg: '#E6F1F5', badgeColor: '#D25B5B' },
  { title: '解析简历数', value: 0, trend: '—', iconBg: '#E7F5EF', iconColor: '#55B88D', icon: Document, badgeBg: '#E7F5EF', badgeColor: '#55B88D' },
  { title: '匹配成功数', value: 0, trend: '—', iconBg: '#FFF3E5', iconColor: '#D58A3D', icon: Trophy, badgeBg: '#FFF3E5', badgeColor: '#D58A3D' },
  { title: '技能缺口数', value: 0, trend: '—', iconBg: '#FAECEC', iconColor: '#D25B5B', icon: User, badgeBg: '#FAECEC', badgeColor: '#D25B5B' },
])
const coralBlocks = ref<{ value: number | string; label: string }[]>([])
const animatedNums = ref([0, 0, 0, 0])
let animTimer: ReturnType<typeof setInterval> | null = null

function animateNumbers() {
  if (animTimer) clearInterval(animTimer)
  const targets = statCards.map(card => card.value)
  let step = 0
  animTimer = setInterval(() => {
    step += 1
    const progress = Math.min(step / 40, 1)
    const ease = 1 - Math.pow(1 - progress, 3)
    animatedNums.value = targets.map(target => Math.round(target * ease))
    if (step >= 40 && animTimer) {
      animatedNums.value = targets
      clearInterval(animTimer)
      animTimer = null
    }
  }, 30)
}

const lineChartRef = ref<HTMLElement>()
const barChartRef = ref<HTMLElement>()
let lineChart: echarts.ECharts | null = null
let barChart: echarts.ECharts | null = null
const months = ref<string[]>([])
const trendSeries = ref<{ name: string; color?: string; data: number[] }[]>([])
const barSkills = ref<string[]>([])
const barValues = ref<number[]>([])

function getLineOption() {
  return {
    title: { show: !months.value.length, text: '暂无趋势数据', left: 'center', top: 'middle', textStyle: { color: '#B0B0B0', fontSize: 13, fontWeight: 400 } },
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#D9E2E7', textStyle: { color: '#3D3D3D', fontSize: 12 }, borderRadius: 12 },
    legend: { bottom: 0, textStyle: { color: '#999', fontSize: 11 }, itemWidth: 14, itemHeight: 6, itemGap: 14 },
    grid: { top: 16, right: 16, bottom: 44, left: 44 },
    xAxis: { type: 'category', data: months.value, axisLine: { lineStyle: { color: '#D9E2E7' } }, axisTick: { show: false }, axisLabel: { color: '#999', fontSize: 11 } },
    yAxis: { type: 'value', axisLabel: { color: '#999', fontSize: 11 }, splitLine: { lineStyle: { color: '#F8FAFB', type: 'dashed' } } },
    series: trendSeries.value.map((series, index) => ({ name: series.name, type: 'line', data: series.data, smooth: 0.4, symbol: 'circle', symbolSize: 5, lineStyle: { width: 2, color: series.color || ['#247CA2', '#55B88D', '#D58A3D', '#2F6FCE'][index % 4] }, itemStyle: { color: series.color || ['#247CA2', '#55B88D', '#D58A3D', '#2F6FCE'][index % 4] } })),
  }
}

function getBarOption() {
  return {
    title: { show: !barSkills.value.length, text: '暂无技能分布数据', left: 'center', top: 'middle', textStyle: { color: '#B0B0B0', fontSize: 13, fontWeight: 400 } },
    tooltip: { trigger: 'axis' },
    grid: { top: 10, right: 32, bottom: 18, left: 76 },
    xAxis: { type: 'value', max: 100, axisLabel: { color: '#999', fontSize: 10 }, splitLine: { lineStyle: { color: '#F8FAFB', type: 'dashed' } } },
    yAxis: { type: 'category', data: [...barSkills.value].reverse(), axisLabel: { color: '#777', fontSize: 11 } },
    series: [{ type: 'bar', data: [...barValues.value].reverse(), barWidth: 12, itemStyle: { borderRadius: [0, 8, 8, 0], color: new echarts.graphic.LinearGradient(1, 0, 0, 0, [{ offset: 0, color: '#247CA2' }, { offset: 1, color: '#55B88D' }]) }, label: { show: true, position: 'right', color: '#888', fontSize: 10, formatter: '{c}%' } }],
  }
}

interface JobRow { id: string; name: string; dept: string; count: number; salary: string; status: string; updateTime: string }
const allJobs = ref<JobRow[]>([])
const filteredJobs = computed(() => jobSearch.value ? allJobs.value.filter(job => job.name.toLowerCase().includes(jobSearch.value.trim().toLowerCase())) : allJobs.value)
const pagedJobs = computed(() => { const start = (currentPage.value - 1) * pageSize; return filteredJobs.value.slice(start, start + pageSize) })
const tblHeaderStyle = { background: '#F8FAFB', color: '#8C8C8C', fontWeight: '500', fontSize: '12px', borderBottom: '1px solid #D9E2E7' }

interface ScheduleItem { id: number; title: string; time: string; tag: string; level: 'urgent' | 'normal' | 'low' }
const scheduleItems = ref<ScheduleItem[]>([])
interface TaskItem { id: number; title: string; deadline: string; done: boolean }
const taskItems = ref<TaskItem[]>([])
const pendingCount = computed(() => taskItems.value.filter(task => !task.done).length)

function initCharts() {
  if (lineChartRef.value) { lineChart = echarts.init(lineChartRef.value); lineChart.setOption(getLineOption()) }
  if (barChartRef.value) { barChart = echarts.init(barChartRef.value); barChart.setOption(getBarOption()) }
}
function refreshCharts() {
  lineChart?.setOption(getLineOption(), true)
  barChart?.setOption(getBarOption(), true)
}
function handleResize() { lineChart?.resize(); barChart?.resize() }

async function loadDashboardData() {
  dashboardLoading.value = true
  try {
    const [overview, trend, distribution, jobs] = await Promise.all([
      getDashboardOverview(),
      getDashboardTrend(timeRange.value),
      getSkillDistribution(),
      getJobList({ page: 1, page_size: 100 }),
    ])
    if (overview) {
      statCards[0].value = Number(overview.totalJobs || 0)
      statCards[1].value = Number(overview.totalResumes || 0)
      statCards[2].value = Number(overview.matchSuccess || 0)
      statCards[3].value = Number(overview.skillGaps || 0)
      coralBlocks.value = (overview.coralBlocks || []).map(block => ({ label: block.label, value: block.value }))
      animateNumbers()
    }
    months.value = Array.isArray(trend?.months) ? trend.months : []
    trendSeries.value = Array.isArray(trend?.series) ? trend.series : []
    const dist = Array.isArray(distribution) ? distribution : []
    barSkills.value = dist.slice(0, 8).map(item => item.name)
    barValues.value = dist.slice(0, 8).map(item => Number(item.percentage || 0))
    allJobs.value = (jobs?.list || []).map(job => ({
      id: String(job.id), name: job.title, dept: job.company || '—', count: 0,
      salary: job.salary || '—', status: job.status === 'open' ? '招聘中' : job.status || '—', updateTime: job.updated || '—',
    }))
    refreshCharts()
  } catch (error) {
    console.error('加载看板数据失败:', error)
  } finally {
    dashboardLoading.value = false
  }
}

watch(timeRange, loadDashboardData)
watch(lineMetric, refreshCharts)
onMounted(async () => { initCharts(); window.addEventListener('resize', handleResize); await loadDashboardData() })
onUnmounted(() => { window.removeEventListener('resize', handleResize); lineChart?.dispose(); barChart?.dispose(); if (animTimer) clearInterval(animTimer) })
</script>
<style scoped>
.dashboard {
  --coral: var(--primary);
  --coral-light: var(--primary-soft);
  --green: var(--green);
  --green-light: var(--green-soft);
  --orange: var(--orange);
  --orange-light: var(--orange-soft);
  --red: var(--danger);
  --red-light: var(--danger-soft);
  --text: var(--text);
  --text-sec: var(--muted-strong);
  --text-muted: var(--muted);
  --bg: var(--card-soft);
  --card-bg: var(--card);
  --border: var(--line);
  --radius: 8px;
  position: relative;
}
.welcome-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
  padding: 18px 20px;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.welcome-left h1 { margin: 0 0 5px; font-size: 22px; font-weight: 650; }
.welcome-sub { margin: 0; color: var(--muted); font-size: 11px; }
.welcome-right { display: flex; align-items: center; gap: 12px; }
.time-pills, .metric-pills {
  display: inline-flex;
  padding: 3px;
  gap: 2px;
  background: var(--card-soft);
  border: 1px solid var(--line);
  border-radius: 6px;
}
.pill-btn {
  min-width: 46px;
  padding: 5px 10px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--muted-strong);
  font-size: 10px;
}
.pill-btn.active {
  color: var(--primary-deep);
  background: var(--card);
  box-shadow: 0 0 0 1px var(--line);
}
.stats-row, .stat-blocks-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 14px;
}
.stat-card {
  min-height: 124px;
  padding: 19px;
  position: relative;
}
.stat-icon-circle {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 7px;
}
.stat-title { display: block; margin-top: 11px; color: var(--muted); font-size: 10px; }
.stat-num {
  display: block;
  margin-top: 3px;
  color: var(--text);
  font-size: 23px;
  font-weight: 650;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}
.stat-badge {
  position: absolute;
  top: 17px;
  right: 17px;
  padding: 2px 7px;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: var(--card-soft);
  color: var(--muted-strong);
  font-size: 9px;
  font-weight: 500;
}
.coral-block {
  min-width: 90px;
  padding: 13px 18px;
  color: #fff;
  background: var(--primary);
  border: 1px solid var(--primary);
  border-radius: 6px;
  text-align: center;
}
.coral-num { display: block; margin-bottom: 2px; font-size: 23px; font-weight: 650; line-height: 1.1; }
.coral-label { font-size: 10px; opacity: .82; }
.charts-row { display: grid; grid-template-columns: 1.4fr 1fr; gap: 14px; margin-bottom: 14px; }
.chart-card { padding: 20px; }
.chart-box { width: 100%; height: 276px; }
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}
.card-head h3 { margin: 0 0 3px; color: var(--text); font-size: 14px; font-weight: 650; }
.card-head p { margin: 0; color: var(--muted); font-size: 10px; }
.card-count {
  padding: 2px 7px;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: var(--primary-soft);
  color: var(--primary);
  font-size: 9px;
  font-weight: 600;
}
.bottom-row { display: grid; grid-template-columns: 1.6fr 1fr; gap: 14px; }
.table-card { padding: 20px; }
:deep(.el-table) {
  --el-table-border-color: var(--line);
  --el-table-tr-bg-hover: var(--primary-soft);
  --el-table-header-bg-color: var(--card-soft);
  background: transparent;
  font-size: 11px;
}
:deep(.el-table th.el-table__cell) {
  background: var(--card-soft) !important;
  border-bottom: 1px solid var(--line);
}
.job-name { color: var(--text); font-size: 12px; font-weight: 550; }
.count-badge {
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 500;
}
.count-badge.hot { color: var(--primary); background: var(--primary-soft); }
.count-badge.warm { color: var(--orange); background: var(--orange-soft); }
.count-badge.cool { color: var(--muted); background: var(--card-soft); }
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 6px;
  border-radius: 50%;
  vertical-align: middle;
}
.status-dot.urgent { background: var(--primary); }
.status-dot.open { background: var(--green); }
.status-dot.pending { background: var(--muted); }
.tbl-pagination { display: flex; justify-content: flex-end; margin-top: 12px; }
.side-panels { display: flex; flex-direction: column; gap: 14px; }
.side-card { padding: 18px; }
.sched-list { display: flex; flex-direction: column; gap: 8px; }
.sched-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 11px;
  background: var(--card-soft);
  border: 1px solid transparent;
  border-radius: 6px;
}
.sched-item:hover { background: var(--primary-soft); border-color: var(--line); }
.sched-item.urgent { border-left: 3px solid var(--primary); }
.sched-item.normal { border-left: 3px solid var(--orange); }
.sched-item.low { border-left: 3px solid var(--green); }
.sched-dot { width: 6px; height: 6px; flex-shrink: 0; border-radius: 50%; }
.sched-dot.urgent { background: var(--primary); }
.sched-dot.normal { background: var(--orange); }
.sched-dot.low { background: var(--green); }
.sched-body { flex: 1; min-width: 0; }
.sched-title { display: block; margin-bottom: 1px; color: var(--text); font-size: 11px; font-weight: 550; }
.sched-time { color: var(--muted); font-size: 9px; }
.sched-tag {
  flex-shrink: 0;
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 9px;
  font-weight: 500;
}
.sched-tag.urgent { color: var(--primary); background: var(--primary-soft); }
.sched-tag.normal { color: var(--orange); background: var(--orange-soft); }
.sched-tag.low { color: var(--green); background: var(--green-soft); }
.task-list { display: flex; flex-direction: column; gap: 6px; }
.task-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 9px;
  border-radius: 5px;
}
.task-item:hover { background: var(--card-soft); }
.task-body { flex: 1; min-width: 0; }
.task-body span:first-child { display: block; color: var(--text); font-size: 11px; }
.task-body span.done { color: var(--muted); text-decoration: line-through; }
.task-deadline { color: var(--muted); font-size: 9px; }
.create-card {
  padding: 24px;
  cursor: pointer;
  background: var(--card);
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  text-align: center;
}
.create-card:hover { border-color: var(--primary); background: var(--primary-soft); }
.create-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 7px;
  color: var(--muted-strong);
  font-size: 11px;
}
.create-inner .el-icon { color: var(--primary); }
.create-icon-wrap { display: flex; align-items: center; justify-content: center; }
@media (max-width: 1200px) {
  .stats-row, .stat-blocks-row { grid-template-columns: repeat(2, 1fr); }
  .charts-row, .bottom-row { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .stats-row, .stat-blocks-row { grid-template-columns: 1fr; }
  .welcome-bar { align-items: flex-start; flex-direction: column; }
}
</style>