<template>
  <section class="page jobs-page">
    <div class="page-title">
      <div class="title-left"><div class="module-mark jobs-mark"><el-icon><Files /></el-icon></div><div><h1>JD 岗位管理</h1><p>展示 M2 完整岗位目录：新一代与现有岗位、中文及英文来源</p></div></div>
      <div class="page-actions"><el-button class="btn-soft" :loading="loading" @click="loadPage"><el-icon><RefreshRight /></el-icon>刷新数据</el-button><el-button class="btn-soft-green" @click="exportCurrent"><el-icon><Download /></el-icon>导出岗位目录</el-button></div>
    </div>

    <div class="stats-row" v-loading="loading">
      <article v-for="card in statCards" :key="card.platform" class="stat-card"><div class="stat-icon-circle" :style="{ background: card.bg, color: card.color }"><strong>{{ card.short }}</strong></div><div class="stat-body"><span class="stat-number">{{ formatNumber(card.count) }}</span><span class="stat-label">{{ card.label }}岗位</span><small>{{ formatNumber(card.unique_titles) }} 个不同岗位名称</small></div></article>
    </div>

    <section class="filter-panel panel">
      <div class="search-line"><el-input v-model="keyword" clearable :prefix-icon="Search" placeholder="搜索岗位名称、岗位职责或技能" @keyup.enter="loadPage" /><el-button class="btn-coral" @click="loadPage">搜索</el-button></div>
      <div class="filter-line"><el-select v-model="platform" clearable placeholder="全部平台" @change="loadPage"><el-option v-for="item in platformStats" :key="item.platform" :label="item.label" :value="item.platform" /></el-select><el-select v-model="category" clearable placeholder="全部岗位类型" @change="loadPage"><el-option label="新一代岗位" value="新一代" /><el-option label="现有岗位" value="现有" /></el-select><el-button class="btn-soft" @click="resetFilters"><el-icon><RefreshLeft /></el-icon>重置</el-button><span class="result-count">共 {{ formatNumber(total) }} 个岗位定义</span></div>
    </section>

    <section class="table-panel panel" v-loading="loading">
      <el-table :data="jobs" stripe style="width: 100%">
        <el-table-column label="岗位信息" min-width="310"><template #default="{ row }"><strong class="job-title">{{ row.title }}</strong><span class="job-subtitle">{{ row.core_duties ? shortText(row.core_duties, 72) : '暂无职责摘要' }}</span></template></el-table-column>
        <el-table-column label="类型 / 来源" width="150"><template #default="{ row }"><el-tag size="small" effect="plain" :type="row.category === '新一代' ? 'success' : 'info'">{{ row.category || '岗位' }}</el-tag><small class="job-source">{{ row.platform_label || row.type || '未知来源' }}</small></template></el-table-column>
        <el-table-column label="当前技能" min-width="300"><template #default="{ row }"><div class="skill-tags"><el-tag v-for="skill in row.skills.slice(0, 6)" :key="skill" size="small" effect="plain">{{ skill }}</el-tag><span v-if="row.skills.length > 6" class="more-skill">+{{ row.skills.length - 6 }}</span><span v-if="!row.skills.length" class="muted">暂无技能</span></div></template></el-table-column>
        <el-table-column label="更新时间" width="170"><template #default="{ row }">{{ formatTime(row.updated) }}</template></el-table-column>
        <el-table-column label="操作" width="110" fixed="right"><template #default="{ row }"><el-button text class="detail-link" @click="openDetail(row)">查看详情</el-button></template></el-table-column>
      </el-table>
      <div v-if="!jobs.length && !loading" class="table-empty"><el-icon><Document /></el-icon><p>没有找到匹配的岗位定义</p><el-button class="btn-soft" @click="resetFilters">清除筛选</el-button></div>
      <div class="pagination-wrap"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next, jumper" background small @current-change="loadPage" @size-change="loadPage" /></div>
    </section>

    <el-dialog v-model="detailVisible" :title="detailJob?.title || '岗位详情'" width="760px"><div v-if="detailJob" class="detail-content"><div class="detail-meta"><el-tag effect="plain">{{ detailJob.category || '岗位' }}</el-tag><el-tag effect="plain">{{ detailJob.platform_label || detailJob.type }}</el-tag><span v-if="detailJob.name_en">英文名：{{ detailJob.name_en }}</span><span>采集时间：{{ formatTime(detailJob.collected_at || detailJob.updated) }}</span><span v-if="detailJob.experience">经验：{{ detailJob.experience }}</span></div><section><h3>岗位职责</h3><p class="duties">{{ detailJob.core_duties || '暂无岗位职责文本' }}</p></section><section><h3>技能要求</h3><div class="skill-tags"><el-tag v-for="(skill, index) in detailSkills" :key="skill + index" closable effect="plain" @close="removeDetailSkill(index)">{{ skill }}</el-tag><span v-if="!detailSkills.length" class="muted">暂无结构化技能</span></div><div class="skill-editor"><template v-if="addingSkill"><el-input v-model="newSkill" size="small" class="skill-input" placeholder="输入技能名后回车添加" @keyup.enter="confirmAddSkill" /><button type="button" class="skill-add-btn" title="确认添加" @click="confirmAddSkill">+</button></template><button v-else type="button" class="skill-add-btn" title="添加技能" @click="startAddSkill">+</button><span v-if="skillDirty" class="muted skill-tip">技能有未保存变更</span><el-button v-if="skillDirty" size="small" type="primary" :loading="savingSkills" @click="saveSkills">保存技能</el-button></div></section></div></el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Document, Download, Files, RefreshLeft, RefreshRight, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { exportJobs, getJobDetail, getJobList, getJobPlatformStats, updateJob, type Job, type JobPlatformStat } from '../api/jobs'

const loading = ref(false)
const keyword = ref('')
const platform = ref('')
const category = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const jobs = ref<Job[]>([])
const platformStats = ref<JobPlatformStat[]>([])
const detailVisible = ref(false)
const detailJob = ref<Job | null>(null)
const detailSkills = ref<string[]>([])
const addingSkill = ref(false)
const newSkill = ref("")
const skillDirty = ref(false)
const savingSkills = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const statCards = computed(() => {
  const fallback = [{ platform: 'boss', label: 'BOSS', count: 0, unique_titles: 0 }, { platform: 'zhaopin', label: '智联', count: 0, unique_titles: 0 }, { platform: 'liepin', label: '猎聘', count: 0, unique_titles: 0 }, { platform: 'linkedin', label: 'LinkedIn', count: 0, unique_titles: 0 }, { platform: 'hn', label: 'Hacker News', count: 0, unique_titles: 0 }]
  return fallback.map((item, index) => ({ ...(platformStats.value.find(stat => stat.platform === item.platform) || item), short: item.label === 'BOSS' ? item.label : item.label.slice(0, 2), bg: ['#E8EFF5', '#E8F5E9', '#FFF3E0'][index], color: ['#6D8EAD', '#68A47D', '#C28F4A'][index] }))
})

function formatNumber(value: number) { return new Intl.NumberFormat('zh-CN').format(value || 0) }
function formatTime(value: string) { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false }) }
function shortText(value: string, length: number) { return value.length > length ? `${value.slice(0, length)}…` : value }
function resetFilters() { keyword.value = ''; platform.value = ''; category.value = ''; page.value = 1; loadPage() }
async function loadPage() { loading.value = true; try { const [result, stats] = await Promise.all([getJobList({ keyword: keyword.value.trim(), platform: platform.value, category: category.value, page: page.value, page_size: pageSize.value }), getJobPlatformStats()]); jobs.value = result?.list || []; total.value = result?.total || 0; platformStats.value = Array.isArray(stats) ? stats : [] } catch { ElMessage.error('中文平台岗位数据加载失败') } finally { loading.value = false } }
async function openDetail(job: Job) { detailJob.value = job; detailSkills.value = [...(job.skills || [])]; skillDirty.value = false; addingSkill.value = false; detailVisible.value = true; try { const detail = await getJobDetail(job.id); if (detail) { detailJob.value = { ...job, ...detail }; detailSkills.value = [...(detail.skills || [])] } } catch { } }
function startAddSkill() { newSkill.value = ""; addingSkill.value = true }
function confirmAddSkill() { const s = newSkill.value.trim(); if (!s) return; if (!detailSkills.value.includes(s)) { detailSkills.value.push(s); skillDirty.value = true } newSkill.value = "" }
function removeDetailSkill(index: number) { detailSkills.value.splice(index, 1); skillDirty.value = true }
async function saveSkills() { const job = detailJob.value; if (!job) return; const edited = detailSkills.value; const oldRequired = job.required_skills || []; const oldBonus = job.bonus_skills || []; const removed = oldRequired.concat(oldBonus).filter(s => !edited.includes(s)); const added = edited.filter(s => !oldRequired.includes(s) && !oldBonus.includes(s)); const required = oldRequired.filter(s => !removed.includes(s)).concat(added); const bonus = oldBonus.filter(s => !removed.includes(s)); savingSkills.value = true; try { const payload: any = { job_name: job.job_name || job.name_en || "", core_duties: job.core_duties || "", required_skills: required, bonus_skills: bonus, scenarios: job.scenarios || [], source: job.source || [], quality: typeof (job as any).quality === "number" ? (job as any).quality : 0, is_emerging: job.category === "新一代", evolution: (job as any).evolution || {}, collected_at: job.collected_at || "", updated_at: new Date().toISOString() }; await updateJob(job.id, payload); skillDirty.value = false; ElMessage.success("技能已保存"); const detail = await getJobDetail(job.id); if (detail) { detailJob.value = { ...job, ...detail }; detailSkills.value = [...(detail.skills || [])] } loadPage() } catch { ElMessage.error("技能保存失败") } finally { savingSkills.value = false } }
async function exportCurrent() { try { const blob = await exportJobs(); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = '中文平台岗位.csv'; link.click(); URL.revokeObjectURL(url) } catch { ElMessage.error('岗位导出失败') } }
watch([keyword, platform, category], () => { if (searchTimer) clearTimeout(searchTimer); searchTimer = setTimeout(() => { page.value = 1; loadPage() }, 300) })
onMounted(loadPage)
onUnmounted(() => { if (searchTimer) clearTimeout(searchTimer) })
</script>

<style scoped>
.module-mark { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 14px; font-size: 23px; }.jobs-mark { color: #6d8ead; background: #e8eff5; }.btn-soft-green { color: #5e9a6b !important; border: 1px solid #cfe8d4 !important; background: #eff9f1 !important; }.stats-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 16px; }.stat-card { display: flex; align-items: center; gap: 15px; min-height: 106px; padding: 20px; border: 1px solid rgba(241,235,228,.8); border-radius: 16px; background: #fff; box-shadow: var(--shadow); }.stat-icon-circle { display: grid; width: 50px; height: 50px; flex: 0 0 auto; place-items: center; border-radius: 50%; font-size: 12px; font-weight: 700; }.stat-body span, .stat-body small { display: block; }.stat-number { margin-bottom: 3px; color: var(--text); font-size: 26px; font-weight: 700; }.stat-label { color: #8e8985; font-size: 13px; }.stat-body small { margin-top: 4px; color: #aaa39e; font-size: 10px; }.filter-panel { margin-bottom: 16px; padding: 17px 20px; }.search-line, .filter-line { display: flex; align-items: center; gap: 12px; }.search-line .el-input { flex: 1; }.filter-line { margin-top: 13px; }.filter-line .el-select { width: 210px; }.result-count { margin-left: auto; color: #9f9995; font-size: 12px; }.table-panel { overflow: hidden; padding: 0; }.table-panel :deep(.el-table) { border-radius: var(--radius); }.job-title, .job-subtitle { display: block; }.job-source { display: block; margin-top: 4px; color: #aaa39e; font-size: 10px; }.job-title { color: #3d3b3c; font-size: 14px; }.job-subtitle { max-width: 460px; margin-top: 5px; overflow: hidden; color: #a19b97; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.skill-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; }.skill-tags :deep(.el-tag) { border-color: #e7ded7; color: #6f91ae; background: #fffdfa; }.more-skill, .muted { color: #aaa39e; font-size: 11px; }.detail-link { color: #6b94b8 !important; }.pagination-wrap { display: flex; justify-content: flex-end; padding: 15px 18px; border-top: 1px solid var(--line); }.table-empty { display: flex; min-height: 260px; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: #b4ada8; font-size: 13px; }.table-empty .el-icon { color: #d7cbc3; font-size: 32px; }.table-empty p { margin: 0 0 5px; }.detail-content section { margin-top: 20px; }.detail-content h3 { margin: 0 0 10px; font-size: 14px; }.detail-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; color: #9d9691; font-size: 12px; }.duties { margin: 0; padding: 14px; border-radius: 10px; background: #fcfaf7; color: #5d5855; font-size: 13px; line-height: 1.8; white-space: pre-wrap; }
.skill-editor { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 10px; }.skill-input { width: 200px; }.skill-add-btn { display: inline-flex; width: 26px; height: 26px; align-items: center; justify-content: center; border: 1px dashed #6b94b8; border-radius: 6px; background: #fff; color: #6b94b8; font-size: 17px; line-height: 1; cursor: pointer; }.skill-add-btn:hover { background: #eef5fb; }.skill-tip { color: #c07a3c; }.skill-save-btn { margin-left: 6px; }
@media (max-width: 900px) { .stats-row { grid-template-columns: 1fr; }.search-line { align-items: stretch; flex-direction: column; }.search-line .el-input, .search-line .btn-coral { width: 100%; }.filter-line { flex-wrap: wrap; }.filter-line .el-select { width: 100%; }.result-count { margin-left: 0; }.table-panel { overflow-x: auto; }.table-panel :deep(.el-table) { min-width: 900px; } }
</style>
