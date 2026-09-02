<template>
  <section class="page evolution-page" v-loading="loading">
    <div class="page-title"><div class="title-left"><div class="module-mark evolution-mark"><el-icon><TrendCharts /></el-icon></div><div><h1>能力动态更新</h1><p>追踪岗位能力变化、变更依据和数据来源</p></div></div><el-button class="btn-soft" @click="loadData"><el-icon><RefreshRight /></el-icon>刷新记录</el-button></div>
    <div class="evolution-layout">
      <aside class="panel job-picker"><div class="section-heading"><div><h2>岗位列表</h2><p>{{ jobs.length }} 个结构化岗位</p></div></div><el-input v-model="keyword" placeholder="搜索岗位" clearable /><div class="job-list"><button v-for="job in filteredJobs" :key="job.id" type="button" :class="{ active: selectedJobId === job.id }" @click="selectJob(job.id)"><span>{{ job.title }}</span><small>{{ job.name_en }}</small></button></div></aside>
      <main class="panel evolution-main"><div class="section-heading"><div><h2>{{ selectedJob?.title || '请选择岗位' }}</h2><p>能力变更审计记录 · 只展示可追溯数据</p></div><el-tag v-if="timeline" effect="plain">{{ timeline.total_changes }} 次变更</el-tag></div><div v-if="timeline?.records?.length" class="record-list"><article v-for="record in timeline.records" :key="record.id" class="record-card"><div><strong>{{ record.summary || '能力变更记录' }}</strong><p>{{ record.reason || record.source || '暂无说明' }}</p></div><el-tag effect="plain">{{ record.change_type || '变更' }}</el-tag></article></div><div v-else class="empty-state"><el-icon :size="42"><TrendCharts /></el-icon><h3>{{ selectedJob ? '暂无能力变更记录' : '请选择岗位' }}</h3><p>{{ selectedJob ? '当前 job_change_log 没有可展示的数据，页面不会使用演示内容填充。' : '从左侧选择岗位查看能力动态。' }}</p></div></main>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RefreshRight, TrendCharts } from '@element-plus/icons-vue'
import { getJobEvolutionTimeline, type EvolutionTimeline } from '../api/evolution'
import { getJobList, type Job } from '../api/jobs'
const loading = ref(false); const keyword = ref(''); const jobs = ref<Job[]>([]); const selectedJobId = ref(''); const timeline = ref<EvolutionTimeline | null>(null)
const filteredJobs = computed(() => jobs.value.filter(job => !keyword.value.trim() || job.title.toLowerCase().includes(keyword.value.trim().toLowerCase()) || job.id.includes(keyword.value.trim())))
const selectedJob = computed(() => jobs.value.find(job => job.id === selectedJobId.value))
async function selectJob(id: string) { selectedJobId.value = id; timeline.value = null; try { timeline.value = await getJobEvolutionTimeline(id) } catch { /* 后端无记录时显示诚实空态 */ } }
async function loadData() { loading.value = true; try { const result = await getJobList({ page: 1, page_size: 100 }); jobs.value = result.list || []; if (!selectedJobId.value && jobs.value[0]) await selectJob(jobs.value[0].id) } finally { loading.value = false } }
onMounted(loadData)
</script>
<style scoped>
.module-mark { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 14px; font-size: 23px; }.evolution-mark { color: #83bc9a; background: #eaf6ee; }.evolution-layout { display: grid; grid-template-columns: 310px 1fr; gap: 16px; align-items: start; }.job-picker { min-height: 620px; }.job-list { display: grid; gap: 5px; max-height: 520px; margin-top: 14px; overflow: auto; }.job-list button { display: flex; flex-direction: column; gap: 3px; padding: 11px 12px; border: 0; border-radius: 10px; background: transparent; color: #555; text-align: left; }.job-list button:hover, .job-list button.active { background: #fff4ef; color: var(--coral-deep); }.job-list small { color: #aaa39e; font-size: 10px; }.evolution-main { min-height: 620px; }.record-list { display: grid; gap: 10px; }.record-card { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; padding: 16px; border: 1px solid var(--line); border-radius: 12px; background: var(--card-soft); }.record-card strong { font-size: 14px; }.record-card p { margin: 7px 0 0; color: #9d9793; font-size: 12px; line-height: 1.6; }.empty-state { min-height: 420px; }.empty-state .el-icon { color: #d4c9c1; }
@media (max-width: 900px) { .evolution-layout { grid-template-columns: 1fr; }.job-picker { min-height: auto; }.job-list { max-height: 260px; } }
</style>