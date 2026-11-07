<template>
  <section class="page evolution-page">
    <div class="page-title"><div class="title-left"><div class="module-mark evolution-mark"><el-icon><TrendCharts /></el-icon></div><div><h1>能力动态更新</h1><p>追踪岗位能力变化、变更依据和数据来源</p></div></div><el-button class="btn-soft" @click="loadData"><el-icon><RefreshRight /></el-icon>刷新记录</el-button></div>
    <div class="evolution-layout">
      <aside class="panel job-picker" v-loading="loading"><div class="section-heading"><div><h2>岗位列表</h2><p>{{ jobsLoaded ? `共 ${total} 个结构化岗位` : '岗位数量待加载' }}</p></div></div><p v-if="jobsError" role="alert">{{ jobsError }}<el-button link @click="loadJobs">重试</el-button></p><p v-else-if="jobsLoaded && !jobs.length">暂无岗位</p><el-input v-model="keyword" placeholder="搜索岗位、技能或职责" clearable @keyup.enter="search" /><div class="job-list"><button v-for="job in jobs" :key="job.id" type="button" :class="{ active: selectedJobId === job.id }" @click="selectJob(job.id)"><span>{{ job.title }}</span><small>{{ job.name_en }}</small></button></div><el-pagination :disabled="loading || !jobsLoaded" :current-page="page" @current-change="changePage" :page-size="pageSize" :total="total" layout="prev, pager, next" :pager-count="5" small /></aside>
      <main class="panel evolution-main"><div class="section-heading"><div><h2>{{ selectedJob?.title || '请选择岗位' }}</h2><p>能力变更审计记录 · 只展示可追溯数据</p></div><el-tag v-if="timeline" effect="plain">{{ timeline.total_changes }} 次变更</el-tag></div><div v-if="timelineLoading" class="empty-state" role="status">正在加载能力变更记录…</div><div v-else-if="timelineError" class="empty-state" role="alert"><h3>能力变更记录加载失败</h3><p>{{ timelineError }}</p><el-button @click="selectJob(selectedJobId)">重试</el-button></div><div v-else-if="timeline?.records?.length" class="record-list"><article v-for="record in timeline.records" :key="record.id" class="record-card"><div><strong>{{ recordTitle(record) }}</strong><p>{{ record.reason || record.source || '暂无说明' }}</p></div><el-tag effect="plain">{{ changeTypeLabel(record.change_type) }}</el-tag></article></div><div v-else class="empty-state"><el-icon :size="42"><TrendCharts /></el-icon><h3>{{ timeline ? '暂无能力变更记录' : '请选择岗位' }}</h3><p>{{ timeline ? '当前 job_change_log 没有可展示的数据，页面不会使用演示内容填充。' : '从左侧选择岗位查看能力动态。' }}</p></div></main>
    </div>
  </section>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { RefreshRight, TrendCharts } from '@element-plus/icons-vue'
import { getJobEvolutionTimeline, type EvolutionTimeline } from '../api/evolution'
import { type Job } from '../api/jobs'
import { usePagedJobs } from '../composables/usePagedJobs'
const pageSize = 20
const { jobs, total, page, keyword, loading, loaded: jobsLoaded, error: jobsError, load: loadJobs, changePage, search } = usePagedJobs(pageSize)
const selectedJobId = ref(''); const selectedJob = ref<Job | undefined>(); const timeline = ref<EvolutionTimeline | null>(null)
const timelineError = ref(''); const timelineLoading = ref(false)
let disposed = false, timelineRequest = 0
const CHANGE_TYPE_LABELS: Record<string, string> = { added: '新增技能', removed: '移除技能', modified: '技能调整', duties_changed: '职责变化', scenarios_added: '新增应用场景', scenarios_removed: '移除应用场景', evolution_changed: '演化阶段变化' }
const META_SKILL_NAMES = ['core_duties', 'stage']
function changeTypeLabel(type?: string) { return (type && CHANGE_TYPE_LABELS[type]) || type || '变更' }
function recordTitle(record: { change_type?: string; skill_name?: string }) { const name = record.skill_name; return (name && !META_SKILL_NAMES.includes(name)) ? `${changeTypeLabel(record.change_type)}：${name}` : changeTypeLabel(record.change_type) }
watch(jobs, rows => {
  if (!jobsLoaded.value) return
  const current = rows.find(job => job.id === selectedJobId.value)
  if (current) { selectedJob.value = current; return }
  if (rows[0]) { void selectJob(rows[0].id); return }
  ++timelineRequest; selectedJobId.value = ''; selectedJob.value = undefined
  timeline.value = null; timelineError.value = ''; timelineLoading.value = false
})
async function selectJob(id: string) {
  if (!id) return
  const request = ++timelineRequest
  selectedJob.value = jobs.value.find(job => job.id === id) || selectedJob.value
  selectedJobId.value = id; timeline.value = null; timelineError.value = ''; timelineLoading.value = true
  try {
    const result = await getJobEvolutionTimeline(id)
    if (!disposed && request === timelineRequest && selectedJobId.value === id) timeline.value = result
  } catch {
    if (!disposed && request === timelineRequest) timelineError.value = '请求失败，请稍后重试。'
  } finally {
    if (!disposed && request === timelineRequest) timelineLoading.value = false
  }
}
async function loadData() {
  await Promise.all([loadJobs(), selectedJobId.value ? selectJob(selectedJobId.value) : Promise.resolve()])
}
onMounted(loadData)
onUnmounted(() => { disposed = true; ++timelineRequest })
</script>
<style scoped>
.module-mark { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 14px; font-size: 23px; }.evolution-mark { color: #3646b6; background: #edf0ff; }.evolution-layout { display: grid; margin-top: 24px; grid-template-columns: 310px 1fr; gap: 16px; align-items: start; }.job-picker { min-height: 620px; }.job-list { display: grid; gap: 5px; max-height: 520px; margin-top: 14px; overflow: auto; }.job-list button { display: flex; flex-direction: column; gap: 3px; padding: 11px 12px; border: 0; border-radius: 10px; background: transparent; color: #555; text-align: left; }.job-list button:hover, .job-list button.active { background: #edf0ff; color: var(--primary-deep); box-shadow: inset 3px 0 0 var(--purple); }.job-list small { color: #69808E; font-size: 10px; }.evolution-main { min-height: 620px; }.record-list { display: grid; gap: 10px; }.record-card { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; padding: 16px; border: 1px solid var(--line); border-radius: 12px; background: var(--card-soft); }.record-card strong { font-size: 14px; }.record-card p { margin: 7px 0 0; color: #69808E; font-size: 12px; line-height: 1.6; }.empty-state { min-height: 420px; }.empty-state .el-icon { color: #D9E2E7; }
@media (max-width: 900px) { .evolution-layout { grid-template-columns: 1fr; }.job-picker { min-height: auto; }.job-list { max-height: 260px; } }
</style>

