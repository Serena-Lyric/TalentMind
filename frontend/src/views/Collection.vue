<template>
  <section class="page collection-page">
    <div class="page-title">
      <div><h1>采集工作台</h1><p>配置一次有界采集，先准备浏览器，再明确启动。登录或验证由你在浏览器中完成。</p></div>
      <el-button :loading="refreshing" @click="refreshAll">刷新状态</el-button>
    </div>
    <el-alert v-if="refreshErrors.length" :title="refreshErrors.join('；')" type="error" :closable="false" show-icon />

    <section class="panel setup-panel">
      <div class="section-heading"><div><h2><span class="step">1</span>配置本轮采集</h2><p>单个平台、单关键词、单城市；本轮最多一页、5 条列表与 5 条详情。</p></div><el-tag effect="plain">单轮验证</el-tag></div>
      <el-form label-position="top" class="config-grid" :disabled="busy || preparing">
        <el-form-item label="招聘平台">
          <el-select v-model="configForm.platform" placeholder="选择平台" aria-label="招聘平台">
            <el-option v-for="item in platforms" :key="item.platform" :label="item.supported ? item.label : `${item.label}（暂未接入）`" :value="item.platform" :disabled="!item.supported" />
          </el-select>
        </el-form-item>
        <el-form-item label="单个关键词"><el-input v-model="keyword" placeholder="例如：Python" maxlength="80" aria-label="单个关键词" /></el-form-item>
        <el-form-item label="城市">
          <el-select v-model="cityCode" placeholder="选择当前平台城市" :disabled="!availableCities.length" aria-label="城市">
            <el-option v-for="city in availableCities" :key="city.code" :label="city.name" :value="city.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="页数"><el-input-number v-model="configForm.pages" :min="1" :max="1" :precision="0" /></el-form-item>
        <el-form-item label="详情尝试上限"><el-input-number v-model="configForm.detail_limit" :min="1" :max="5" :precision="0" /></el-form-item>
        <el-form-item label="列表岗位上限"><el-input-number v-model="configForm.max_jobs" :min="1" :max="5" :precision="0" /></el-form-item>
      </el-form>
      <p v-if="!selectedPlatform?.supported" class="hint">{{ platforms.length ? '当前来源未接入可启动采集，请选择受支持的平台。' : '正在等待平台配置；配置不可用时无法启动。' }}</p>
      <div class="gate-note"><el-radio-group model-value="once"><el-radio-button value="once">单轮</el-radio-button><el-radio-button value="continuous" disabled>持续采集</el-radio-button></el-radio-group><span>持续能力保留：Gate 1 尚未验收，暂不可启用。</span></div>
    </section>

    <div class="action-grid">
      <section class="panel prepare-panel">
        <h2><span class="step">2</span>准备浏览器</h2>
        <p>打开独立采集浏览器并检查当前平台访问状态。准备操作不会开始采集或写库。</p>
        <div class="access-row"><el-tag :type="accessReady ? 'success' : 'warning'">{{ accessText(accessState) }}</el-tag><span>{{ accessMessage }}</span></div>
        <p v-if="preparation?.target_url" class="source-detail">搜索目标：<a v-if="sourceUrl(preparation.target_url)" :href="sourceUrl(preparation.target_url)" target="_blank" rel="noopener noreferrer">{{ preparation.target_url }}</a><span v-else>搜索地址无效，请重新检查。</span></p>
        <p v-if="['login_required', 'verification_required', 'content_limited'].includes(accessState)" class="hint">请在浏览器人工处理；完成后再次点击“准备 / 重新检查”。受限时采集会停止。</p>
        <el-button :loading="preparing" :disabled="!selectedPlatform?.supported || busy || starting" @click="prepareBrowser">{{ preparing ? '浏览器准备中，请稍候' : '准备 / 重新检查' }}</el-button>
      </section>
      <section class="panel launch-panel">
        <h2><span class="step">3</span>启动单轮</h2>
        <p class="launch-summary">{{ selectedPlatform?.label || '未选平台' }} · {{ keyword.trim() || '待填关键词' }} · {{ configForm.cities[0]?.name || '待选城市' }}</p>
        <p>{{ configForm.pages }} 页 / 列表 ≤ {{ configForm.max_jobs }} / 详情尝试 ≤ {{ configForm.detail_limit }}</p>
        <div class="button-row"><el-button type="primary" :disabled="!canStart" :loading="starting" @click="startTask">启动本轮采集</el-button><el-button type="danger" plain :disabled="!canStop" :loading="stopping" @click="stopTask">停止任务</el-button></div>
        <p class="hint">{{ startHint }}</p>
      </section>
    </div>

    <section class="panel progress-panel">
      <div class="section-heading"><div><h2>本轮进度</h2><p class="mono">任务 ID：{{ currentTask.run_id || '暂无任务' }}</p></div><el-tag>{{ statusText(currentTask.status) }}</el-tag></div>
      <div class="task-context"><span>平台：{{ platformText(currentTask.platform) }}</span><span>关键词：{{ currentTask.current_keyword || '—' }}</span><span>城市：{{ currentTask.current_city || '—' }}</span><span>开始：{{ formatTime(currentTask.started_at) }}</span></div>
      <div class="count-grid"><div v-for="item in progressItems" :key="item.key"><strong>{{ item.value }}</strong><span>{{ item.label }}</span></div></div>
      <p class="hint">“—”表示尚无可信计数；详情尝试、详情取得、完整 JD 与实际入库分别计数。</p>
      <el-alert v-if="currentTask.stop_reason || currentTask.last_error" :title="[currentTask.stop_reason, currentTask.last_error].filter(Boolean).join(' · ')" type="warning" :closable="false" show-icon />
    </section>

    <section class="panel results-panel">
      <div class="section-heading"><div><h2>本轮真实结果</h2><p>仅展示任务 {{ currentTask.run_id || '—' }} 的实际事件；拒绝和失败也保留，不补入历史 JD。</p></div><el-tag effect="plain">{{ results.length }} 条事件</el-tag></div>
      <el-alert v-if="resultsError" :title="resultsError" type="error" :closable="false" />
      <el-table v-loading="resultsLoading" :data="results" stripe empty-text="本轮暂无结果事件" style="width:100%">
        <el-table-column prop="job_title" label="岗位" min-width="180" show-overflow-tooltip />
        <el-table-column label="来源" width="100"><template #default="{ row }">{{ platformText(row.source) }}</template></el-table-column>
        <el-table-column label="处理结果" width="110"><template #default="{ row }">{{ outcomeText(row.outcome) }}</template></el-table-column>
        <el-table-column label="jd_pool ID" width="110"><template #default="{ row }">{{ row.jd_pool_id ?? '—' }}</template></el-table-column>
        <el-table-column prop="rejection_reason" label="拒绝 / 失败原因" min-width="180" show-overflow-tooltip />
        <el-table-column label="采集时间" width="180"><template #default="{ row }">{{ formatTime(row.crawled_at) }}</template></el-table-column>
        <el-table-column label="正文与来源" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openRaw(row)">查看原文</el-button></template></el-table-column>
      </el-table>
    </section>

    <section class="panel stats-panel">
      <div class="section-heading"><div><h2>数据库现状</h2><p>累计原始 JD；与上方本轮事件分开核验。</p></div><span>最近采集：{{ formatTime(stats.latest_crawled_at) }}</span></div>
      <el-alert v-if="databaseError" :title="databaseError" type="error" :closable="false" show-icon />
      <div class="stats-grid"><div><span>全库岗位</span><strong>{{ stats.available === false ? '—' : formatNumber(stats.database_total) }}</strong></div><div v-for="item in platformStats" :key="item.platform"><span>{{ item.label }}</span><strong>{{ formatNumber(item.count) }}</strong></div></div>
      <div class="quality-row"><span v-for="item in qualityItems" :key="item.label">{{ item.label }}：{{ item.value }}</span></div>
    </section>

    <section class="panel history-panel">
      <div class="section-heading"><div><h2>历史任务</h2><p>按任务查看日志与结果，历史未知计数保留为“—”。</p></div></div>
      <el-table :data="history" stripe empty-text="暂无控制台历史任务">
        <el-table-column prop="run_id" label="任务 ID" min-width="190" show-overflow-tooltip />
        <el-table-column label="平台" width="100"><template #default="{ row }">{{ platformText(row.platform) }}</template></el-table-column>
        <el-table-column label="状态" width="130"><template #default="{ row }">{{ statusText(row.status) }}</template></el-table-column>
        <el-table-column label="完整 JD" width="100"><template #default="{ row }">{{ formatNumber(row.complete) }}</template></el-table-column>
        <el-table-column label="新增 / 更新" width="130"><template #default="{ row }">{{ formatNumber(row.inserted) }} / {{ formatNumber(row.updated) }}</template></el-table-column>
        <el-table-column prop="stop_reason" label="停止原因" min-width="170" show-overflow-tooltip />
        <el-table-column label="开始时间" width="180"><template #default="{ row }">{{ formatTime(row.started_at) }}</template></el-table-column>
        <el-table-column label="详情" width="115" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openHistory(row)">日志与结果</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-if="historyTotal > 20" v-model:current-page="historyPage" :page-size="20" :total="historyTotal" layout="prev, pager, next" @current-change="loadHistory" />
    </section>

    <el-drawer v-model="showHistory" title="历史任务日志与结果" size="min(900px, 95vw)">
      <template v-if="selectedTask">
        <p class="mono">{{ selectedTask.run_id }}</p><p>{{ platformText(selectedTask.platform) }} · {{ statusText(selectedTask.status) }} · {{ selectedTask.stop_reason || '无停止原因记录' }}</p>
        <div class="count-grid"><div v-for="item in countsFor(selectedTask)" :key="item.key"><strong>{{ item.value }}</strong><span>{{ item.label }}</span></div></div>
        <h3>任务日志 · {{ selectedTask.log_status || '未知' }}</h3><pre class="raw-text">{{ selectedTask.raw_log_tail?.join('\n') || '暂无可读取日志' }}</pre>
        <h3>该任务结果</h3><el-alert v-if="historyResultsError" :title="historyResultsError" type="error" :closable="false" />
        <el-table v-loading="historyLoading" :data="historyResults" empty-text="该任务无结果事件">
          <el-table-column prop="job_title" label="岗位" min-width="170" /><el-table-column label="结果" width="100"><template #default="{ row }">{{ outcomeText(row.outcome) }}</template></el-table-column><el-table-column prop="rejection_reason" label="原因" min-width="150" /><el-table-column label="原文" width="85"><template #default="{ row }"><el-button link type="primary" @click="openRaw(row)">查看</el-button></template></el-table-column>
        </el-table>
      </template>
    </el-drawer>
    <el-drawer v-model="showRaw" title="来源与完整正文" size="min(760px, 95vw)">
      <template v-if="eventRecord">
        <h3>{{ eventRecord.job_title || '未取得岗位标题' }}</h3>
        <div class="source-meta"><span>来源：{{ platformText(eventRecord.source) }}</span><span>结果：{{ outcomeText(eventRecord.outcome) }}</span><span>jd_pool ID：{{ eventRecord.jd_pool_id ?? '—' }}</span><span>采集时间：{{ formatTime(eventRecord.crawled_at) }}</span></div>
        <p class="source-detail">来源地址：<a v-if="sourceUrl(eventRecord.source_detail)" :href="sourceUrl(eventRecord.source_detail)" target="_blank" rel="noopener noreferrer">{{ eventRecord.source_detail }}</a><span v-else>{{ eventRecord.source_detail || '未取得' }}</span></p>
        <el-alert v-if="eventRecord.rejection_reason" :title="eventRecord.rejection_reason" type="warning" :closable="false" />
        <h3>该任务取得的原文</h3><pre class="raw-text">{{ eventRecord.raw_text || '该事件未取得正文' }}</pre>
        <h3>原始库完整正文</h3>
        <div v-loading="rawLoading" class="raw-db">
          <el-alert v-if="rawError" :title="rawError" type="error" :closable="false" />
          <p v-if="!eventRecord.jd_pool_id" class="hint">该事件未关联入库 ID，无法读取数据库原文。</p>
          <template v-if="rawRecord"><p class="hint">当前数据库记录；仅显式授权的本地访问可读取。质量分：{{ formatQuality(rawRecord.quality) }}</p><pre class="raw-text">{{ rawRecord.raw_text || '库记录正文为空' }}</pre><h3>职责（原始字段或原文分段）</h3><pre class="raw-text">{{ rawRecord.duties || '原文未提供明确职责段' }}</pre><h3>任职要求（按原文标题分段）</h3><pre class="raw-text">{{ rawRecord.requirements || '原文未提供明确要求段，请核验完整原文' }}</pre></template>
        </div>
      </template>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getCDPStatus, getCollectionConfig, getCollectionHistory, getCollectionPlatforms, getCollectionRaw, getCollectionResults, getCollectionStatus, getDatabaseStats, prepareCollection, startCollection, stopCollection, type CDPStatus, type CollectionAccess, type CollectionConfig, type CollectionPlatform, type CollectionPreparation, type CollectionRaw, type CollectionResult, type CollectionStats, type CollectionTask } from '../api/collection'

const platforms = ref<CollectionPlatform[]>([])
const configForm = reactive<CollectionConfig>({ platform: 'boss', mode: 'once', keywords: [], cities: [], pages: 1, detail_limit: 5, max_jobs: 5 })
const currentTask = ref<CollectionTask>({ run_id: null, status: 'idle' })
const stats = ref<CollectionStats>({ database_total: null, platform_counts: [] })
const cdpStatus = ref<CDPStatus | null>(null)
const preparation = ref<CollectionPreparation | null>(null)
const preparedFor = ref<string | null>(null)
const refreshing = ref(false)
const preparing = ref(false)
const starting = ref(false)
const stopping = ref(false)
const refreshErrors = ref<string[]>([])
const results = ref<CollectionResult[]>([])
const resultsError = ref('')
const resultsLoading = ref(false)
const history = ref<CollectionTask[]>([])
const historyPage = ref(1)
const historyTotal = ref(0)
const selectedTask = ref<CollectionTask | null>(null)
const showHistory = ref(false)
const historyResults = ref<CollectionResult[]>([])
const historyResultsError = ref('')
const historyLoading = ref(false)
const showRaw = ref(false)
const eventRecord = ref<CollectionResult | null>(null)
const rawRecord = ref<CollectionRaw | null>(null)
const rawError = ref('')
const rawLoading = ref(false)
let browserRequest = 0

const selectedPlatform = computed(() => platforms.value.find(item => item.platform === configForm.platform))
const availableCities = computed(() => selectedPlatform.value?.cities || [])
const keyword = computed({ get: () => configForm.keywords[0] || '', set: (value: string) => { configForm.keywords = value.trim() ? [value] : [] } })
const cityCode = computed({ get: () => configForm.cities[0]?.code || '', set: (code: string) => { const city = availableCities.value.find(item => item.code === code); configForm.cities = city ? [{ ...city }] : [] } })
watch(() => configForm.platform, () => { configForm.cities = [] }, { flush: 'sync' })
watch(() => JSON.stringify([configForm.platform, configForm.keywords, configForm.cities, configForm.pages, configForm.detail_limit, configForm.max_jobs]), () => {
  browserRequest++
  preparedFor.value = null
  preparation.value = null
  cdpStatus.value = null
}, { flush: 'sync' })
const busy = computed(() => !currentTask.value.finished_at && ['preparing', 'waiting_for_browser', 'running', 'waiting_next_round', 'stopping'].includes(currentTask.value.status))
const canStop = computed(() => busy.value && !!currentTask.value.run_id && !stopping.value)
const access = computed<CollectionAccess | null>(() => cdpStatus.value && !cdpStatus.value.reachable ? { access_state: 'cdp_unavailable', can_collect: false } : cdpStatus.value?.platform_access?.[configForm.platform || ''] || preparation.value)
const accessState = computed(() => preparing.value ? 'preparing' : access.value?.content_limited || preparation.value?.content_limited || preparation.value?.access_state === 'content_limited' ? 'content_limited' : access.value?.access_state || 'unready')
const accessReady = computed(() => access.value?.can_collect === true && ['public_accessible', 'authenticated_accessible', 'public', 'auth', 'empty_results'].includes(accessState.value))
const accessMessage = computed(() => {
  if (accessState.value === 'content_limited') return '正文访问受限，请在浏览器中人工处理后重新检查。'
  const last = preparation.value
  if (last?.message && (!last.can_collect || preparedFor.value === configForm.platform)) return last.message
  return cdpStatus.value?.error ? `浏览器检查失败：${cdpStatus.value.error}` : access.value?.message || (access.value?.reason ? accessReasonText(access.value.reason) : '请显式准备浏览器；系统不会自动登录或绕过验证。')
})
const configValid = computed(() => !!selectedPlatform.value?.supported && configForm.keywords.length === 1 && !!keyword.value.trim() && keyword.value.trim().length <= 80 && configForm.cities.length === 1 && availableCities.value.some(city => city.code === configForm.cities[0]?.code && city.name === configForm.cities[0]?.name) && configForm.pages === 1 && Number.isInteger(configForm.detail_limit) && configForm.detail_limit >= 1 && configForm.detail_limit <= 5 && Number.isInteger(configForm.max_jobs) && configForm.max_jobs >= 1 && configForm.max_jobs <= 5)
const canStart = computed(() => configValid.value && preparedFor.value === configForm.platform && accessReady.value && !busy.value && !preparing.value && !starting.value && !stopping.value)
const startHint = computed(() => busy.value ? '任务处理中；可停止后查看已取得结果。' : !configValid.value ? '请完成有效的平台、关键词与城市配置，页数为 1，列表和详情上限为 1–5。' : preparing.value ? '浏览器准备中，请稍候。' : !accessReady.value && (preparation.value || access.value || cdpStatus.value?.error) ? `${accessMessage.value}；请处理后点击“准备 / 重新检查”。` : preparedFor.value !== configForm.platform ? '先点击左侧准备浏览器，再启动单轮。' : '已准备就绪，点击后仅提交当前单轮任务。')
const databaseError = computed(() => stats.value.error || (stats.value.available === false ? '数据库统计暂不可用' : ''))
const platformStats = computed(() => platforms.value.map(item => ({ platform: item.platform, label: item.label, count: stats.value.available === false ? null : stats.value.platform_counts?.find(row => row.platform === item.platform)?.count ?? null })))
const qualityItems = computed(() => [
  { label: '职责非空', value: stats.value.data_quality?.duties_nonempty },
  { label: '来源为空', value: stats.value.data_quality?.empty_source_detail },
  { label: '重复来源组', value: stats.value.data_quality?.duplicate_source_detail },
  { label: '占位 / 空 URL', value: stats.value.data_quality?.placeholder_empty_url },
].map(item => ({ label: item.label, value: formatNumber(stats.value.available === false ? null : item.value) })))
const countFields = [
  ['listed', '列表识别'], ['detail_attempted', '详情尝试'], ['detail_obtained', '详情取得'], ['complete', '完整 JD'], ['inserted', '新增入库'], ['updated', '更新入库'], ['skipped', '跳过'], ['rejected', '拒绝'], ['failed', '失败'],
] as const
function countsFor(task: CollectionTask) { return countFields.map(([key, label]) => ({ key, label, value: formatNumber(task[key]) })) }
const progressItems = computed(() => countsFor(currentTask.value))
function formatNumber(value?: number | null) { return typeof value === 'number' && Number.isFinite(value) ? new Intl.NumberFormat('zh-CN').format(value) : '—' }
function formatQuality(value?: number | null) { return typeof value === 'number' && Number.isFinite(value) ? String(value) : '—' }
function formatTime(value?: string | null) { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false }) }
function platformText(value?: string | null) { return platforms.value.find(item => item.platform === value)?.label || value || '—' }
function statusText(value: string) { return ({ idle: '空闲', preparing: '准备中', waiting_for_browser: '等待浏览器', running: '运行中', stopping: '停止中', stopped: '已停止', completed: '已完成', error: '错误', waiting_next_round: '等待下一轮' } as Record<string, string>)[value] || value }
function accessText(value: string) { return ({ public_accessible: '公开可访问', authenticated_accessible: '已登录可访问', public: '公开可访问', auth: '已登录可访问', login_required: '需要人工登录', verification_required: '需要人工验证', content_limited: '正文访问受限', preparing: '准备中', unready: '尚未准备', cdp_unavailable: '浏览器不可用', page_missing: '未找到平台页面', page_error: '页面未就绪', loading: '页面加载中', empty_results: '无搜索结果' } as Record<string, string>)[value] || value }
function accessReasonText(reason: string) {
  const text = ({ no_access_evidence: '页面尚未出现可访问的职位内容', unexpected_domain: '当前页面未到达所选招聘平台', manual_verification_or_access_limit: '需要人工验证或处理访问限制', manual_login_gate: '需要在浏览器中人工登录', visible_page_error: '招聘页面显示错误', document_loading: '招聘页面仍在加载', visible_job_content: '已看到可访问的职位内容', explicit_empty_results: '搜索页已打开，当前搜索没有结果', no_owned_edge: '尚未连接独立采集浏览器', edge_or_cdp_error: '浏览器启动或调试连接失败', no_platform_page: '未找到当前平台页面' } as Record<string, string>)[reason]
  return `${text || '浏览器访问检查未通过'}（${reason}）`
}
function outcomeText(value?: string | null) { return ({ inserted: '新增入库', updated: '更新入库', skipped: '跳过', rejected: '拒绝', failed: '失败', complete: '完整 JD' } as Record<string, string>)[value || ''] || value || '未记录' }
function sourceUrl(value?: string | null) { try { const url = new URL(value || ''); return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : undefined } catch { return undefined } }
function errorText(error: unknown) {
  const response = (error as { response?: { data?: { detail?: unknown; message?: unknown } } } | null)?.response?.data
  const detail = response?.detail || response?.message
  return typeof detail === 'string' ? detail : error instanceof Error ? error.message : String(error)
}

let resultsRequest = 0
async function loadResults() {
  const request = ++resultsRequest
  const runId = currentTask.value.run_id
  results.value = []
  resultsError.value = ''
  resultsLoading.value = !!runId
  if (!runId) return
  try { const rows = await getCollectionResults(runId); if (request === resultsRequest && currentTask.value.run_id === runId) results.value = rows }
  catch (error) { if (request === resultsRequest) resultsError.value = `本轮结果读取失败：${errorText(error)}` }
  finally { if (request === resultsRequest) resultsLoading.value = false }
}
async function loadStatus() { currentTask.value = await getCollectionStatus(); await loadResults() }
async function loadHistory() {
  try { const value = await getCollectionHistory({ page: historyPage.value, page_size: 20 }); history.value = value.items; historyTotal.value = value.total }
  catch (error) { history.value = []; historyTotal.value = 0; throw error }
}
async function loadStats() {
  try { stats.value = await getDatabaseStats() }
  catch (error) { stats.value = { available: false, error: errorText(error), database_total: null, platform_counts: [] } }
}
async function loadBrowserStatus() {
  if (preparing.value) return
  const request = ++browserRequest
  try {
    const value = await getCDPStatus()
    if (request !== browserRequest) return
    cdpStatus.value = value
    const currentAccess = value.platform_access?.[configForm.platform || '']
    if (!value.reachable || (currentAccess && (!currentAccess.can_collect || currentAccess.content_limited))) {
      preparedFor.value = null
    }
  } catch (error) {
    if (request !== browserRequest) return
    cdpStatus.value = { reachable: false, error: errorText(error) }
    preparedFor.value = null
    throw error
  }
}
async function refreshAll() {
  if (refreshing.value) return
  refreshing.value = true
  const checks = await Promise.allSettled([loadStatus(), loadStats(), loadHistory(), loadBrowserStatus()])
  refreshErrors.value = checks.flatMap((result, index) => result.status === 'rejected' ? [`${['进度', '数据库', '历史', '浏览器状态'][index]}读取失败：${errorText(result.reason)}`] : [])
  refreshing.value = false
}
async function prepareBrowser() {
  if (preparing.value || busy.value || starting.value) return
  if (!configValid.value) { ElMessage.warning('请检查配置：选择支持的平台、1 个不超过 80 字的关键词及对应城市，页数为 1，列表和详情上限为 1–5。'); return }
  const platform = configForm.platform!
  const request = ++browserRequest
  preparing.value = true
  preparation.value = null
  preparedFor.value = null
  cdpStatus.value = null
  try {
    const result = await prepareCollection(false, platform, { keywords: [keyword.value.trim()], cities: configForm.cities.map(city => ({ ...city })), pages: configForm.pages, detail_limit: configForm.detail_limit, max_jobs: configForm.max_jobs })
    if (request === browserRequest) { preparation.value = result; cdpStatus.value = result.cdp; preparedFor.value = result.can_collect ? platform : null }
  } catch (error) {
    if (request === browserRequest) {
      const detail = errorText(error)
      preparation.value = { access_state: 'unready', can_collect: false, message: /timeout|timed out|ECONNABORTED/i.test(detail) ? '浏览器准备超时，请刷新状态或重新检查。' : `浏览器准备失败：${detail}`, cdp: { reachable: false } }
    }
  }
  finally { preparing.value = false }
}
async function startTask() {
  if (!canStart.value) return
  starting.value = true
  try {
    const task = await startCollection({ platform: configForm.platform, mode: 'once', keywords: [keyword.value.trim()], cities: configForm.cities.map(city => ({ ...city })), pages: configForm.pages, detail_limit: configForm.detail_limit, max_jobs: configForm.max_jobs, rounds: 1, check_cdp_before_start: true })
    currentTask.value = { run_id: task.run_id, platform: configForm.platform, status: task.status || 'preparing' }
    preparedFor.value = null
    ElMessage.info(task.message || '本轮任务已提交，请查看进度与停止原因。')
    await refreshAll()
  } catch (error) { ElMessage.error(`任务提交失败：${errorText(error)}`) }
  finally { starting.value = false }
}
async function stopTask() {
  if (!canStop.value) return
  stopping.value = true
  try { await stopCollection(currentTask.value.run_id); preparedFor.value = null; await refreshAll() }
  catch (error) { ElMessage.error(`停止失败：${errorText(error)}`) }
  finally { stopping.value = false }
}
let historyRequest = 0
async function openHistory(task: CollectionTask) {
  const request = ++historyRequest
  selectedTask.value = task
  showHistory.value = true
  historyResults.value = []
  historyResultsError.value = ''
  historyLoading.value = !!task.run_id
  if (!task.run_id) return
  try { const rows = await getCollectionResults(task.run_id); if (request === historyRequest) historyResults.value = rows }
  catch (error) { if (request === historyRequest) historyResultsError.value = `历史结果读取失败：${errorText(error)}` }
  finally { if (request === historyRequest) historyLoading.value = false }
}
let rawRequest = 0
async function openRaw(row: CollectionResult) {
  const request = ++rawRequest
  eventRecord.value = row
  showRaw.value = true
  rawRecord.value = null
  rawError.value = ''
  rawLoading.value = !!row.jd_pool_id
  if (!row.jd_pool_id) return
  try { const record = await getCollectionRaw(row.jd_pool_id); if (request === rawRequest) rawRecord.value = record }
  catch (error) { if (request === rawRequest) rawError.value = `数据库原文读取失败：${errorText(error)}` }
  finally { if (request === rawRequest) rawLoading.value = false }
}
let timer: ReturnType<typeof setInterval> | null = null
onMounted(async () => {
  const configChecks = await Promise.allSettled([getCollectionPlatforms(), getCollectionConfig()])
  if (configChecks[0].status === 'fulfilled') platforms.value = configChecks[0].value
  if (configChecks[1].status === 'fulfilled') {
    const saved = configChecks[1].value
    configForm.platform = saved.platform || platforms.value.find(item => item.supported)?.platform || 'boss'
    configForm.keywords = saved.keywords?.length ? [saved.keywords[0]!] : []
    const city = availableCities.value.find(item => item.code === saved.cities?.[0]?.code)
    configForm.cities = city ? [{ ...city }] : []
    configForm.detail_limit = Math.max(1, Math.min(5, saved.detail_limit || 5))
    configForm.max_jobs = Math.max(1, Math.min(5, saved.max_jobs || 5))
  }
  await refreshAll()
  refreshErrors.value.push(...configChecks.flatMap((result, index) => result.status === 'rejected' ? [`${index === 0 ? '平台' : '配置'}读取失败：${errorText(result.reason)}`] : []))
  timer = setInterval(() => { if (!refreshing.value) void refreshAll() }, 5000)
})
onUnmounted(() => { if (timer) clearInterval(timer); resultsRequest++; historyRequest++; rawRequest++; browserRequest++ })
</script>

<style scoped>
.collection-page { --muted: #8c8581; }
.page-title p, .section-heading p { color: var(--muted); line-height: 1.65; }
.panel { margin: 18px 0; padding: 24px; border-radius: 16px; }
h2 { display: flex; align-items: center; gap: 10px; margin: 0 0 12px; font-size: 18px; }
h3 { margin-top: 24px; font-size: 15px; }
.step { display: inline-grid; place-items: center; width: 26px; height: 26px; background: #edf3fa; color: #688db5; border-radius: 8px; font-size: 14px; }
.config-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 24px; }
.config-grid :deep(.el-select), .config-grid :deep(.el-input-number) { width: 100%; }
.action-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.action-grid .panel { margin: 0; }
.action-grid p { color: var(--muted); line-height: 1.7; }
.launch-panel { border: 1px solid #dce8f5; background: #fafdff; }
.launch-summary { font-size: 16px; color: var(--text) !important; }
.access-row, .button-row, .gate-note { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin: 16px 0; }
.access-row span, .gate-note span, .hint { font-size: 12px; line-height: 1.7; color: var(--muted); }
.gate-note { margin-bottom: 0; padding-top: 12px; border-top: 1px solid var(--line); }
.task-context, .source-meta, .quality-row { display: flex; gap: 12px 22px; flex-wrap: wrap; font-size: 12px; color: var(--muted); margin: 14px 0; }
.count-grid { display: grid; grid-template-columns: repeat(9, minmax(0, 1fr)); gap: 10px; margin: 18px 0; }
.count-grid > div { padding: 18px 8px; background: #f8fafc; border-radius: 12px; text-align: center; }
.count-grid strong { display: block; color: var(--text); font-size: 24px; margin-bottom: 7px; }
.count-grid span { font-size: 12px; color: var(--muted); }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(115px, 1fr)); gap: 12px; margin-top: 18px; }
.stats-grid > div { padding: 18px; border-radius: 10px; background: #fcfaf8; }
.stats-grid span { font-size: 12px; color: var(--muted); }
.stats-grid strong { display: block; font-size: 22px; margin-top: 8px; }
.mono { font-family: ui-monospace, Consolas, monospace; overflow-wrap: anywhere; }
.raw-text { padding: 16px; background: #f7f8fa; border-radius: 10px; white-space: pre-wrap; overflow-wrap: anywhere; font: 13px/1.8 inherit; }
.raw-db { min-height: 70px; }
.source-detail { overflow-wrap: anywhere; font-size: 13px; line-height: 1.7; }
.source-detail a { color: #547fae; }
.el-alert { margin: 12px 0; }
.el-pagination { justify-content: flex-end; margin-top: 18px; }
@media (max-width: 1100px) { .count-grid { grid-template-columns: repeat(5, 1fr); } }
@media (max-width: 760px) { .config-grid, .action-grid { grid-template-columns: 1fr; } .count-grid { grid-template-columns: repeat(3, 1fr); } .panel { padding: 18px; } .page-title, .section-heading { flex-wrap: wrap; gap: 12px; } }
</style>
