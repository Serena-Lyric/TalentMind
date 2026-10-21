<template>
  <section class="page jobs-page">
    <div class="page-title">
      <div class="title-left">
        <div class="module-mark jobs-mark"><el-icon><Files /></el-icon><span class="mark-spark">✦</span></div>
        <div><h1>JD 岗位管理 <span class="title-star" aria-hidden="true">✦</span></h1><p>完整岗位目录：新一代与现有岗位、中文及英文来源</p></div>
      </div>
      <div class="page-actions"><el-button class="btn-soft" :loading="loading" @click="loadPage"><el-icon><RefreshRight /></el-icon>刷新数据</el-button><el-button class="btn-soft-green" @click="exportCurrent"><el-icon><Download /></el-icon>导出岗位目录</el-button></div>
    </div>

    <div class="stats-row" v-loading="loading">
      <aside class="job-guide-mascot" aria-label="岗位小管家">
        <span class="mascot-spark spark-a" aria-hidden="true">✦</span>
        <span class="mascot-spark spark-b" aria-hidden="true">✧</span>
        <div class="mascot-person" aria-hidden="true">
          <img class="mascot-person__image" src="/jobs-nebula-girl.png" alt="" />
        </div>
        <small>岗位小管家</small>
        <div class="job-skill-bubble" role="note">
          <div class="job-bubble-title"><span>✦</span><b>岗位管理概述</b></div>
          <p>这里汇总各平台 JD 岗位目录，支持按岗位名称、职责和技能搜索筛选，查看岗位分类、来源、职责、技能要求与更新时间，并维护结构化技能和导出岗位目录。</p>
        </div>
      </aside>
      <article v-for="(card, index) in statCards" :key="card.platform" class="stat-card" :style="{ '--sprite-color': card.color, '--sprite-bg': card.bg }">
        <div class="stat-icon-circle" :style="{ background: card.bg, color: card.color }"><strong>{{ card.short }}</strong></div>
        <div class="stat-body"><span class="stat-number">{{ formatNumber(card.count) }}</span><span class="stat-label">{{ card.label }}岗位</span><small>{{ formatNumber(card.unique_titles) }} 个不同岗位名称</small></div>
        <div class="stat-sprite" :class="`sprite-${index % 3}`" aria-hidden="true">
          <span class="sprite-orbit"></span><span class="sprite-face"><i></i><i></i><b></b></span><span class="sprite-hand">✦</span>
        </div>
      </article>
    </div>

    <section class="filter-panel panel">
      <div class="filter-sprite" aria-hidden="true"><span class="satellite-ring"></span><span class="satellite-face"><i></i><i></i><b></b></span><em>✦</em></div>
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

    <el-dialog v-model="detailVisible" :title="detailJob?.title || '岗位详情'" width="760px"><div v-if="detailJob" class="detail-content"><div class="detail-meta"><el-tag effect="plain">{{ detailJob.category || '岗位' }}</el-tag><el-tag effect="plain">{{ detailJob.platform_label || detailJob.type }}</el-tag><span v-if="detailJob.name_en">英文名：{{ detailJob.name_en }}</span><span>采集时间：{{ formatTime(detailJob.collected_at || detailJob.updated) }}</span><span v-if="detailJob.experience">经验：{{ detailJob.experience }}</span></div><section><h3>岗位职责</h3><p class="duties">{{ detailJob.core_duties || '暂无岗位职责文本' }}</p></section><section><h3>技能要求</h3><div class="skill-tags"><template v-for="(skill, index) in detailSkills" :key="skill + index"><el-input v-if="editingIndex === index" v-model="editValue" size="small" class="skill-input" placeholder="修改技能名" @keyup.enter="confirmEditSkill" @keyup.esc="cancelEditSkill" @blur="confirmEditSkill" /><el-tag v-else closable effect="plain" @close="removeDetailSkill(index)" @dblclick="startEditSkill(index)">{{ skill }}</el-tag></template><span v-if="!detailSkills.length" class="muted">暂无结构化技能</span></div><div class="skill-editor"><template v-if="addingSkill"><el-input v-model="newSkill" size="small" class="skill-input" placeholder="输入技能名后回车添加" @keyup.enter="confirmAddSkill" /><button type="button" class="skill-add-btn" title="确认添加" @click="confirmAddSkill">+</button></template><button v-else type="button" class="skill-add-btn" title="添加技能" @click="startAddSkill">+</button><span v-if="skillDirty" class="muted skill-tip">技能有未保存变更</span><el-button v-if="skillDirty" size="small" type="primary" :loading="savingSkills" @click="saveSkills">保存技能</el-button></div></section></div></el-dialog>
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
const editingIndex = ref(-1)
const editValue = ref("")
let searchTimer: ReturnType<typeof setTimeout> | null = null

const statCards = computed(() => {
  const fallback = [{ platform: 'boss', label: 'BOSS', count: 0, unique_titles: 0 }, { platform: 'zhaopin', label: '智联', count: 0, unique_titles: 0 }, { platform: 'liepin', label: '猎聘', count: 0, unique_titles: 0 }, { platform: 'linkedin', label: 'LinkedIn', count: 0, unique_titles: 0 }, { platform: 'hn', label: 'Hacker News', count: 0, unique_titles: 0 }]
  return fallback.map((item, index) => ({ ...(platformStats.value.find(stat => stat.platform === item.platform) || item), short: item.label === 'BOSS' ? item.label : item.label.slice(0, 2), bg: ['#E8EFF5', '#E7F5EF', '#FFF3E5'][index], color: ['#6D8EAD', '#55B88D', '#D58A3D'][index] }))
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
function startEditSkill(index: number) { editingIndex.value = index; editValue.value = detailSkills.value[index] }
function cancelEditSkill() { editingIndex.value = -1; editValue.value = "" }
function confirmEditSkill() { if (editingIndex.value < 0) return; const idx = editingIndex.value; const old = detailSkills.value[idx]; const val = editValue.value.trim(); if (!val) { cancelEditSkill(); return } if (val !== old) { if (detailSkills.value.includes(val)) { ElMessage.warning("该技能已存在"); editValue.value = old; return } detailSkills.value[idx] = val; skillDirty.value = true } editingIndex.value = -1 }
async function saveSkills() { const job = detailJob.value; if (!job) return; const edited = detailSkills.value; const oldRequired = job.required_skills || []; const oldBonus = job.bonus_skills || []; const removed = oldRequired.concat(oldBonus).filter(s => !edited.includes(s)); const added = edited.filter(s => !oldRequired.includes(s) && !oldBonus.includes(s)); const required = oldRequired.filter(s => !removed.includes(s)).concat(added); const bonus = oldBonus.filter(s => !removed.includes(s)); savingSkills.value = true; try { const payload: any = { job_name: job.job_name || job.name_en || "", core_duties: job.core_duties || "", required_skills: required, bonus_skills: bonus, scenarios: job.scenarios || [], source: job.source || [], quality: typeof (job as any).quality === "number" ? (job as any).quality : 0, is_emerging: job.category === "新一代", evolution: (job as any).evolution || {}, collected_at: job.collected_at || "", updated_at: new Date().toISOString() }; await updateJob(job.id, payload); skillDirty.value = false; ElMessage.success("技能已保存"); const detail = await getJobDetail(job.id); if (detail) { detailJob.value = { ...job, ...detail }; detailSkills.value = [...(detail.skills || [])] } loadPage() } catch { ElMessage.error("技能保存失败") } finally { savingSkills.value = false } }
async function exportCurrent() { try { const blob = await exportJobs(); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = '中文平台岗位.csv'; link.click(); URL.revokeObjectURL(url) } catch { ElMessage.error('岗位导出失败') } }
watch([keyword, platform, category], () => { if (searchTimer) clearTimeout(searchTimer); searchTimer = setTimeout(() => { page.value = 1; loadPage() }, 300) })
onMounted(loadPage)
onUnmounted(() => { if (searchTimer) clearTimeout(searchTimer) })
</script>

<style scoped>
.module-mark { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 14px; font-size: 23px; }.jobs-mark { color: #6d8ead; background: #e8eff5; }.btn-soft-green { color: #55B88D !important; border: 1px solid #E7F5EF !important; background: #E7F5EF !important; }.stats-row { display: grid; grid-template-columns: 112px repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }.stat-card { display: flex; align-items: center; gap: 15px; min-height: 106px; padding: 20px; border: 1px solid rgba(241,235,228,.8); border-radius: 16px; background: #fff; box-shadow: var(--shadow); }.stat-icon-circle { display: grid; width: 50px; height: 50px; flex: 0 0 auto; place-items: center; border-radius: 50%; font-size: 12px; font-weight: 700; }.stat-body span, .stat-body small { display: block; }.stat-number { margin-bottom: 3px; color: var(--text); font-size: 26px; font-weight: 700; }.stat-label { color: #69808E; font-size: 13px; }.stat-body small { margin-top: 4px; color: #69808E; font-size: 10px; }.filter-panel { margin-bottom: 16px; padding: 17px 20px; }.search-line, .filter-line { display: flex; align-items: center; gap: 12px; }.search-line .el-input { flex: 1; }.filter-line { margin-top: 13px; }.filter-line .el-select { width: 210px; }.result-count { margin-left: auto; color: #9f9995; font-size: 12px; }.table-panel { overflow: hidden; padding: 0; }.table-panel :deep(.el-table) { border-radius: var(--radius); }.job-title, .job-subtitle { display: block; }.job-source { display: block; margin-top: 4px; color: #69808E; font-size: 10px; }.job-title { color: #172735; font-size: 14px; }.job-subtitle { max-width: 460px; margin-top: 5px; overflow: hidden; color: #69808E; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.skill-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; }.skill-tags :deep(.el-tag) { border-color: #D9E2E7; color: #6f91ae; background: #FFFFFF; }.more-skill, .muted { color: #69808E; font-size: 11px; }.detail-link { color: #6b94b8 !important; }.pagination-wrap { display: flex; justify-content: flex-end; padding: 15px 18px; border-top: 1px solid var(--line); }.table-empty { display: flex; min-height: 260px; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: #b4ada8; font-size: 13px; }.table-empty .el-icon { color: #D9E2E7; font-size: 32px; }.table-empty p { margin: 0 0 5px; }.detail-content section { margin-top: 20px; }.detail-content h3 { margin: 0 0 10px; font-size: 14px; }.detail-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; color: #69808E; font-size: 12px; }.duties { margin: 0; padding: 14px; border-radius: 10px; background: #fcfaf7; color: #69808E; font-size: 13px; line-height: 1.8; white-space: pre-wrap; }
.skill-editor { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 10px; }.skill-input { width: 200px; }.skill-add-btn { display: inline-flex; width: 26px; height: 26px; align-items: center; justify-content: center; border: 1px dashed #6b94b8; border-radius: 6px; background: #fff; color: #6b94b8; font-size: 17px; line-height: 1; cursor: pointer; }.skill-add-btn:hover { background: #E8F0FA; }.skill-tip { color: #D58A3D; }.skill-save-btn { margin-left: 6px; }
@media (max-width: 900px) { .stats-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }.job-guide-mascot { grid-column:1 / -1; }.search-line { align-items: stretch; flex-direction: column; }.search-line .el-input, .search-line .btn-coral { width: 100%; }.filter-line { flex-wrap: wrap; }.filter-line .el-select { width: 100%; }.result-count { margin-left: 0; }.table-panel { overflow-x: auto; }.table-panel :deep(.el-table) { min-width: 900px; } }

/* 轻量卡通互动层：仅视觉装饰，不参与数据或业务逻辑 */
.title-star { display:inline-block; margin-left:5px; color:var(--purple); font-size:16px; transform:translateY(-8px); opacity:.72; transition:transform .25s ease; }
.page-title:hover .title-star { transform:translateY(-11px) rotate(18deg) scale(1.12); }
.mark-spark { position:absolute; top:-7px; right:-6px; color:#f2c86d; font-size:13px; filter:drop-shadow(0 2px 4px rgba(242,200,109,.28)); }
.jobs-mark { position:relative; transition:transform .25s ease; }
.page-title:hover .jobs-mark { transform:rotate(-4deg) translateY(-2px); }
.page-actions :deep(.el-button) { transition:transform .2s ease, box-shadow .2s ease; }
.page-actions :deep(.el-button:hover) { transform:translateY(-2px) rotate(-.6deg); box-shadow:0 8px 18px rgba(54,70,182,.10); }

.job-guide-mascot { position:relative; z-index:32; display:flex; min-width:0; min-height:112px; flex-direction:column; align-items:center; justify-content:flex-end; overflow:visible; padding:6px 8px 9px; border:1px solid rgba(88,87,181,.13); border-radius:16px; background:linear-gradient(145deg,#f4f1ff,#eef8f6); box-shadow:var(--shadow); }
.job-guide-mascot small { position:relative; z-index:3; margin-top:2px; color:#65748a; font-size:10px; font-weight:700; letter-spacing:.04em; }
.mascot-person { position:relative; z-index:3; width:104px; height:98px; transform-origin:50% 88%; transition:transform .28s cubic-bezier(.2,.8,.2,1); }
.mascot-person__image { display:block; width:100%; height:100%; object-fit:contain; object-position:center bottom; filter:contrast(1.05) saturate(1.08) brightness(1.02) drop-shadow(0 10px 13px rgba(83,77,151,.18)); transition:transform .24s ease, filter .24s ease; }
.job-guide-mascot:hover .mascot-person__image { transform:translateY(-3px) rotate(1deg) scale(1.05); filter:contrast(1.07) saturate(1.12) brightness(1.03) drop-shadow(0 14px 18px rgba(83,77,151,.23)); }
.mascot-head { position:absolute; top:4px; left:26px; z-index:3; width:28px; height:27px; border:2px solid #6577c7; border-radius:48% 52% 46% 54%; background:#fff4df; box-shadow:inset -4px -3px 0 rgba(101,119,199,.08); }
.mascot-head i { position:absolute; top:10px; width:3px; height:4px; border-radius:50%; background:#3646b6; transition:height .18s ease, transform .18s ease; }
.mascot-head i:first-child { left:7px; }.mascot-head i:nth-child(2) { right:7px; }
.mascot-head b { position:absolute; left:50%; bottom:5px; width:8px; height:4px; border-bottom:2px solid #9b63d9; border-radius:0 0 8px 8px; transform:translateX(-50%); }
.mascot-hair { position:absolute; top:1px; left:24px; z-index:4; width:31px; height:13px; border-radius:70% 45% 35% 30%; background:#6577c7; transform:rotate(-5deg); }
.mascot-hair::after { content:""; position:absolute; top:7px; left:1px; width:8px; height:8px; border-radius:50%; background:#6577c7; }
.mascot-body { position:absolute; top:29px; left:20px; z-index:2; width:40px; height:37px; overflow:hidden; border:2px solid #6577c7; border-radius:12px 12px 8px 8px; background:#8795e3; }
.mascot-body::before { content:""; position:absolute; top:-4px; left:12px; width:13px; height:17px; border-right:2px solid #fff; border-bottom:2px solid #fff; background:#f8fbff; transform:rotate(45deg); }
.mascot-body i { position:absolute; top:8px; left:18px; z-index:2; width:5px; height:17px; background:#9b63d9; clip-path:polygon(50% 0,100% 22%,72% 100%,28% 100%,0 22%); }
.mascot-body b { position:absolute; right:4px; bottom:5px; width:7px; height:7px; border:1px solid rgba(255,255,255,.72); border-radius:50%; }
.mascot-arm { position:absolute; top:35px; z-index:1; width:10px; height:31px; border:2px solid #6577c7; border-radius:8px; background:#8795e3; transform-origin:50% 4px; }
.mascot-arm-left { left:14px; transform:rotate(24deg); }.mascot-arm-right { right:13px; transform:rotate(-31deg); }
.mascot-leg { position:absolute; top:62px; z-index:1; width:10px; height:14px; border:2px solid #6577c7; border-radius:0 0 7px 7px; background:#5969bd; }
.mascot-leg-left { left:27px; transform:rotate(3deg); }.mascot-leg-right { right:26px; transform:rotate(-3deg); }
.mascot-briefcase { position:absolute; right:0; bottom:7px; z-index:5; width:22px; height:18px; border:2px solid #d28b45; border-radius:4px; background:#f2b566; box-shadow:inset 0 -4px 0 rgba(180,108,48,.12); transition:transform .22s ease; }
.mascot-briefcase::before { content:""; position:absolute; top:-6px; left:6px; width:7px; height:5px; border:2px solid #d28b45; border-bottom:0; border-radius:4px 4px 0 0; }
.mascot-briefcase i { position:absolute; inset:4px 2px auto; color:#8b5b2d; font-size:7px; font-style:normal; font-weight:800; text-align:center; }
.mascot-badge { position:absolute; top:34px; right:22px; z-index:5; color:#f2c86d; font-size:10px; }
.mascot-spark { position:absolute; z-index:4; color:#9b63d9; font-weight:700; opacity:.72; animation:twinkle 2.4s ease-in-out infinite; }
.spark-a { top:8px; left:10px; font-size:13px; }.spark-b { top:18px; right:8px; color:#34c7b0; font-size:11px; animation-delay:.7s; }
.job-skill-bubble { position:absolute; top:4px; left:112px; z-index:20; width:min(390px, calc(100vw - 180px)); padding:12px 15px; border:1px solid rgba(88,87,181,.18); border-radius:15px; background:linear-gradient(135deg,rgba(247,247,255,.98),rgba(233,249,246,.97)); box-shadow:0 14px 30px rgba(62,73,135,.16); opacity:0; visibility:hidden; pointer-events:none; text-align:left; transform:translateX(-8px) scale(.96); transform-origin:left center; transition:opacity .2s ease, visibility .2s ease, transform .24s ease; }
.job-skill-bubble::before { content:""; position:absolute; top:22px; left:-7px; width:12px; height:12px; border-top:1px solid rgba(88,87,181,.18); border-left:1px solid rgba(88,87,181,.18); border-radius:2px 0 0; background:#f7f7ff; transform:rotate(-45deg); }
.job-skill-bubble::after { content:"✦"; position:absolute; top:-11px; right:12px; color:#9b63d9; font-size:14px; font-weight:700; }
.job-bubble-title { display:flex; align-items:center; gap:7px; color:#3646b6; font-size:13px; }
.job-bubble-title span { color:#9b63d9; }
.job-skill-bubble p { margin:6px 0 0; color:#607084; font-size:12px; line-height:1.75; }
.job-guide-mascot:hover .job-skill-bubble { opacity:1; visibility:visible; transform:translateX(0) scale(1); animation:job-bubble-speak .34s ease; }
.job-guide-mascot:hover .mascot-person { transform:translateY(-4px) rotate(-2deg) scale(1.05); }
.job-guide-mascot:hover .mascot-arm-left { transform:rotate(42deg); }
.job-guide-mascot:hover .mascot-arm-right { transform:rotate(-48deg); }
.job-guide-mascot:hover .mascot-briefcase { transform:translateY(-3px) rotate(5deg); }
.job-guide-mascot:hover .mascot-head i { height:2px; transform:translateY(2px); }
.stat-card { position:relative; overflow:hidden; transition:transform .24s ease, border-color .24s ease, box-shadow .24s ease; }
.stat-card:hover { z-index:2; transform:translateY(-4px); border-color:color-mix(in srgb, var(--sprite-color) 34%, #dce5e9); box-shadow:0 12px 25px rgba(47,75,91,.10); }
.stat-sprite { position:absolute; top:13px; right:15px; width:39px; height:39px; opacity:.72; transform:translateY(0) rotate(0); transition:transform .28s cubic-bezier(.2,.8,.2,1), opacity .2s ease; }
.sprite-face, .satellite-face, .empty-planet { position:absolute; inset:7px; border:2px solid color-mix(in srgb, var(--sprite-color, #3646b6) 75%, #fff); border-radius:45% 55% 50% 48%; background:var(--sprite-bg, #edf0ff); box-shadow:inset 0 -4px 0 rgba(255,255,255,.45); }
.sprite-face i, .satellite-face i, .empty-planet i { position:absolute; top:10px; width:3px; height:5px; border-radius:50%; background:var(--sprite-color, #3646b6); transition:height .18s ease, transform .18s ease; }
.sprite-face i:first-child, .satellite-face i:first-child, .empty-planet i:first-child { left:8px; }
.sprite-face i:nth-child(2), .satellite-face i:nth-child(2), .empty-planet i:nth-child(2) { right:8px; }
.sprite-face b, .satellite-face b, .empty-planet b { position:absolute; left:50%; bottom:7px; width:8px; height:4px; transform:translateX(-50%); border-bottom:2px solid var(--sprite-color, #3646b6); border-radius:0 0 8px 8px; }
.sprite-orbit, .satellite-ring, .empty-orbit { position:absolute; inset:1px; border:1px dashed color-mix(in srgb, var(--sprite-color, #3646b6) 42%, transparent); border-radius:50%; transform:rotate(-18deg) scaleY(.55); }
.sprite-hand { position:absolute; top:2px; right:-2px; color:#f2c86d; font-size:11px; transform:rotate(8deg); transition:transform .2s ease; }
.stat-card:hover .stat-sprite { opacity:1; transform:translateY(-5px) rotate(-5deg) scale(1.08); }
.stat-card:hover .sprite-orbit { animation:orbit-spin 2.6s linear infinite; }
.stat-card:hover .sprite-face i { height:2px; transform:translateY(2px); }
.stat-card:hover .sprite-hand { transform:rotate(28deg) scale(1.18); }
.sprite-1 .sprite-face { border-radius:52% 46% 55% 45%; }
.sprite-2 .sprite-face { border-radius:50%; transform:rotate(8deg); }

.filter-panel { position:relative; overflow:visible; transition:box-shadow .24s ease, border-color .24s ease; }
.filter-panel:hover { border-color:rgba(54,70,182,.18); box-shadow:0 11px 25px rgba(47,75,91,.07); }
.filter-sprite { position:absolute; top:-17px; right:24px; width:35px; height:35px; opacity:.55; transform:translateX(0) rotate(-8deg); transition:transform .35s ease, opacity .2s ease; --sprite-color:#34c7b0; --sprite-bg:#e8f6f2; }
.filter-sprite .satellite-face { inset:6px; }
.filter-sprite > em { position:absolute; top:-3px; right:-7px; color:#f2c86d; font-size:11px; font-style:normal; }
.filter-panel:hover .filter-sprite { opacity:1; transform:translateX(-8px) translateY(-3px) rotate(5deg); }
.filter-panel:hover .satellite-ring { animation:orbit-spin 2.8s linear infinite; }
.search-line :deep(.el-input__wrapper), .filter-line :deep(.el-select__wrapper) { transition:transform .2s ease, box-shadow .2s ease; }
.search-line :deep(.el-input__wrapper:hover), .filter-line :deep(.el-select__wrapper:hover) { transform:translateY(-1px); }

.table-panel { position:relative; }
.table-panel :deep(.el-table__row) { transition:background-color .18s ease, transform .18s ease; }
.table-panel :deep(.el-table__row:hover) .job-title::after { content:"✦"; display:inline-block; margin-left:7px; color:#f2c86d; font-size:10px; animation:twinkle .65s ease; }
.detail-link { transition:color .2s ease, transform .2s ease; }
.detail-link:hover { color:var(--primary) !important; transform:translateX(3px); }
.table-empty { position:relative; overflow:hidden; }
.empty-mascot { position:absolute; top:24px; left:50%; width:62px; height:52px; transform:translateX(-50%); --sprite-color:#9b63d9; --sprite-bg:#f1eafa; opacity:.78; transition:transform .3s ease; }
.empty-planet { inset:7px 12px 10px; border-radius:48% 52% 46% 54%; }
.empty-orbit { inset:1px 0 4px; transform:rotate(-9deg) scaleY(.48); }
.empty-mascot em { position:absolute; color:#f2c86d; font-style:normal; }
.empty-mascot em:nth-of-type(1) { top:1px; right:3px; font-size:11px; }
.empty-mascot em:nth-of-type(2) { bottom:4px; left:4px; font-size:14px; }
.table-empty:hover .empty-mascot { transform:translateX(-50%) translateY(-7px) rotate(-4deg); }
.table-empty:hover .empty-orbit { animation:orbit-spin 3.2s linear infinite; }
.table-empty:hover .empty-planet i { height:2px; transform:translateY(2px); }
.table-empty > .el-icon { margin-top:70px; opacity:.75; }

@keyframes orbit-spin { to { transform:rotate(342deg) scaleY(.55); } }
@keyframes twinkle { 0%,100% { opacity:.3; transform:scale(.7) rotate(0); } 55% { opacity:1; transform:scale(1.25) rotate(24deg); } }
@keyframes job-bubble-speak { 0% { opacity:0; transform:translateX(-8px) scale(.96); } 65% { opacity:1; transform:translateX(3px) scale(1.01); } 100% { opacity:1; transform:translateX(0) scale(1); } }
@media (prefers-reduced-motion: reduce) {
  .job-guide-mascot:hover .job-skill-bubble, .job-guide-mascot:hover .mascot-person, .job-guide-mascot:hover .mascot-arm-left, .job-guide-mascot:hover .mascot-arm-right, .job-guide-mascot:hover .mascot-briefcase,
  .stat-card:hover .sprite-orbit, .filter-panel:hover .satellite-ring, .table-empty:hover .empty-orbit,
  .table-panel :deep(.el-table__row:hover) .job-title::after { animation:none; }
}
@media (max-width: 900px) {
  .job-skill-bubble { top:90px; left:8px; width:min(390px, calc(100vw - 48px)); transform:translateY(-8px) scale(.96); transform-origin:top left; }
  .job-skill-bubble::before { top:-7px; left:28px; }
  .job-guide-mascot:hover .job-skill-bubble { transform:translateY(0) scale(1); }
}
@media (max-width: 600px) {
  .stats-row { grid-template-columns:1fr; }
  .job-guide-mascot { min-height:122px; }
}
</style>
