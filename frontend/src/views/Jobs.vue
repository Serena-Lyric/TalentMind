<template>
  <section class="job-page">
    <!-- 页面装饰 -->
    <div class="page-deco deco-top-right">
      <svg width="180" height="100" viewBox="0 0 180 100" fill="none">
        <circle cx="160" cy="20" r="4" fill="#D98B6E" opacity="0.07"/>
        <circle cx="140" cy="45" r="2.5" fill="#A8C5B8" opacity="0.08"/>
        <circle cx="170" cy="60" r="3" fill="#B8C4D0" opacity="0.06"/>
        <path d="M120 10 Q135 5 150 12" stroke="#D98B6E" stroke-width="0.6" fill="none" opacity="0.08"/>
        <ellipse cx="100" cy="30" rx="10" ry="6" fill="#B8C4D0" opacity="0.04"/>
      </svg>
    </div>
    <div class="page-deco deco-bottom-left">
      <svg width="160" height="80" viewBox="0 0 160 80" fill="none">
        <path d="M0 60 Q30 40 60 60 T120 60 T160 55" stroke="#D98B6E" stroke-width="0.8" fill="none" opacity="0.06"/>
        <circle cx="30" cy="30" r="3" fill="#A8C5B8" opacity="0.06"/>
        <circle cx="100" cy="45" r="2" fill="#D98B6E" opacity="0.05"/>
      </svg>
    </div>

    <!-- 页面标题 -->
    <div class="page-title">
      <div class="title-left">
        <div class="title-illustration">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <rect x="4" y="8" width="28" height="34" rx="3" fill="#FDF5F0" stroke="#D98B6E" stroke-width="1"/>
            <rect x="16" y="4" width="28" height="34" rx="3" fill="#fff" stroke="#D98B6E" stroke-width="1"/>
            <line x1="22" y1="14" x2="38" y2="14" stroke="#D98B6E" stroke-width="1" opacity="0.4"/>
            <line x1="22" y1="20" x2="35" y2="20" stroke="#D98B6E" stroke-width="1" opacity="0.3"/>
            <line x1="22" y1="26" x2="32" y2="26" stroke="#D98B6E" stroke-width="1" opacity="0.2"/>
            <circle cx="10" cy="20" r="6" fill="#F5D5C8"/>
            <path d="M6 18 Q8 14 10 13 Q12 14 14 18" fill="#8B7B6B" opacity="0.4"/>
            <path d="M6 22 Q6 20 10 20 Q14 20 14 22 L14 28 Q14 30 10 30 Q6 30 6 28 Z" fill="#D98B6E" opacity="0.2"/>
          </svg>
        </div>
        <div>
          <h1>JD 岗位管理</h1>
          <p>导入、维护并追踪成熟岗位的技能演进</p>
        </div>
      </div>
      <div class="job-actions">
        <el-button class="btn-ghost" @click="importDialog = true">
          <el-icon><Upload /></el-icon>批量导入 JD
        </el-button>
        <el-button class="btn-coral" @click="openEditor()">
          <el-icon><Plus /></el-icon>人工新增岗位
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card" v-for="(s, i) in statCards" :key="s.label">
        <div class="stat-icon-circle" :style="{ background: s.iconBg }">
          <svg v-if="i===0" width="24" height="24" viewBox="0 0 24 24" fill="none">
            <rect x="3" y="6" width="18" height="14" rx="2" stroke="#7B8FA8" stroke-width="1.4" fill="none"/>
            <path d="M8 6 V4 Q8 2 12 2 Q16 2 16 4 V6" stroke="#7B8FA8" stroke-width="1.4" fill="none"/>
            <circle cx="12" cy="13" r="2.5" stroke="#7B8FA8" stroke-width="1" fill="#E8EFF5"/>
          </svg>
          <svg v-else-if="i===1" width="24" height="24" viewBox="0 0 24 24" fill="none">
            <polyline points="4,18 10,10 14,14 20,6" stroke="#8BBFA0" stroke-width="1.8" fill="none" stroke-linecap="round"/>
            <polyline points="16,6 20,6 20,10" stroke="#8BBFA0" stroke-width="1.8" fill="none" stroke-linecap="round"/>
            <circle cx="4" cy="18" r="1.5" fill="#8BBFA0" opacity="0.3"/>
            <circle cx="10" cy="10" r="1.5" fill="#8BBFA0" opacity="0.3"/>
            <circle cx="20" cy="6" r="1.5" fill="#8BBFA0"/>
          </svg>
          <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="8" stroke="#D4A574" stroke-width="1.4" fill="none"/>
            <path d="M12 8 V12 L15 15" stroke="#D4A574" stroke-width="1.4" stroke-linecap="round" fill="none"/>
            <path d="M8 4 L6 2" stroke="#D4A574" stroke-width="1" opacity="0.4" stroke-linecap="round"/>
            <path d="M16 4 L18 2" stroke="#D4A574" stroke-width="1" opacity="0.4" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-number">{{ s.value }}</span>
          <span class="stat-label">{{ s.label }}</span>
        </div>
      </div>
    </div>


    <!-- 筛选栏 -->
    <section class="filter-panel">
      <!-- 第一行：搜索框通栏 -->
      <div class="filter-row">
        <el-input v-model="keyword" placeholder="搜索岗位名称 / 公司" :prefix-icon="Search" clearable @clear="onSearchClear" class="filter-input" />
      </div>
      <!-- 第二行：四个下拉框均分 -->
      <div class="filter-row filter-row-selects">
        <el-select v-model="city" placeholder="全部城市" clearable class="filter-select">
          <el-option v-for="item in cities" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="trackFilter" placeholder="全部赛道" clearable class="filter-select">
          <el-option v-for="t in trackOptions" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-select v-model="skillStatus" placeholder="技能演进状态" clearable class="filter-select">
          <el-option label="含新增技能" value="新增" />
          <el-option label="含淘汰技能" value="淘汰" />
          <el-option label="含变更技能" value="变更" />
        </el-select>
        <el-select v-model="salaryRange" placeholder="薪资区间" clearable class="filter-select">
          <el-option v-for="r in salaryRanges" :key="r" :label="r" :value="r" />
        </el-select>
      </div>
      <!-- 第三行：时间选择器 + 操作按钮 -->
      <div class="filter-row filter-row-actions">
        <el-date-picker v-model="updateTimeRange" type="daterange" range-separator="~" start-placeholder="更新起始" end-placeholder="更新截止" value-format="YYYY-MM-DD" clearable style="width:260px" class="filter-date" />
        <div class="filter-actions">
          <el-button class="btn-soft-pink" :disabled="!selectedRows.length" @click="batchDelete">
            <el-icon><Delete /></el-icon>批量删除 ({{ selectedRows.length }})
          </el-button>
          <el-button class="btn-soft-green" :disabled="!selectedRows.length" @click="batchExportExcel">
            <el-icon><Download /></el-icon>批量导出 Excel
          </el-button>
          <el-button class="btn-ghost-sm" @click="resetFilters">
            <el-icon><RefreshLeft /></el-icon>重置
          </el-button>
          <span class="result-count">共 <b>{{ filteredJobs.length }}</b> 条结果</span>
        </div>
      </div>
    </section>

    <!-- 表格区域 -->
    <section class="table-panel">
      <div v-if="!pagedJobs.length" class="empty-state">
        <div class="empty-illustration">
          <svg width="180" height="140" viewBox="0 0 180 140" fill="none">
            <circle cx="90" cy="70" r="55" fill="#FDE8E4" opacity="0.4"/>
            <circle cx="90" cy="70" r="40" fill="#FDF5F0"/>
            <rect x="55" y="45" width="70" height="50" rx="4" fill="#fff" stroke="#E0D5CA" stroke-width="1"/>
            <line x1="65" y1="58" x2="115" y2="58" stroke="#D98B6E" stroke-width="1" opacity="0.3"/>
            <line x1="65" y1="65" x2="105" y2="65" stroke="#D98B6E" stroke-width="1" opacity="0.25"/>
            <line x1="65" y1="72" x2="100" y2="72" stroke="#D98B6E" stroke-width="1" opacity="0.2"/>
            <line x1="65" y1="79" x2="95" y2="79" stroke="#D98B6E" stroke-width="1" opacity="0.15"/>
            <circle cx="130" cy="40" r="5" fill="#A8C5B8" opacity="0.15"/>
            <circle cx="50" cy="100" r="3" fill="#D98B6E" opacity="0.1"/>
            <path d="M70 100 Q80 90 90 100 Q100 110 110 100" stroke="#B8C4D0" stroke-width="0.8" fill="none" opacity="0.2"/>
          </svg>
        </div>
        <p class="empty-text">暂无匹配的岗位数据</p>
        <el-button class="btn-coral-outline" @click="resetFilters">清除筛选条件</el-button>
      </div>

      <el-table v-else ref="tableRef" :data="pagedJobs" :row-class-name="tableRowClassName" @selection-change="onSelectionChange" @row-click="selectJob" highlight-current-row>
        <el-table-column type="selection" width="50" align="center" />
        <el-table-column label="岗位信息" min-width="250">
          <template #default="{ row }">
            <b class="job-title-link" @click.stop="openJdDetail(row)">{{ row.title }}</b>
            <p class="subline">{{ row.company }} · {{ row.city }} · {{ row.type }}</p>
          </template>
        </el-table-column>
        <el-table-column prop="salary" label="薪资范围" width="120" />
        <el-table-column label="当前技能" min-width="260">
          <template #default="{ row }">
            <el-tag v-for="skill in row.skills.slice(0, 3)" :key="skill" size="small" effect="plain" class="clickable-tag" @click.stop="onSkillTagClick(skill)">{{ skill }}</el-tag>
            <el-tooltip v-if="row.skills.length > 3" :content="row.skills.slice(3).join('、')" placement="top">
              <span class="more-skill">+{{ row.skills.length - 3 }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="演进概览" width="170">
          <template #default="{ row }">
            <div class="tiny-status">
              <el-tooltip :content="'新增：' + row.evolution.added.join('、') || '无'" placement="top">
                <span class="evolution-badge skill-add">+{{ row.evolution.added.length }}</span>
              </el-tooltip>
              <el-tooltip :content="'淘汰：' + row.evolution.removed.join('、') || '无'" placement="top">
                <span class="evolution-badge skill-remove">-{{ row.evolution.removed.length }}</span>
              </el-tooltip>
              <el-tooltip :content="'变更：' + row.evolution.changed.join('、') || '无'" placement="top">
                <span class="evolution-badge skill-change">~{{ row.evolution.changed.length }}</span>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="updated" label="更新时间" width="120" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button text class="action-blue" @click.stop="selectJob(row)">技能对比</el-button>
            <el-button text class="action-green" @click.stop="openEditor(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap" v-if="filteredJobs.length">
        <el-pagination v-model:current-page="currentPage" :page-size="pageSize" :total="filteredJobs.length" layout="total, sizes, prev, pager, next, jumper" :page-sizes="[10, 20, 50]" background small />
      </div>
    </section>

    <!-- 对比区 -->
    <section v-if="selectedJob" class="compare-section panel">
      <div class="section-title">
        <div>
          <h2>成熟岗位技能演进对比</h2>
          <p>以 {{ selectedJob.title }} 为例，对比最新 JD 与历史版本的技能变化</p>
        </div>
        <el-tag effect="plain" class="version-tag">版本 {{ selectedJob.updated }} vs 2024-06-18</el-tag>
      </div>
      <div class="compare-grid">
        <article class="compare-card old">
          <header>
            <span class="version-dot"></span>
            <div><b>历史 JD 技能</b><p>2024-06-18 · {{ oldSkills.length }} 项</p></div>
          </header>
          <div class="skill-cloud">
            <el-tag v-for="skill in oldSkills" :key="skill" effect="plain" class="tag-old">{{ skill }}</el-tag>
          </div>
        </article>
        <article class="compare-card new">
          <header>
            <span class="version-dot"></span>
            <div><b>当前 JD 技能</b><p>{{ selectedJob.updated }} · {{ selectedJob.skills.length }} 项</p></div>
          </header>
          <div class="skill-cloud">
            <el-tag v-for="skill in selectedJob.skills" :key="skill" effect="light" class="tag-new">{{ skill }}</el-tag>
          </div>
        </article>
        <article class="compare-card evolution">
          <div class="panel-head-sm">
            <div><h3>技能变化清单</h3><p>颜色标识可作为图谱演进数据源</p></div>
          </div>
          <div class="evolution-groups">
            <div v-for="group in evolutionGroups" :key="group.key" class="evolution-group">
              <div class="evolution-label" :class="group.key">
                <span>{{ group.symbol }}</span>
                {{ group.label }} <b>{{ group.items.length }}</b>
              </div>
              <div>
                <el-tag v-for="skill in group.items" :key="skill" :class="['evolution-tag', group.key]" effect="plain">{{ skill }}</el-tag>
                <span v-if="!group.items.length" class="empty-tip">暂无</span>
              </div>
            </div>
          </div>
        </article>
      </div>
    </section>

    <!-- JD 详情弹窗 -->
    <el-dialog v-model="jdDetailDialog" :title="jdDetailJob?.title" width="720px">
      <template v-if="jdDetailJob">
        <div class="jd-meta">
          <el-tag effect="plain">{{ jdDetailJob.company }}</el-tag>
          <el-tag effect="plain" type="info">{{ jdDetailJob.city }}</el-tag>
          <el-tag effect="plain" type="warning">{{ jdDetailJob.salary }}</el-tag>
          <el-tag effect="plain">{{ jdDetailJob.type }}</el-tag>
        </div>
        <el-divider />
        <div class="jd-section">
          <h4><el-icon><Document /></el-icon> 岗位职责</h4>
          <ul><li v-for="(r, i) in jdDetailJob.responsibilities" :key="i">{{ r }}</li></ul>
        </div>
        <el-divider />
        <div class="jd-section">
          <h4><el-icon><User /></el-icon> 任职要求</h4>
          <ul><li v-for="(r, i) in jdDetailJob.requirements" :key="i">{{ r }}</li></ul>
        </div>
        <el-divider />
        <div class="jd-section">
          <h4><el-icon><Collection /></el-icon> 技能要求</h4>
          <div class="skill-cloud">
            <el-tag v-for="skill in jdDetailJob.skills" :key="skill" effect="light" class="tag-new">{{ skill }}</el-tag>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 批量导入弹窗 -->
    <el-dialog v-model="importDialog" title="批量导入 JD 文本" width="680px">
      <p class="dialog-tip">支持 .txt / .md / .csv 文件或直接粘贴多条 JD。每段以"岗位名称："开头即可自动识别。</p>
      <el-upload drag :auto-upload="false" accept=".txt,.md,.csv" :show-file-list="false" :on-change="readFile">
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽 JD 文件到此处，或 <em>点击选择文件</em></div>
        <template #tip><div class="el-upload__tip">文件内容仅用于本地模拟解析，不会上传服务器</div></template>
      </el-upload>
      <el-divider>或粘贴 JD 文本</el-divider>
      <el-input v-model="jdText" type="textarea" :rows="7" placeholder="岗位名称：高级前端工程师..." />
      <template #footer>
        <el-button @click="importDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!jdText.trim()" @click="importJds">解析并导入</el-button>
      </template>
    </el-dialog>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editorDialog" :title="editingId ? '编辑岗位与技能' : '人工新增岗位'" width="720px" destroy-on-close>
      <el-form :model="form" label-width="86px">
        <div class="form-grid">
          <el-form-item label="岗位名称"><el-input v-model="form.title" /></el-form-item>
          <el-form-item label="所属公司"><el-input v-model="form.company" /></el-form-item>
          <el-form-item label="城市"><el-input v-model="form.city" /></el-form-item>
          <el-form-item label="薪资范围"><el-input v-model="form.salary" /></el-form-item>
        </div>
        <el-form-item label="当前技能">
          <div class="tag-editor">
            <el-tag v-for="(skill, index) in form.skills" :key="skill" closable @close="form.skills.splice(index, 1)">{{ skill }}</el-tag>
            <el-input v-if="addingCurrent" ref="currentInput" v-model="newCurrent" size="small" class="new-tag-input" @keyup.enter="addCurrent" @blur="addCurrent" />
            <el-button v-else class="add-tag-btn" size="small" @click="addingCurrent = true">+ 添加技能</el-button>
          </div>
        </el-form-item>
      </el-form>
      <el-divider>技能演进标注</el-divider>
      <div class="manual-evolution">
        <div v-for="group in editableGroups" :key="group.key" :class="['manual-group', group.key]">
          <h4><span>{{ group.symbol }}</span>{{ group.label }}</h4>
          <div class="tag-editor">
            <el-tag v-for="(skill, index) in form.evolution[group.key]" :key="skill" closable :class="['evolution-tag', group.key]" @close="form.evolution[group.key].splice(index, 1)">{{ skill }}</el-tag>
            <el-input v-if="addingType === group.key" v-model="newEvolution" size="small" class="new-tag-input" @keyup.enter="addEvolution(group.key)" @blur="addEvolution(group.key)" />
            <el-button v-else size="small" class="add-tag-btn" @click="addingType = group.key">+ 添加</el-button>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="editorDialog = false">取消</el-button>
        <el-button type="primary" @click="saveJob">保存岗位</el-button>
      </template>
    </el-dialog>
  </section>
</template>
<script setup lang="ts">
import { ref, computed, nextTick, reactive, onMounted } from 'vue'
import { Upload, Plus, Search, UploadFilled, Delete, Download, RefreshLeft, Close, Document, User, Collection, DataAnalysis, TrendCharts, Warning } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getJobList } from '../api/jobs'
import { getIndustryTracks } from '../api/dashboard'

interface Evolution { added: string[]; removed: string[]; changed: string[] }
interface Job { id: string; title: string; company: string; city: string; type: string; track: string; salary: string; updated: string; skills: string[]; responsibilities?: string[]; requirements?: string[]; evolution: Evolution }

const jobs = ref<any[]>([])
const industryTracks = ref<any[]>([])

const keyword = ref('')
const city = ref('')
const trackFilter = ref('')
const skillStatus = ref('')
const salaryRange = ref('')
const updateTimeRange = ref<string[] | null>(null)
const tableLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)
const selectedRows = ref<Job[]>([])
const tableRef = ref()
const importDialog = ref(false)
const editorDialog = ref(false)
const jdDetailDialog = ref(false)
const jdDetailJob = ref<Job | null>(null)
const jdText = ref('')
const selectedJob = ref<Job | null>(null)
const editingId = ref('')
const addingCurrent = ref(false)
const newCurrent = ref('')
const addingType = ref('')
const newEvolution = ref('')
const form = ref({ title: '', company: '', city: '', salary: '', skills: [] as string[], evolution: { added: [] as string[], removed: [] as string[], changed: [] as string[] } })

const cities = computed(() => Array.from(new Set(jobs.value.map((j: any) => j.city))))
const trackOptions = computed(() => industryTracks.value)
const salaryRanges = ['10-18K','15-25K','18-30K','20-35K','25-40K','30-45K','35-55K','40-60K']

const statCards = computed(() => {
  let addedCount = 0, removedCount = 0
  jobs.value.forEach((j: any) => { addedCount += (j.evolution?.added?.length || 0); removedCount += (j.evolution?.removed?.length || 0) })
  return [
    { label: '总岗位数量', value: jobs.value.length, iconBg: '#E8EFF5' },
    { label: '新增技能次数', value: addedCount, iconBg: '#E8F5E9' },
    { label: '淘汰技能次数', value: removedCount, iconBg: '#FFF3E0' }
  ]
})

const filteredJobs = computed(() => {
  return jobs.value.filter((job: any) => {
    const kw = keyword.value.trim().toLowerCase()
    const keywordMatch = !kw || job.title.toLowerCase().includes(kw) || job.company.toLowerCase().includes(kw)
    const cityMatch = !city.value || job.city === city.value
    const trackMatch = !trackFilter.value || job.track === trackFilter.value
    const statusMatch = !skillStatus.value || (
      (skillStatus.value === '新增' && (job.evolution?.added?.length || 0) > 0) ||
      (skillStatus.value === '淘汰' && (job.evolution?.removed?.length || 0) > 0) ||
      (skillStatus.value === '变更' && (job.evolution?.changed?.length || 0) > 0)
    )
    const salaryMatch = !salaryRange.value || job.salary === salaryRange.value
    let timeMatch = true
    if (updateTimeRange.value && updateTimeRange.value.length === 2) {
      timeMatch = job.updated >= updateTimeRange.value[0] && job.updated <= updateTimeRange.value[1]
    }
    return keywordMatch && cityMatch && trackMatch && statusMatch && salaryMatch && timeMatch
  })
})

const pagedJobs = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredJobs.value.slice(start, start + pageSize.value)
})

function onSkillTagClick(skill: string) { keyword.value = skill; currentPage.value = 1; ElMessage.success('已筛选技能：' + skill) }
function resetFilters() { keyword.value = ''; city.value = ''; trackFilter.value = ''; skillStatus.value = ''; salaryRange.value = ''; updateTimeRange.value = null; currentPage.value = 1 }
function onSearchClear() { keyword.value = ''; currentPage.value = 1 }
function onSelectionChange(rows: Job[]) { selectedRows.value = rows }
function tableRowClassName({ row }: { row: Job }) { return 'hover-highlight-row' }

function batchDelete() {
  ElMessageBox.confirm(`确认删除选中的 ${selectedRows.value.length} 个岗位？`, '批量删除确认', { type: 'warning' })
    .then(() => { ElMessage.success(`已删除 ${selectedRows.value.length} 个岗位`); selectedRows.value = [] }).catch(() => {})
}

function batchExportExcel() {
  const data = selectedRows.value.length ? selectedRows.value : filteredJobs.value
  const header = ['岗位名称','公司','城市','薪资','赛道','技能','更新时间']
  const rows = data.map((j: any) => [j.title, j.company, j.city, j.salary, j.type, j.skills.join(' | '), j.updated])
  const bom = '\uFEFF'
  const csv = bom + [header, ...rows].map(r => r.map(c => '"' + String(c).replace(/"/g, '""') + '"').join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob); link.download = 'JD岗位数据_' + new Date().toISOString().slice(0, 10) + '.csv'; link.click()
  URL.revokeObjectURL(link.href); ElMessage.success('已导出 ' + data.length + ' 条数据')
}

function openJdDetail(job: Job) { jdDetailJob.value = job; jdDetailDialog.value = true }

const oldSkills = computed(() => selectedJob.value ? selectedJob.value.skills.slice(0, 4).concat(['jQuery', '传统特征工程']) : [])
const evolutionGroups = computed(() => selectedJob.value ? [
  { key: 'added', symbol: '+', label: '新增技能', items: selectedJob.value.evolution.added },
  { key: 'removed', symbol: '-', label: '淘汰技能', items: selectedJob.value.evolution.removed },
  { key: 'changed', symbol: '~', label: '变更技能', items: selectedJob.value.evolution.changed }
] : [])
const editableGroups = [
  { key: 'added', symbol: '+', label: '新增技能' },
  { key: 'removed', symbol: '-', label: '淘汰技能' },
  { key: 'changed', symbol: '~', label: '变更技能' }
]

function selectJob(job: Job) { selectedJob.value = job }
function readFile(file: any) { const reader = new FileReader(); reader.onload = (e) => { jdText.value = e.target?.result as string }; reader.readAsText(file.raw) }
function importJds() { ElMessage.success('JD 解析成功'); importDialog.value = false; jdText.value = '' }

function openEditor(job?: Job) {
  if (job) {
    editingId.value = job.id
    form.value = { title: job.title, company: job.company, city: job.city, salary: job.salary, skills: [...job.skills], evolution: { ...job.evolution } }
  } else {
    editingId.value = ''
    form.value = { title: '', company: '', city: '', salary: '', skills: [], evolution: { added: [], removed: [], changed: [] } }
  }
  editorDialog.value = true
}

function addCurrent() { if (newCurrent.value.trim()) { form.value.skills.push(newCurrent.value.trim()); newCurrent.value = '' }; addingCurrent.value = false }
function addEvolution(type: string) { if (newEvolution.value.trim()) { (form.value.evolution as any)[type].push(newEvolution.value.trim()); newEvolution.value = '' }; addingType.value = '' }
function saveJob() { ElMessage.success('岗位保存成功'); editorDialog.value = false }

onMounted(async () => {
  tableLoading.value = true
  try {
    const data = await getJobList({ page: 1, page_size: 100 })
    if (data?.list) jobs.value = data.list
    const tracks = await getIndustryTracks()
    if (Array.isArray(tracks)) industryTracks.value = tracks
  } catch (e) {
    ElMessage.error('岗位数据加载失败')
  } finally {
    tableLoading.value = false
  }
})
</script>
<style scoped>
.job-page {max-width: 1440px;
  margin: auto;
  position: relative;
  padding: 4px 0 40px;}

.page-deco {display: none;}

.deco-top-right {top: 70px;
  right: 0;}

.deco-bottom-left {bottom: 0;
  left: 250px;}

.page-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
}

.title-left {display: flex;
  align-items: center;
  gap: 14px;}

.title-illustration {display: none;}

.job-actions {display: flex;
  gap: 10px;}

/* ===== 按钮 ===== */
.btn-ghost {background: #FDFBF7;
  border: 1px solid #E8DDD4;
  color: #77777E;
  border-radius: 20px;
  font-weight: 500;}

.btn-ghost:hover {background: #F5EDE5;
  border-color: #D9CFC6;
  color: #555559;}

.btn-coral {background: #D98B6E;
  border: none;
  color: #fff;
  border-radius: 20px;
  font-weight: 500;
  box-shadow: 0 2px 8px rgba(217, 139, 110, 0.25);}

.btn-coral:hover {background: #C87A5E;
  box-shadow: 0 4px 12px rgba(217, 139, 110, 0.35);}

.btn-coral-outline {background: transparent;
  border: 1px solid #D98B6E;
  color: #D98B6E;
  border-radius: 20px;}

.btn-soft-pink {background: #FDF0EE;
  border: 1px solid #F0D5D0;
  color: #C07060;
  border-radius: 20px;}

.btn-soft-pink:hover {background: #F8E2DD;}

.btn-soft-green {background: #EEF7F0;
  border: 1px solid #C8E6C9;
  color: #5A9A60;
  border-radius: 20px;}

.btn-soft-green:hover {background: #DDF0E0;}

.btn-ghost-sm {background: transparent;
  border: 1px solid #E0D5CC;
  color: #77777E;
  border-radius: 20px;
  font-size: 12px;}

.stats-row {display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px;}

.stat-card {background: #fff;
  border: none;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  padding: 22px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: box-shadow 0.2s;}

.stat-card:hover {box-shadow: 0 4px 18px rgba(0, 0, 0, 0.07);}

.stat-icon-circle {width: 52px;
  height: 52px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;}

.stat-body {flex: 1;}

.stat-number {display: block;
  font-size: 28px;
  font-weight: 700;
  color: #333338;
  line-height: 1.1;
  margin-bottom: 4px;}

.stat-label {font-size: 13px;
  color: #77777E;}

/* ===== 筛选栏 ===== */
.filter-panel {background: #fff;
  border: none;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  padding: 18px 20px;
  margin-bottom: 18px;}

.filter-row {display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 20px;}

.filter-row:last-child {margin-bottom: 0;}

.filter-row-selects {display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;}

.filter-row-actions {display: flex;
  justify-content: space-between;
  align-items: center;}

.filter-input {width: 100%;}

.filter-select {width: 100%;}

.filter-date {flex-shrink: 0;}

.filter-actions {display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;}

.result-count {margin-left: auto;
  font-size: 13px;
  color: #77777E;}

/* ===== 表格 ===== */
.table-panel {background: #fff;
  border: none;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  overflow: hidden;}

.job-title-link {color: #333338;
  cursor: pointer;
  transition: color 0.2s;}

.job-title-link:hover {color: #D98B6E;
  text-decoration: underline;}

.subline {font-size: 12px;
  color: #77777E;
  margin: 3px 0 0;}

.clickable-tag {cursor: pointer;
  background: #FDFBF7;
  border-color: #E8DDD4;
  color: #6B8BA4;
  border-radius: 8px;
  transition: all 0.2s;}

.clickable-tag:hover {background: #D98B6E !important;
  color: #fff !important;
  border-color: #D98B6E !important;}

.more-skill {font-size: 12px;
  color: #77777E;
  margin-left: 4px;
  cursor: pointer;}

.action-blue {color: #7B8FA8;}

.action-blue:hover {color: #5A7A94;}

.action-green {color: #8BBFA0;}

.action-green:hover {color: #6AA080;}

/* ===== 演进概览 ===== */
.tiny-status {display: flex;
  gap: 6px;}

.evolution-badge {font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
  cursor: help;
  transition: transform 0.15s;}

.evolution-badge:hover {transform: scale(1.15);}

.skill-add {background: #E8F5E9;
  color: #6A9A70;}

.skill-remove {background: #FFF3E0;
  color: #C8A060;}

.skill-change {background: #FDF0EE;
  color: #C07060;}

/* ===== 分页 ===== */
.pagination-wrap {padding: 14px 20px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #F5F0EA;}

/* ===== 空状态 ===== */
.empty-state {padding: 60px 20px;
  text-align: center;}

.empty-text {font-size: 15px;
  color: #77777E;
  margin: 16px 0 20px;}

/* ===== 对比区 ===== */
.compare-section {margin-top: 20px;}

.section-title {display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;}

.version-tag {background: #FDFBF7;
  border-color: #E8DDD4;
  color: #77777E;
  border-radius: 8px;}

.compare-grid {grid-template-columns: 1fr;}

.compare-card {background: #FDFBF7;
  border-radius: 14px;
  padding: 18px;}

.version-dot {background: #D98B6E;}

.skill-cloud {display: flex;
  flex-wrap: wrap;
  gap: 6px;}

.tag-old {background: #F5F0EA;
  border-color: #E0D5CC;
  color: #77777E;
  border-radius: 8px;}

.tag-new {background: #FDF0EE;
  border-color: #F0D5D0;
  color: #C07060;
  border-radius: 8px;}

.panel-head-sm {margin-bottom: 14px;}

.evolution-groups {display: flex;
  flex-direction: column;
  gap: 10px;}

.evolution-group {padding: 10px;
  background: #fff;
  border-radius: 10px;}

.evolution-label {display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  margin-bottom: 8px;}

.evolution-tag {border-radius: 8px;
  margin: 2px;}

.added {background: #E8F5E9;
  border-color: #C8E6C9;
  color: #6A9A70;}

.removed {background: #FFF3E0;
  border-color: #FFE0B2;
  color: #C8A060;}

.changed {background: #FDF0EE;
  border-color: #F0D5D0;
  color: #C07060;}

.empty-tip {font-size: 11px;
  color: #77777E;}

/* ===== 弹窗 ===== */
.jd-meta {display: flex;
  gap: 8px;
  flex-wrap: wrap;}

.upload-icon {font-size: 48px;
  color: #D98B6E;}

.dialog-tip {font-size: 13px;
  color: #77777E;
  margin-bottom: 16px;}

.form-grid {grid-template-columns: 1fr;}

.tag-editor {display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;}

.new-tag-input {width: 100px;}

.add-tag-btn {border-style: dashed;
  border-radius: 8px;}

.manual-evolution {display: flex;
  flex-direction: column;
  gap: 16px;}

/* filter responsive handled by grid */

</style>