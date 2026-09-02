<template>
  <section class="page collection-page">
    <div class="page-title">
      <div class="title-left">
        <div class="module-mark collection-mark"><el-icon><Connection /></el-icon></div>
        <div><h1>采集模块管理</h1><p>进入页面自动准备独立 Edge；已登录时尝试单轮采集，未登录则提示</p></div>
      </div>
      <div class="page-actions">
        <el-button class="btn-soft" :loading="refreshing" @click="refreshAll"><el-icon><Refresh /></el-icon>刷新状态</el-button>
        <el-button class="btn-coral" @click="showConfigDialog = true"><el-icon><Setting /></el-icon>采集配置</el-button>
      </div>
    </div>

    <div class="collection-status-grid" v-loading="refreshing">
      <article v-for="card in statusCards" :key="card.label" class="collection-status-card">
        <div class="status-icon" :class="card.tone"><el-icon><component :is="card.icon" /></el-icon></div>
        <div><small>{{ card.label }}</small><strong>{{ card.value }}</strong><span>{{ card.sub }}</span></div>
      </article>
    </div>

    <section class="panel collection-control-panel">
      <div class="section-heading"><div><h2>任务控制</h2><p>进入本页会自动准备浏览器并尝试单轮采集；系统不会自动登录或绕过验证。</p></div><el-tag :type="canStart ? 'success' : 'warning'" effect="plain">{{ canStart ? '可启动' : '任务进行中' }}</el-tag></div>
      <div class="control-row">
        <div class="platform-switch"><span>采集平台</span><el-radio-group v-model="configForm.platform" size="small"><el-radio-button value="boss">BOSS</el-radio-button><el-radio-button value="zhaopin">智联</el-radio-button><el-radio-button value="liepin">猎聘</el-radio-button></el-radio-group></div>
        <div class="mode-switch"><span>运行模式</span><el-radio-group v-model="startMode" size="small"><el-radio-button value="once">单轮验证</el-radio-button><el-radio-button value="limited">指定轮数</el-radio-button><el-radio-button value="continuous">持续运行</el-radio-button></el-radio-group><el-input-number v-if="startMode === 'limited'" v-model="rounds" :min="1" :max="100" size="small" /></div>
        <div class="control-actions"><el-button class="start-button" :disabled="!canStart" :loading="actionLoading" @click="startTask"><el-icon><VideoPlay /></el-icon>启动采集</el-button><el-button class="stop-button" :disabled="!canStop" :loading="actionLoading" @click="stopTask"><el-icon><VideoPause /></el-icon>停止任务</el-button></div>
      </div>
      <div class="control-note"><el-icon><InfoFilled /></el-icon><span>当前配置：{{ configSummary }}。采集器只读取用户已人工登录的 Edge 页面。</span></div>
    </section>

    <section class="panel progress-panel">
      <div class="section-heading"><div><h2>实时进度</h2><p>刷新页面不会丢失最近一次任务汇总</p></div><el-button text class="refresh-text" @click="loadStatus"><el-icon><RefreshRight /></el-icon>刷新进度</el-button></div>
      <div class="target-grid">
        <div><small>当前关键词</small><strong>{{ currentTask.current_keyword || '—' }}</strong></div>
        <div><small>当前城市</small><strong>{{ currentTask.current_city || '—' }}</strong></div>
        <div><small>轮次</small><strong>{{ currentTask.current_round || 0 }}<em v-if="currentTask.total_rounds"> / {{ currentTask.total_rounds }}</em></strong></div>
        <div><small>任务 ID</small><strong class="mono">{{ currentTask.run_id || '暂无任务' }}</strong></div>
      </div>
      <div class="progress-count-grid">
        <div v-for="item in progressItems" :key="item.label" class="progress-count"><strong>{{ item.value }}</strong><span>{{ item.label }}</span></div>
      </div>
      <div v-if="currentTask.last_error" class="error-note"><el-icon><WarningFilled /></el-icon>{{ currentTask.last_error }}</div>
    </section>

    <section class="panel stats-panel">
      <div class="section-heading"><div><h2>数据统计</h2><p>数据库累计数据与当前采集平台来源质量</p></div><el-button text class="refresh-text" @click="loadStats"><el-icon><RefreshRight /></el-icon>刷新统计</el-button></div>
      <div class="stats-number-grid">
        <div v-for="item in statItems" :key="item.label" class="stat-number-card"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div>
      </div>
      <div class="platform-breakdown">
        <div class="quality-title">中文平台岗位</div>
        <div class="platform-breakdown-grid"><div v-for="item in stats.platform_counts" :key="item.platform"><span>{{ item.label }}</span><strong>{{ formatNumber(item.count) }}</strong></div></div>
      </div>
      <div class="quality-block"><div class="quality-title">数据质量</div><div class="quality-grid"><div v-for="item in qualityItems" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div></div></div>
    </section>

    <section class="panel history-panel">
      <div class="section-heading"><div><h2>历史任务</h2><p>仅记录通过本控制台启动的采集任务</p></div><div class="history-filters"><el-select v-model="historyFilter.status" placeholder="状态筛选" clearable size="small" style="width:130px"><el-option label="已完成" value="completed" /><el-option label="已停止" value="stopped" /><el-option label="错误" value="error" /></el-select><el-select v-model="historyFilter.mode" placeholder="模式筛选" clearable size="small" style="width:130px"><el-option label="单轮" value="once" /><el-option label="指定轮数" value="limited" /><el-option label="持续" value="continuous" /></el-select></div></div>
      <el-table :data="filteredHistory" stripe size="small" style="width:100%"><el-table-column prop="run_id" label="任务 ID" min-width="190" /><el-table-column label="平台" width="100"><template #default="{ row }"><el-tag size="small" effect="plain">{{ platformText(row.platform) }}</el-tag></template></el-table-column><el-table-column label="模式" width="100"><template #default="{ row }"><el-tag size="small" effect="plain">{{ modeText(row.mode) }}</el-tag></template></el-table-column><el-table-column label="状态" width="100"><template #default="{ row }"><el-tag size="small" :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag></template></el-table-column><el-table-column label="开始时间" min-width="160"><template #default="{ row }">{{ formatTime(row.started_at) }}</template></el-table-column><el-table-column label="结束时间" min-width="160"><template #default="{ row }">{{ formatTime(row.finished_at) }}</template></el-table-column><el-table-column prop="listed" label="列表" width="70" /><el-table-column prop="details" label="详情" width="70" /><el-table-column prop="new" label="新增" width="70" /><el-table-column prop="skipped" label="跳过" width="70" /><el-table-column prop="errors" label="异常" width="70" /><el-table-column label="操作" width="70" fixed="right"><template #default="{ row }"><el-button text class="detail-link" @click="selectedTask = row; showDetailDialog = true">详情</el-button></template></el-table-column></el-table>
      <div v-if="!filteredHistory.length" class="table-empty">暂无控制台历史任务</div>
    </section>

    <el-dialog v-model="showConfigDialog" title="采集参数配置" width="620px" :close-on-click-modal="false">
      <el-form :model="configForm" label-width="110px"><el-form-item label="关键词"><el-select v-model="configForm.keywords" multiple filterable allow-create default-first-option style="width:100%"><el-option v-for="item in defaultKeywords" :key="item" :label="item" :value="item" /></el-select></el-form-item><el-form-item label="城市"><el-select v-model="configForm.cities" multiple value-key="code" style="width:100%"><el-option v-for="item in defaultCities" :key="item.code" :label="item.name" :value="item" /></el-select></el-form-item><el-form-item label="每轮页数"><el-input-number v-model="configForm.pages" :min="1" :max="10" /></el-form-item><el-form-item label="详情上限"><el-input-number v-model="configForm.detail_limit" :min="0" :max="50" /></el-form-item><el-form-item label="岗位上限"><el-input-number v-model="configForm.max_jobs" :min="0" :max="100" /></el-form-item><el-form-item label="页面间隔"><el-slider v-model="pageDelay" range :min="5" :max="60" :step="5" /><span class="form-help">{{ pageDelay[0] }}–{{ pageDelay[1] }} 秒</span></el-form-item><el-form-item label="启动前检查"><el-checkbox v-model="configForm.check_cdp_before_start">检查 CDP 连接和当前平台页面</el-checkbox></el-form-item></el-form>
      <template #footer><el-button class="btn-soft" @click="showConfigDialog = false">取消</el-button><el-button class="btn-coral" :loading="actionLoading" @click="saveConfig">保存配置</el-button></template>
    </el-dialog>

    <el-dialog v-model="showDetailDialog" title="任务详情" width="620px"><div v-if="selectedTask" class="task-detail-list"><div v-for="item in taskDetailItems" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div><div class="task-log"><span>日志状态</span><strong>{{ logStatusText(selectedTask.log_status) }}</strong><pre v-if="selectedTask.raw_log_tail?.length">{{ selectedTask.raw_log_tail.join('\n') }}</pre><small v-else>暂无可读取日志；历史任务不会再显示为无法识别。</small></div></div></el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, Clock, Collection, DataAnalysis, InfoFilled, Refresh, RefreshRight, Setting, VideoPause, VideoPlay, WarningFilled } from '@element-plus/icons-vue'
import { getCDPStatus, getCollectionConfig, getCollectionHistory, getCollectionStats, getCollectionStatus, prepareCollection, startCollection, stopCollection, updateCollectionConfig, type CDPStatus, type CollectionConfig, type CollectionStats, type CollectionTask } from '../api/collection'

const emptyTask: CollectionTask = { run_id: null, platform: 'boss', status: 'idle', mode: 'once', started_at: null, finished_at: null, current_keyword: null, current_city: null, current_round: 0, total_rounds: null, listed: 0, details: 0, new: 0, skipped: 0, errors: 0, last_error: null, next_run_at: null, cdp_status: 'unknown', browser_page_status: null, database_total: 0, database_boss_total: 0, database_new_count: 0 }
const emptyStats: CollectionStats = { database_total: 0, database_boss_total: 0, database_new_count: 0, platform_counts: [], latest_crawled_at: null, data_quality: { empty_source_detail: 0, duplicate_source_detail: 0, placeholder_empty_url: 0, duties_nonempty: 0, status_distribution: [] } }
const currentTask = ref<CollectionTask>({ ...emptyTask })
const cdpStatus = ref<CDPStatus | null>(null)
const stats = ref<CollectionStats>({ ...emptyStats })
const history = ref<CollectionTask[]>([])
const configForm = reactive<CollectionConfig>({ platform: 'boss', mode: 'once', keywords: [], cities: [], pages: 1, detail_limit: 8, max_jobs: 12, page_delay_min: 15, page_delay_max: 30, settle_min: 5, settle_max: 10, switch_interval_min: 360, switch_interval_max: 720, rounds: 0, check_cdp_before_start: true, cdp_endpoint: 'http://127.0.0.1:9333', user_data_dir: null })
const startMode = ref<'once' | 'limited' | 'continuous'>('once')
const rounds = ref(3)
const pageDelay = ref<[number, number]>([15, 30])
const historyFilter = reactive({ status: '', mode: '' })
const refreshing = ref(false)
const actionLoading = ref(false)
const showConfigDialog = ref(false)
const showDetailDialog = ref(false)
const selectedTask = ref<CollectionTask | null>(null)
const defaultKeywords = ['Python', 'Java', '前端', '后端工程师', '数据分析', '数据工程师', 'AI工程师', '机器学习']
const defaultCities = [{ name: '北京', code: '101010100' }, { name: '上海', code: '101020100' }, { name: '深圳', code: '101280600' }, { name: '广州', code: '101280100' }, { name: '杭州', code: '101210100' }, { name: '成都', code: '101270100' }]

const taskStatus = computed(() => currentTask.value.status || 'idle')
const canStart = computed(() => ['idle', 'stopped', 'completed', 'error'].includes(taskStatus.value))
const canStop = computed(() => ['preparing', 'waiting_for_browser', 'running', 'waiting_next_round'].includes(taskStatus.value))
const statusCards = computed(() => [
  { label: '任务状态', value: statusText(taskStatus.value), sub: currentTask.value.run_id ? `ID: ${currentTask.value.run_id}` : '暂无进行中的任务', icon: Clock, tone: taskStatus.value === 'running' ? 'green' : taskStatus.value === 'error' ? 'red' : 'warm' },
  { label: 'CDP 连接', value: cdpStatus.value?.reachable ? '已连接' : '不可达', sub: cdpStatus.value ? `BOSS/智联/猎聘：${Object.values(cdpStatus.value.platform_pages || {}).join('/') || 0}` : '等待检查', icon: Connection, tone: cdpStatus.value?.reachable ? 'green' : 'red' },
  { label: '浏览器页面', value: currentTask.value.browser_page_status || (cdpStatus.value?.platform_pages?.[configForm.platform || 'boss'] ? `${platformText(configForm.platform)} 页面` : '未识别'), sub: `端点：${cdpStatus.value?.endpoint || configForm.cdp_endpoint}`, icon: Collection, tone: cdpStatus.value?.boss_page_count ? 'green' : 'warm' },
  { label: `${platformText(configForm.platform)} 数据`, value: formatNumber(stats.value.platform_counts.find(item => item.platform === configForm.platform)?.count || 0), sub: `全库：${formatNumber(stats.value.database_total)}`, icon: DataAnalysis, tone: 'coral' },
])
const progressItems = computed(() => [{ label: '列表识别', value: currentTask.value.listed }, { label: '详情补采', value: currentTask.value.details }, { label: '新增入库', value: currentTask.value.new }, { label: '跳过重复', value: currentTask.value.skipped }, { label: '异常', value: currentTask.value.errors }])
const statItems = computed(() => [{ label: '全库岗位', value: formatNumber(stats.value.database_total) }, { label: `${platformText(configForm.platform)} 岗位`, value: formatNumber(stats.value.platform_counts.find(item => item.platform === configForm.platform)?.count || 0) }, { label: '本次新增', value: formatNumber(currentTask.value.new || stats.value.database_new_count) }, { label: '最近采集', value: formatTime(stats.value.latest_crawled_at) }])
const qualityItems = computed(() => [{ label: '职责非空', value: stats.value.data_quality.duties_nonempty }, { label: '来源详情为空', value: stats.value.data_quality.empty_source_detail }, { label: '来源详情重复组', value: stats.value.data_quality.duplicate_source_detail }, { label: '占位/空 URL', value: stats.value.data_quality.placeholder_empty_url }])
const filteredHistory = computed(() => history.value.filter(item => (!historyFilter.status || item.status === historyFilter.status) && (!historyFilter.mode || item.mode === historyFilter.mode)))
const configSummary = computed(() => `${startMode.value === 'once' ? '单轮' : startMode.value === 'limited' ? `${rounds.value} 轮` : '持续'} · ${configForm.keywords.length || 0} 个关键词 · ${configForm.cities.length || 0} 个城市`)
const taskDetailItems = computed(() => selectedTask.value ? [{ label: '任务 ID', value: selectedTask.value.run_id || '—' }, { label: '平台', value: platformText(selectedTask.value.platform) }, { label: '模式', value: modeText(selectedTask.value.mode) }, { label: '状态', value: statusText(selectedTask.value.status) }, { label: '关键词', value: selectedTask.value.current_keyword || '—' }, { label: '城市', value: selectedTask.value.current_city || '—' }, { label: '开始时间', value: formatTime(selectedTask.value.started_at) }, { label: '结束时间', value: formatTime(selectedTask.value.finished_at) }, { label: '列表 / 详情', value: `${selectedTask.value.listed} / ${selectedTask.value.details}` }, { label: '新增 / 跳过 / 异常', value: `${selectedTask.value.new} / ${selectedTask.value.skipped} / ${selectedTask.value.errors}` }] : [])

function formatNumber(value: number) { return new Intl.NumberFormat('zh-CN').format(value || 0) }
function formatTime(value: string | null) { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false }) }
function modeText(value: string) { return ({ once: '单轮', limited: '指定轮数', continuous: '持续' } as Record<string, string>)[value] || value }
function statusText(value: string) { return ({ idle: '空闲', preparing: '准备中', waiting_for_browser: '等待浏览器', running: '运行中', waiting_next_round: '等待下一轮', stopped: '已停止', completed: '已完成', error: '错误', auth_required: '需要登录', verification_detected: '需要验证', cdp_unavailable: 'CDP 不可用' } as Record<string, string>)[value] || value }
function platformText(value: string | undefined) { return ({ boss: 'BOSS', zhaopin: '智联', liepin: '猎聘' } as Record<string, string>)[value || ''] || value || '未知' }
function logStatusText(value: string | undefined) { return ({ parsed: '已识别', missing: '日志不存在', empty: '日志为空', unrecognized: '存在但格式未知' } as Record<string, string>)[value || ''] || '未记录' }
function statusTag(value: string) { return ['completed'].includes(value) ? 'success' : ['error', 'auth_required', 'verification_detected', 'cdp_unavailable'].includes(value) ? 'danger' : 'info' }
async function loadStatus() { currentTask.value = await getCollectionStatus() }
async function loadStats() { stats.value = await getCollectionStats() }
async function loadHistory() { history.value = (await getCollectionHistory({ page: 1, page_size: 50 })).items || [] }
async function loadConfig() { const value = await getCollectionConfig(); Object.assign(configForm, value); pageDelay.value = [value.page_delay_min, value.page_delay_max]; startMode.value = value.mode }
async function loadCDP() { cdpStatus.value = await getCDPStatus() }
async function refreshAll() { refreshing.value = true; try { await Promise.all([loadStatus(), loadStats(), loadHistory(), loadConfig(), loadCDP()]); ElMessage.success('状态已刷新') } catch { /* request.ts 已提示 */ } finally { refreshing.value = false } }
async function prepareOnEntry() {
  try {
    const result = await prepareCollection(true, configForm.platform)
    if (result?.status === 'started') {
      ElMessage.success('已登录，已自动启动单轮采集')
      await refreshAll()
    } else if (result?.status === 'login_required') {
      ElMessage.info('已打开采集浏览器，请登录当前平台后再启动采集')
    } else if (result?.status === 'cdp_unavailable') {
      ElMessage.warning('采集浏览器未准备好，请检查 Edge 是否成功打开')
    } else if (result?.status === 'start_failed') {
      ElMessage.warning(result.message || '自动启动采集失败，请使用手动按钮重试')
    }
  } catch { /* request.ts 已提示 */ }
}
async function startTask() {
  try {
    await ElMessageBox.confirm(`确定启动${platformText(configForm.platform)}${startMode.value === 'once' ? '单轮' : startMode.value === 'limited' ? `${rounds.value} 轮` : '持续'}采集吗？浏览器未运行时系统会自动拉起独立 Edge。`, '确认启动', { type: 'info' })
    actionLoading.value = true
    const prepared = await prepareCollection(false, configForm.platform)
    if (prepared?.status === 'login_required') {
      ElMessage.warning('浏览器已打开，请先登录当前平台并打开岗位页面')
      await refreshAll()
      return
    }
    if (prepared?.status !== 'ready') throw new Error(prepared?.message || '浏览器未准备就绪')
    const task = await startCollection({ ...configForm, mode: startMode.value, rounds: startMode.value === 'limited' ? rounds.value : 0 })
    if (task?.run_id) ElMessage.success('已登录，采集任务已启动')
    await refreshAll()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error((error as Error)?.message || '启动失败')
  } finally { actionLoading.value = false }
}
async function stopTask() { try { await ElMessageBox.confirm('确定停止当前采集任务吗？', '确认停止', { type: 'warning' }); actionLoading.value = true; await stopCollection(currentTask.value.run_id); await refreshAll() } catch (error) { if (error !== 'cancel') ElMessage.error((error as Error)?.message || '停止失败') } finally { actionLoading.value = false } }
async function saveConfig() { try { actionLoading.value = true; await updateCollectionConfig({ ...configForm, page_delay_min: pageDelay.value[0], page_delay_max: pageDelay.value[1] }); showConfigDialog.value = false; ElMessage.success('配置已保存'); await loadConfig() } catch (error) { ElMessage.error((error as Error)?.message || '保存失败') } finally { actionLoading.value = false } }
let timer: ReturnType<typeof setInterval> | null = null
onMounted(async () => {
  await refreshAll()
  await prepareOnEntry()
  timer = setInterval(() => { loadStatus().catch(() => {}); loadCDP().catch(() => {}) }, 10000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.module-mark { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 14px; font-size: 23px; }
.collection-mark { color: #6f9dca; background: #eaf3fb; }
.collection-status-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 16px; }
.collection-status-card { display: flex; align-items: center; gap: 14px; min-height: 108px; padding: 20px; background: #fff; border: 1px solid rgba(241,235,228,.8); border-radius: 16px; box-shadow: var(--shadow); }
.status-icon { display: grid; width: 48px; height: 48px; flex: 0 0 auto; place-items: center; border-radius: 50%; font-size: 20px; }
.status-icon.warm { color: #c49a67; background: #fff5e7; }.status-icon.green { color: #78b58f; background: #eaf6ee; }.status-icon.red { color: #db8170; background: #fcefeb; }.status-icon.coral { color: #df8d70; background: #fbedE8; }
.collection-status-card small, .collection-status-card span { display: block; color: #a29d99; font-size: 11px; }.collection-status-card strong { display: block; margin: 4px 0; color: var(--text); font-size: 19px; line-height: 1.2; }
.collection-control-panel, .progress-panel, .stats-panel, .history-panel { margin-bottom: 16px; }
.control-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 15px; border-radius: 12px; background: var(--card-soft); }.platform-switch, .mode-switch, .control-actions { display: flex; align-items: center; gap: 12px; }.platform-switch > span, .mode-switch > span { color: #8e8985; font-size: 12px; }.start-button { --el-button-bg-color: var(--green); --el-button-border-color: var(--green); color: #fff !important; border: 0 !important; }.stop-button { --el-button-bg-color: var(--coral); --el-button-border-color: var(--coral); color: #fff !important; border: 0 !important; }.control-note { display: flex; align-items: center; gap: 7px; margin-top: 12px; color: #a09a96; font-size: 12px; }.control-note .el-icon { color: var(--blue); }
.refresh-text, .detail-link { color: var(--blue) !important; }.target-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }.target-grid > div { padding: 14px; border-radius: 12px; background: var(--card-soft); }.target-grid small, .target-grid strong { display: block; }.target-grid small { margin-bottom: 6px; color: #a29d99; font-size: 11px; }.target-grid strong { overflow: hidden; color: #4b4847; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }.target-grid em { color: #aaa; font-style: normal; }.mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px !important; }.progress-count-grid, .stats-number-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }.progress-count { padding: 14px; border-radius: 12px; background: #fcfaf8; text-align: center; }.progress-count strong { display: block; color: var(--text); font-size: 24px; }.progress-count span, .stat-number-card span { color: #a09a96; font-size: 11px; }.error-note { display: flex; align-items: center; gap: 7px; margin-top: 14px; padding: 10px 12px; border-radius: 10px; background: #fff3f0; color: #c96f5e; font-size: 12px; }.stats-number-grid { grid-template-columns: repeat(4, 1fr); margin-bottom: 16px; }.stat-number-card { padding: 16px; border-radius: 12px; background: var(--card-soft); }.stat-number-card strong { display: block; margin-top: 7px; color: var(--text); font-size: 22px; }.platform-breakdown { margin-bottom: 14px; padding: 16px; border-radius: 12px; background: #fdfbf8; }.platform-breakdown-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }.platform-breakdown-grid > div { padding: 12px; border-radius: 10px; background: #fff; }.platform-breakdown-grid span, .platform-breakdown-grid strong { display: block; }.platform-breakdown-grid span { color: #a09a96; font-size: 11px; }.platform-breakdown-grid strong { margin-top: 4px; color: var(--text); font-size: 20px; }.quality-block { padding: 16px; border-radius: 12px; background: #fcfaf8; }.quality-title { margin-bottom: 12px; font-size: 13px; font-weight: 700; }.quality-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }.quality-grid span, .quality-grid strong { display: block; }.quality-grid span { color: #aaa39e; font-size: 11px; }.quality-grid strong { margin-top: 5px; font-size: 17px; }.history-filters { display: flex; gap: 8px; }.table-empty { padding: 28px 0 5px; color: #a9a39f; font-size: 12px; text-align: center; }.task-detail-list > div { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 11px 0; border-bottom: 1px solid var(--line); }.task-detail-list > div:last-child { border-bottom: 0; }.task-detail-list span { color: #a29d99; font-size: 12px; }.task-detail-list strong { color: var(--text); font-size: 13px; text-align: right; }
.form-help { margin-left: 14px; color: #9b9692; font-size: 12px; }
@media (max-width: 1200px) { .collection-status-grid { grid-template-columns: repeat(2, 1fr); }.control-row { align-items: flex-start; flex-direction: column; }.target-grid { grid-template-columns: repeat(2, 1fr); }.progress-count-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 720px) { .collection-status-grid, .stats-number-grid, .quality-grid, .target-grid, .platform-breakdown-grid { grid-template-columns: 1fr; }.progress-count-grid { grid-template-columns: repeat(2, 1fr); }.platform-switch, .mode-switch, .control-actions { align-items: flex-start; flex-direction: column; }.history-filters { width: 100%; flex-wrap: wrap; }.history-panel :deep(.el-table) { min-width: 900px; }.history-panel { overflow-x: auto; } }
</style>