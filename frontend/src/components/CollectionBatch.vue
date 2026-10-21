<template>
  <section class="batch-panel panel" aria-label="批量采集计划">
    <div class="section-heading"><div><h2>批量采集计划</h2><p>单平台、多关键词 × 多城市。先保存待执行计划，再显式开始串行采集。</p></div><el-button :loading="refreshing" @click="refreshBatches">刷新批次</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <el-form class="batch-grid" label-position="top" :disabled="mutating">
      <el-form-item label="批次平台"><el-select v-model="platform" aria-label="批次平台"><el-option v-for="item in platforms" :key="item.platform" :label="item.supported ? item.label : `${item.label}（暂未接入）`" :value="item.platform" :disabled="!item.supported" /></el-select></el-form-item>
      <el-form-item label="关键词（最多 10 个，可输入新增）"><el-select v-model="keywords" multiple filterable allow-create default-first-option placeholder="输入关键词后按 Enter 添加" aria-label="批次关键词"><el-option v-for="word in keywordOptions" :key="word" :label="word" :value="word" /></el-select></el-form-item>
      <el-form-item label="批次城市"><el-select v-model="cityCodes" multiple filterable :disabled="!availableCities.length" placeholder="选择当前平台城市" aria-label="批次城市"><el-option v-for="city in availableCities" :key="city.code" :label="city.name" :value="city.code" /></el-select></el-form-item>
      <el-form-item label="每项页数"><el-input-number :model-value="1" disabled /></el-form-item>
      <el-form-item label="每项列表上限"><el-input-number v-model="maxJobs" :min="1" :max="5" :precision="0" /></el-form-item>
      <el-form-item label="每项详情尝试上限"><el-input-number v-model="detailLimit" :min="1" :max="5" :precision="0" /></el-form-item>
    </el-form>
    <p class="hint">{{ normalizedKeywords.length }} 个关键词 × {{ selectedCities.length }} 个城市 = {{ combinations.length }} 个组合（最多 50）。{{ validationHint }}</p>
    <el-collapse v-if="combinations.length"><el-collapse-item :title="`预览全部 ${combinations.length} 个组合`" name="preview"><div class="combination-tags"><el-tag v-for="row in combinations" :key="JSON.stringify([row.keyword, row.city.code])" effect="plain">{{ row.keyword }} · {{ row.city.name }}</el-tag></div></el-collapse-item></el-collapse>
    <div class="button-row"><el-button type="primary" :disabled="!canCreate" :loading="creating" @click="createBatch">创建批次计划</el-button><span class="hint">仅保存待执行计划；不会准备浏览器或启动采集。</span></div>
    <el-alert :title="`串行低速执行：组合间隔沿现有配置 ${intervalText}；登录、验证或正文受限时自动停止后续，不自动重试。`" type="info" :closable="false" />
    <h3>最近批次</h3>
    <el-table :data="batches" empty-text="暂无批次计划" stripe>
      <el-table-column prop="batch_id" label="批次 ID" min-width="180" show-overflow-tooltip />
      <el-table-column label="平台" width="100"><template #default="{ row }">{{ platformText(row.platform) }}</template></el-table-column>
      <el-table-column label="状态" width="125"><template #default="{ row }">{{ statusText(row.status) }}</template></el-table-column>
      <el-table-column label="已处理 / 总项数" width="145"><template #default="{ row }">{{ row.completed }} / {{ row.total }}</template></el-table-column>
      <el-table-column label="创建时间" min-width="170"><template #default="{ row }">{{ formatTime(row.created_at) }}</template></el-table-column>
      <el-table-column label="详情" width="100"><template #default="{ row }"><el-button link type="primary" :disabled="mutating" @click="selectBatch(row.batch_id)">查看批次</el-button></template></el-table-column>
    </el-table>
    <div v-if="selectedBatch" v-loading="detailLoading" class="batch-detail">
      <div class="section-heading"><div><h3>批次 {{ selectedBatch.batch_id }}</h3><p>{{ platformText(selectedBatch.platform) }} · {{ statusText(selectedBatch.status) }} · 已处理 {{ selectedBatch.completed }} / {{ selectedBatch.total }}；处理结束不代表采集成功。</p></div><el-tag>{{ statusText(selectedBatch.status) }}</el-tag></div>
      <div class="button-row"><el-button type="primary" :disabled="!canStart" :loading="starting" @click="startBatch">开始批次</el-button><el-button type="danger" plain :disabled="!canStop" :loading="stopping" @click="stopBatch">停止整个批次</el-button></div>
      <p class="hint">{{ launchHint }}</p>
      <p v-if="selectedBatch.next_run_at" class="hint">下一项预计开始：{{ formatTime(selectedBatch.next_run_at) }}；等待期间可停止整个批次。</p>
      <el-alert v-if="selectedBatch.stop_reason" :title="`停止原因：${selectedBatch.stop_reason}`" type="warning" :closable="false" />
      <el-table :data="selectedBatch.items" stripe empty-text="暂无组合">
        <el-table-column prop="keyword" label="关键词" min-width="130" /><el-table-column prop="city.name" label="城市" width="90" />
        <el-table-column label="状态" width="100"><template #default="{ row }">{{ statusText(row.status) }}</template></el-table-column>
        <el-table-column v-for="field in countFields" :key="field[0]" :label="field[1]" width="100"><template #default="{ row }">{{ formatCount(row[field[0]]) }}</template></el-table-column>
        <el-table-column prop="stop_reason" label="停止 / 失败原因" min-width="170" show-overflow-tooltip />
        <el-table-column prop="run_id" label="任务 ID" min-width="170" show-overflow-tooltip />
        <el-table-column label="日志与结果" width="115" fixed="right"><template #default="{ row }"><el-button link type="primary" :disabled="!row.run_id || inspecting" @click="inspectItem(row)">查看单项</el-button></template></el-table-column>
      </el-table>
      <p class="hint">“—”表示尚无可信计数。待执行项没有 run_id；已有任务的日志、结果及原文复用单轮查看入口。</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { createCollectionBatch, getCollectionBatch, getCollectionBatches, getCollectionBatchItemTask, getCollectionConfig, startCollectionBatch, stopCollectionBatch, type CollectionBatch, type CollectionBatchItem, type CollectionPlatform, type CollectionTask } from '../api/collection'

const props = defineProps<{ platforms: CollectionPlatform[]; singleBusy: boolean }>()
const emit = defineEmits<{ (event: 'busy', value: boolean): void; (event: 'inspect', value: CollectionTask): void }>()
const platform = ref('boss')
const keywords = ref<string[]>([])
const cityCodes = ref<string[]>([])
const maxJobs = ref(5)
const detailLimit = ref(5)
const batches = ref<CollectionBatch[]>([])
const selectedBatch = ref<CollectionBatch | null>(null)
const selectedId = ref('')
const creating = ref(false)
const starting = ref(false)
const stopping = ref(false)
const inspecting = ref(false)
const refreshing = ref(false)
const detailLoading = ref(false)
const error = ref('')
const intervalText = ref('6–12 分钟（默认）')
const keywordOptions = computed(() => [...new Set(['Python', 'Java', '前端开发', ...keywords.value])])
const selectedPlatform = computed(() => props.platforms.find(item => item.platform === platform.value))
const availableCities = computed(() => selectedPlatform.value?.cities || [])
const normalizedKeywords = computed(() => [...new Set(keywords.value.map(word => word.trim()).filter(Boolean))])
const uniqueCodes = computed(() => [...new Set(cityCodes.value)])
const selectedCities = computed(() => uniqueCodes.value.flatMap(code => { const city = availableCities.value.find(item => item.code === code); return city ? [{ ...city }] : [] }))
const combinations = computed(() => normalizedKeywords.value.flatMap(keyword => selectedCities.value.map(city => ({ keyword, city }))))
const mutating = computed(() => creating.value || starting.value || stopping.value)
const validationHint = computed(() => !selectedPlatform.value?.supported ? '请选择已接入平台。' : !normalizedKeywords.value.length || normalizedKeywords.value.length > 10 || normalizedKeywords.value.some(word => word.length > 80) ? '请填写 1–10 个不超过 80 字的有效关键词。' : !selectedCities.value.length || selectedCities.value.length !== uniqueCodes.value.length ? '请选择当前平台的有效城市。' : combinations.value.length > 50 ? '组合超过 50，请减少关键词或城市。' : ![maxJobs.value, detailLimit.value].every(value => Number.isInteger(value) && value >= 1 && value <= 5) ? '列表与详情上限须为 1–5。' : '')
const canCreate = computed(() => !validationHint.value && !mutating.value)
function isActive(batch: CollectionBatch) { return ['running', 'waiting_next_round', 'stopping'].includes(batch.status) }
const activeBatch = computed(() => batches.value.find(isActive) || (selectedBatch.value && isActive(selectedBatch.value) ? selectedBatch.value : null))
const canStart = computed(() => selectedBatch.value?.status === 'queued' && !props.singleBusy && !activeBatch.value && !mutating.value && !detailLoading.value && !refreshing.value)
const canStop = computed(() => !!selectedBatch.value && (isActive(selectedBatch.value) || selectedBatch.value.status === 'queued') && !mutating.value && !detailLoading.value)
const launchHint = computed(() => props.singleBusy ? '单轮任务正在准备或运行；批次与单轮互斥，请先停止当前任务。' : activeBatch.value && activeBatch.value.batch_id !== selectedId.value ? `批次 ${activeBatch.value.batch_id} 正在执行，请先停止该批次。` : selectedBatch.value?.status === 'queued' ? '计划尚未启动。点击“开始批次”后才会准备浏览器并执行。' : '停止会取消后续待执行项，并等待当前单项实际停止；不会自动重试或恢复。')
watch(platform, () => { cityCodes.value = [] }, { flush: 'sync' })
watch(() => props.platforms, () => { if (!selectedPlatform.value?.supported) platform.value = props.platforms.find(item => item.supported)?.platform || '' }, { immediate: true })
watch(() => !!activeBatch.value || starting.value || stopping.value, value => emit('busy', value), { immediate: true, flush: 'sync' })

const countFields = [['listed', '列表识别'], ['detail_attempted', '详情尝试'], ['detail_obtained', '详情取得'], ['content_eligible', '内容合格'], ['identity_pending', '身份待审'], ['identity_verified', '身份已验证'], ['complete', '完整 JD'], ['inserted', '新增入库'], ['updated', '更新入库'], ['skipped', '跳过'], ['rejected', '拒绝'], ['failed', '失败']] as const
function formatCount(value?: number | null) { return typeof value === 'number' && Number.isFinite(value) ? String(value) : '—' }
function formatTime(value?: string | null) { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false }) }
function platformText(value: string) { return props.platforms.find(item => item.platform === value)?.label || value }
function statusText(value: string) { return ({ queued: '待执行', preparing: '准备中', running: '运行中', waiting_next_round: '等待下一项', stopping: '停止中', stopped: '已停止', completed: '已完成', blocked: '访问受限', error: '失败', cancelled: '已取消', interrupted: '已中断' } as Record<string, string>)[value] || value }
function errorText(value: unknown) { const data = (value as { response?: { data?: { detail?: unknown; message?: unknown } } } | null)?.response?.data; return typeof data?.detail === 'string' ? data.detail : typeof data?.message === 'string' ? data.message : value instanceof Error ? value.message : String(value) }
let disposed = false
let listRequest = 0
let detailRequest = 0
let inspectRequest = 0
let timer: ReturnType<typeof setInterval> | null = null
function saveBatch(batch: CollectionBatch) { batches.value = [batch, ...batches.value.filter(item => item.batch_id !== batch.batch_id)]; selectedId.value = batch.batch_id; selectedBatch.value = batch }
async function selectBatch(id: string) {
  if (mutating.value || disposed) return
  if (id !== selectedId.value) { inspectRequest++; inspecting.value = false }
  const request = ++detailRequest
  selectedId.value = id
  selectedBatch.value = batches.value.find(item => item.batch_id === id) || null
  detailLoading.value = true
  try { const batch = await getCollectionBatch(id); if (!disposed && request === detailRequest && selectedId.value === id) selectedBatch.value = batch }
  catch (reason) { if (!disposed && request === detailRequest) error.value = `批次详情读取失败：${errorText(reason)}` }
  finally { if (!disposed && request === detailRequest) detailLoading.value = false }
}
async function refreshBatches() {
  if (refreshing.value || mutating.value || disposed) return
  const request = ++listRequest
  refreshing.value = true
  error.value = ''
  try {
    const value = await getCollectionBatches()
    if (disposed || request !== listRequest) return
    batches.value = value.items
    const id = selectedId.value || value.items[0]?.batch_id
    if (id) await selectBatch(id)
  } catch (reason) { if (!disposed && request === listRequest) error.value = `批次列表读取失败：${errorText(reason)}` }
  finally { if (!disposed) refreshing.value = false }
}
async function createBatch() {
  if (!canCreate.value || disposed) return
  creating.value = true; error.value = ''; listRequest++; detailRequest++
  try { const value = await createCollectionBatch({ platform: platform.value, keywords: normalizedKeywords.value, cities: selectedCities.value, pages: 1, max_jobs: maxJobs.value, detail_limit: detailLimit.value }); if (!disposed) saveBatch(value) }
  catch (reason) { if (!disposed) error.value = `计划创建失败：${errorText(reason)}` }
  finally { if (!disposed) { creating.value = false; detailLoading.value = false } }
}
async function startBatch() {
  if (!canStart.value || !selectedBatch.value || disposed) return
  const id = selectedBatch.value.batch_id
  starting.value = true; error.value = ''; listRequest++; detailRequest++
  try { const value = await startCollectionBatch(id); if (!disposed) saveBatch(value) }
  catch (reason) { if (!disposed) error.value = `批次启动失败：${errorText(reason)}` }
  finally { if (!disposed) starting.value = false }
}
async function stopBatch() {
  if (!canStop.value || !selectedBatch.value || disposed) return
  const id = selectedBatch.value.batch_id
  stopping.value = true; error.value = ''; listRequest++; detailRequest++
  try { const value = await stopCollectionBatch(id); if (!disposed) saveBatch(value) }
  catch (reason) { if (!disposed) error.value = `批次停止失败：${errorText(reason)}` }
  finally { if (!disposed) stopping.value = false }
}
async function inspectItem(item: CollectionBatchItem) {
  if (!item.run_id || !selectedBatch.value || disposed) return
  const batchId = selectedBatch.value.batch_id
  const request = ++inspectRequest
  inspecting.value = true; error.value = ''
  try {
    const task = await getCollectionBatchItemTask(batchId, item.item_id)
    if (disposed || request !== inspectRequest || selectedBatch.value?.batch_id !== batchId) return
    if (task.run_id !== item.run_id) throw new Error('单项任务 ID 不匹配，请刷新批次后重试')
    emit('inspect', task)
  } catch (reason) { if (!disposed && request === inspectRequest) error.value = `单项日志读取失败：${errorText(reason)}` }
  finally { if (!disposed && request === inspectRequest) inspecting.value = false }
}
onMounted(async () => {
  try { const config = await getCollectionConfig(); if (!disposed) intervalText.value = `${(config.switch_interval_min ?? 360) / 60}–${(config.switch_interval_max ?? 720) / 60} 分钟` }
  catch { if (!disposed) intervalText.value = '6–12 分钟（默认；现有配置读取失败，以服务端配置为准）' }
  if (disposed) return
  await refreshBatches()
  if (!disposed) timer = setInterval(() => refreshBatches(), 5000)
})
onUnmounted(() => { disposed = true; if (timer) clearInterval(timer); listRequest++; detailRequest++; inspectRequest++ })
</script>

<style scoped>
.batch-panel { margin: 18px 0; padding: 24px; border-radius: 16px; }
.batch-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 24px; }
.batch-grid :deep(.el-select), .batch-grid :deep(.el-input-number) { width: 100%; }
h2 { margin: 0 0 12px; font-size: 18px; }
h3 { margin: 24px 0 12px; font-size: 15px; overflow-wrap: anywhere; }
.section-heading p, .hint { color: #8c8581; font-size: 12px; line-height: 1.7; }
.combination-tags, .button-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 16px 0; }
.batch-detail { margin-top: 24px; }
.el-alert { margin: 12px 0; }
@media (max-width: 760px) { .batch-grid { grid-template-columns: 1fr; } .batch-panel { padding: 18px; } .section-heading { flex-wrap: wrap; gap: 12px; } }
</style>
