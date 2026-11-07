<template>
  <section class="page evolution-page">
    <div class="page-title"><div class="title-left"><div class="module-mark evolution-mark"><el-icon><TrendCharts /></el-icon></div><div><h1>能力动态更新</h1><p>岗位档案与研究历史；解释变化不等于市场需求变化</p></div></div><el-button class="btn-soft" @click="loadData"><el-icon><RefreshRight /></el-icon>刷新记录</el-button></div>
    <section class="panel research-panel">
      <h2>M2 研究版本比较</h2><p>显式选择两个已保存运行，按来源身份比较原文、机器分析、知识解释及研究候选。缺少可比结果时保留未知。</p>
      <div class="research-controls">
        <el-select v-model="beforeRun" placeholder="选择较早运行" aria-label="较早运行" filterable @change="clearComparison"><el-option v-for="run in researchRuns" :key="run.run_id" :value="run.run_id" :label="runLabel(run)" /></el-select>
        <el-select v-model="afterRun" placeholder="选择较新运行" aria-label="较新运行" filterable @change="clearComparison"><el-option v-for="run in researchRuns" :key="run.run_id" :value="run.run_id" :label="runLabel(run)" /></el-select>
        <el-button :loading="comparisonLoading" :disabled="!beforeRun || !afterRun || beforeRun === afterRun" @click="compareResearch">比较所选版本</el-button>
      </div>
      <p v-if="researchError" role="alert">{{ researchError }}</p><p v-else-if="!researchRuns.length">暂无新版运行。可从岗位分析工作台显式创建任务。</p>
      <div v-if="comparison" class="research-result">
        <p>{{ comparison.interpretation }}</p><p class="version-text">{{ comparison.before_run }}（{{ comparison.before_created_at || '时间未知' }}） → {{ comparison.after_run }}（{{ comparison.after_created_at || '时间未知' }}）</p>
        <p class="version-text">请求摘要：{{ comparison.before_request_sha256 }} → {{ comparison.after_request_sha256 }}</p>
        <article v-for="item in comparison.items" :key="item.namespace + item.jd_id" class="record-card">
          <strong>{{ item.namespace }} / {{ item.jd_id }}</strong><p v-if="!item.source_comparable">只存在于一个运行，不能推断新增或删除招聘要求。</p>
          <details v-for="layer in item.layers" :key="layer.kind"><summary>{{ layerLabel(layer.kind) }} · {{ differenceLabel(layer) }}</summary><div class="difference-grid"><div><h4>之前</h4><pre>{{ valueText(layer.before) }}</pre></div><div><h4>之后</h4><pre>{{ valueText(layer.after) }}</pre></div></div></details>
        </article>
        <details><summary>工作候选研究 · {{ differenceLabel(comparison.research) }}</summary><div class="difference-grid"><pre>{{ valueText(comparison.research.before) }}</pre><pre>{{ valueText(comparison.research.after) }}</pre></div></details>
        <details><summary>研究原因与原版本绑定</summary><div class="difference-grid"><pre>{{ valueText({ binding: comparison.research.before_binding, causes: comparison.research.before_causes }) }}</pre><pre>{{ valueText({ binding: comparison.research.after_binding, causes: comparison.research.after_causes }) }}</pre></div></details>
      </div>
    </section>
    <div class="evolution-layout">
      <aside class="panel job-picker" v-loading="loading">
        <div class="section-heading"><div><h2>岗位画像</h2><p>{{ jobsLoaded ? `共 ${total} 个岗位画像` : '岗位数量待加载' }}</p></div></div>
        <p v-if="jobsError" role="alert">{{ jobsError }}<el-button link @click="loadJobs">重试</el-button></p><p v-else-if="jobsLoaded && !jobs.length">暂无岗位</p>
        <el-input v-model="keyword" placeholder="搜索岗位、技能或职责" clearable @keyup.enter="search" />
        <div class="job-list"><button v-for="job in jobs" :key="job.id" type="button" :class="{ active: selectedJobId === job.id }" @click="selectJob(job.id)"><span>{{ job.title }}</span><small>{{ job.name_en }}</small></button></div>
        <el-pagination :disabled="loading || !jobsLoaded" :current-page="page" @current-change="changePage" :page-size="pageSize" :total="total" layout="prev, pager, next" :pager-count="5" small />
      </aside>
      <main class="panel evolution-main">
        <div class="section-heading"><div><h2>{{ selectedJob?.title || '请选择岗位' }}</h2><p>档案编辑与历史记录 · 记录条数不是岗位版本</p></div><el-tag v-if="timeline" effect="plain">{{ timeline.total_changes }} 条记录</el-tag></div>
        <div v-if="timelineLoading" class="empty-state" role="status">正在加载能力变更记录…</div>
        <div v-else-if="timelineError" class="empty-state" role="alert"><h3>能力变更记录加载失败</h3><p>{{ timelineError }}</p><el-button @click="selectJob(selectedJobId)">重试</el-button></div>
        <div v-else-if="timeline?.records?.length" class="record-list">
          <article v-for="record in timeline.records" :key="record.id" class="record-card">
            <div class="record-heading"><strong>{{ recordTitle(record) }}</strong><el-tag effect="plain">{{ natureLabel(record.change_nature) }}</el-tag></div>
            <p>{{ record.reason || '变更原因未记录' }}</p><p>记录时间：{{ record.created_at || '未知' }} · 来源观察时间：{{ record.source_jd_time || '未知' }}</p><p>来源：{{ record.source || '未记录' }}</p>
            <p class="version-text">版本：{{ record.previous_version || '未知' }} → {{ record.version || '未知' }}</p>
            <div v-if="record.comparison_available" class="difference-grid"><div><h4>之前</h4><pre>{{ valueText(record.before) }}</pre></div><div><h4>之后</h4><pre>{{ valueText(record.after) }}</pre></div></div>
            <p v-else>未保存可比较的前后值，不能推断变化内容。</p>
            <details><summary>原始记录与来源核验</summary><pre>{{ valueText({ detail: record.detail, provenance: record.provenance }) }}</pre></details>
          </article>
        </div>
        <div v-else class="empty-state"><el-icon :size="42"><TrendCharts /></el-icon><h3>{{ timeline ? '暂无能力变更记录' : '请选择岗位' }}</h3><p>{{ timeline ? '尚无保存的变更记录。' : '从左侧选择岗位查看能力动态。' }}</p></div>
      </main>
    </div>
  </section>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { RefreshRight, TrendCharts } from '@element-plus/icons-vue'
import { getJobEvolutionTimeline, compareDeliveryRuns, type EvolutionTimeline, type RunComparison, type ComparisonLayer } from '../api/evolution'
import { getDeliveryRuns, type DeliveryHistory } from '../api/m2'
import { useRoute } from 'vue-router'
import { type Job } from '../api/jobs'
import { usePagedJobs } from '../composables/usePagedJobs'
const route = useRoute()
const pageSize = 20
const { jobs, total, page, keyword, loading, loaded: jobsLoaded, error: jobsError, load: loadJobs, changePage, search } = usePagedJobs(pageSize)
const selectedJobId = ref(''); const selectedJob = ref<Job | undefined>(); const timeline = ref<EvolutionTimeline | null>(null)
const timelineError = ref(''); const timelineLoading = ref(false)
let disposed = false, timelineRequest = 0, comparisonRequest = 0, researchRequest = 0
const researchRuns = ref<DeliveryHistory[]>([]), beforeRun = ref(''), afterRun = ref(typeof route.query.run === 'string' ? route.query.run : '')
const comparison = ref<RunComparison | null>(null), researchError = ref(''), comparisonLoading = ref(false)
function valueText(value: unknown) { return value == null ? '未记录 / 不适用' : typeof value === 'string' ? value : JSON.stringify(value, null, 2) }
function natureLabel(value:string) { return ({ profile_edit:'岗位档案编辑', historical_demo:'历史演示（非市场事实）', unverified_history:'历史来源性质待核实' } as Record<string,string>)[value] || '来源性质待核实' }
function layerLabel(value:string) { return ({ input:'原文观察', analysis:'机器分析（含模型版本与证据）', knowledge:'知识解释', skill_governance:'技能候选有效投影' } as Record<string,string>)[value] || value }
function differenceLabel(layer:ComparisonLayer) { return !layer.available ? '缺少可比结果' : layer.changed ? '保存值不同' : '保存值相同' }
function runLabel(run:DeliveryHistory) { return `${run.created_at || '时间未知'} · ${run.run_id}` }
function clearComparison() { ++comparisonRequest; comparison.value = null; comparisonLoading.value = false; researchError.value = '' }
watch(() => route.query.run, id => { if (typeof id === 'string') { afterRun.value = id; clearComparison() } })
async function loadResearchRuns() {
  const request = ++researchRequest
  try { const runs = await getDeliveryRuns(); if (!disposed && request === researchRequest) { researchRuns.value = runs; researchError.value = '' } }
  catch { if (!disposed && request === researchRequest) researchError.value = '新版运行读取失败，请检查本地访问配置并刷新。' }
}
async function compareResearch() {
  if (!beforeRun.value || !afterRun.value || beforeRun.value === afterRun.value) return
  const request = ++comparisonRequest, before = beforeRun.value, after = afterRun.value
  comparison.value = null; researchError.value = ''; comparisonLoading.value = true
  try { const result = await compareDeliveryRuns(before, after); if (!disposed && request === comparisonRequest && before === beforeRun.value && after === afterRun.value) comparison.value = result }
  catch { if (!disposed && request === comparisonRequest) researchError.value = '所选版本比较失败，未切换到其他历史结果。' }
  finally { if (!disposed && request === comparisonRequest) comparisonLoading.value = false }
}
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
  await Promise.all([loadResearchRuns(), loadJobs(), selectedJobId.value ? selectJob(selectedJobId.value) : Promise.resolve()])
}
onMounted(loadData)
onUnmounted(() => { disposed = true; ++timelineRequest; ++comparisonRequest; ++researchRequest })
</script>
<style scoped>
.research-panel { margin-top:24px; }.research-controls { display:flex; gap:12px; flex-wrap:wrap; }.research-controls .el-select { min-width:240px; flex:1; }.research-result { margin-top:16px; }.difference-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; min-width:0; }.difference-grid > div { min-width:0; }pre { white-space:pre-wrap; overflow-wrap:anywhere; max-height:360px; overflow:auto; background:var(--card-soft); padding:12px; font-size:12px; }.record-heading { display:flex; justify-content:space-between; gap:12px; }.version-text { overflow-wrap:anywhere; }details { width:100%; margin-top:10px; }summary { cursor:pointer; }h4 { margin-bottom:6px; }

.module-mark { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 14px; font-size: 23px; }.evolution-mark { color: #3646b6; background: #edf0ff; }.evolution-layout { display: grid; margin-top: 24px; grid-template-columns: 310px 1fr; gap: 16px; align-items: start; }.job-picker { min-height: 620px; }.job-list { display: grid; gap: 5px; max-height: 520px; margin-top: 14px; overflow: auto; }.job-list button { display: flex; flex-direction: column; gap: 3px; padding: 11px 12px; border: 0; border-radius: 10px; background: transparent; color: #555; text-align: left; }.job-list button:hover, .job-list button.active { background: #edf0ff; color: var(--primary-deep); box-shadow: inset 3px 0 0 var(--purple); }.job-list small { color: #69808E; font-size: 10px; }.evolution-main { min-height: 620px; }.record-list { display: grid; gap: 10px; }.record-card { display: flex; flex-direction:column; align-items: stretch; gap: 14px; padding: 16px; border: 1px solid var(--line); border-radius: 12px; background: var(--card-soft); }.record-card strong { font-size: 14px; }.record-card p { margin: 7px 0 0; color: #69808E; font-size: 12px; line-height: 1.6; }.empty-state { min-height: 420px; }.empty-state .el-icon { color: #D9E2E7; }
@media (max-width: 900px) { .difference-grid { grid-template-columns:1fr; } .evolution-layout { grid-template-columns: 1fr; }.job-picker { min-height: auto; }.job-list { max-height: 260px; } }
</style>

