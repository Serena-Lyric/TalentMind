<template>
  <section class="bridge-panel panel">
    <div class="section-heading">
      <div>
        <h2><span class="step">普通</span>普通浏览器人工采集</h2>
        <p>用于 BOSS 远程调试被自动安全校验阻断时的合规路径。扩展只在你点击按钮时读取当前可见页面。</p>
      </div>
      <div><el-button :disabled="creating || refreshing || finishing" @click="loadPairing">刷新配对信息</el-button><el-tag effect="plain">BOSS · Edge 扩展</el-tag></div>
    </div>

    <el-alert v-if="pairingError" :title="pairingError" type="error" :closable="false" show-icon />
    <el-alert v-if="actionError" :title="actionError" type="error" :closable="false" show-icon />

    <section class="bridge-setup">
      <el-form label-position="top" class="bridge-form" :disabled="!!activeSession || creating || busy">
        <el-form-item label="关键词"><el-input v-model="keyword" maxlength="80" placeholder="例如：Java" /></el-form-item>
        <el-form-item label="城市">
          <el-select v-model="cityCode" placeholder="选择 BOSS 城市">
            <el-option v-for="city in bossPlatform?.cities || []" :key="city.code" :label="city.name" :value="city.code" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="bridge-create">
        <p>创建任务不会打开浏览器、连接 CDP 或启动采集。当前上限固定为一页、最多 5 条列表与 5 条详情。</p>
        <el-button type="primary" :loading="creating" :disabled="creating || !!activeSession || busy" @click="createSession">
          {{ activeSession ? '已有进行中的桥接任务' : '创建桥接任务' }}
        </el-button>
      </div>
    </section>

    <section v-if="session" class="bridge-session">
      <div class="bridge-session-head">
        <div>
          <label>任务 ID</label>
          <p class="mono">{{ session.run_id }}</p>
        </div>
        <el-tag :type="session.finished_at ? 'info' : 'success'">{{ statusText(session.status) }}</el-tag>
      </div>
      <div class="count-grid bridge-counts">
        <div v-for="item in countItems" :key="item.key"><strong>{{ item.value }}</strong><span>{{ item.label }}</span></div>
      </div>

      <details class="bridge-pairing">
        <summary>扩展配对与操作步骤</summary>
        <ol>
          <li>在 Edge 打开 <code>edge://extensions</code>，启用开发人员模式并加载目录：<span class="mono">{{ pairing?.extension_path || 'frontend/bridge-extension' }}</span></li>
          <li>把下方任务 ID 与配对令牌填入 TalentMind 扩展。</li>
          <li>你在普通 Edge 中自行登录、完成正常验证并打开 BOSS 搜索页；系统不会自动处理验证码。</li>
          <li>扩展中先采集当前列表，再手动打开一个真实详情并点击采集详情。重复点击同一详情不会新增重复岗位。</li>
        </ol>
        <div class="pairing-values">
          <span>扩展 ID：<b class="mono">{{ pairing?.extension_id || '—' }}</b></span>
          <span>配对令牌：<b class="mono">{{ pairing?.token || '—' }}</b>
            <el-button link type="primary" :disabled="!pairing?.token" @click="copyToken">复制</el-button>
          </span>
        </div>
      </details>

      <div class="bridge-actions">
        <el-button :loading="refreshing" :disabled="refreshing || finishing" @click="refreshSession">刷新桥接结果</el-button>
        <el-button type="primary" plain :disabled="!!session.finished_at || finishing" @click="finishSession">完成并归档</el-button>
        <el-button type="danger" plain :disabled="!!session.finished_at || finishing" @click="stopSession">停止任务</el-button>
        <el-button @click="inspectSession">日志与逐条结果</el-button>
      </div>
      <el-alert v-if="session.stop_reason || session.last_error" :title="[session.stop_reason, session.last_error].filter(Boolean).join(' · ')" type="warning" :closable="false" show-icon />

      <div class="results-head">
        <h3>当前桥接结果</h3>
        <span>{{ results.length }} 条事件结果</span>
      </div>
      <el-alert v-if="resultsError" :title="resultsError" type="error" :closable="false" />
      <el-table v-loading="resultsLoading" :data="results" stripe empty-text="尚未收到扩展采集请求" style="width:100%">
        <el-table-column prop="job_title" label="岗位" min-width="190" show-overflow-tooltip />
        <el-table-column label="结果" width="105"><template #default="{ row }">{{ outcomeText(row.outcome) }}</template></el-table-column>
        <el-table-column label="身份" width="110"><template #default="{ row }">{{ identityText(row.identity_status) }}</template></el-table-column>
        <el-table-column prop="jd_pool_id" label="jd_pool ID" width="105" />
        <el-table-column prop="rejection_reason" label="拒绝 / 失败原因" min-width="170" show-overflow-tooltip />
      </el-table>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createBridgeSession,
  finishBridgeSession,
  getBridgePairing,
  getBridgeSession,
  getCollectionResults,
  type CollectionBridgePairing,
  type CollectionBridgeSession,
  type CollectionPlatform,
  type CollectionResult,
} from '../api/collection'

const props = defineProps<{ platforms: CollectionPlatform[]; singleBusy?: boolean }>()
const emit = defineEmits<{
  busy: [value: boolean]
  changed: []
  inspect: [task: { run_id: string; platform: string; status: string }]
}>()

const bossPlatform = computed(() => props.platforms.find(item => item.platform === 'boss'))
const keyword = ref('')
const cityCode = ref('')
const pairing = ref<CollectionBridgePairing | null>(null)
const pairingError = ref('')
const session = ref<CollectionBridgeSession | null>(null)
const results = ref<CollectionResult[]>([])
const resultsError = ref('')
const resultsLoading = ref(false)
const actionError = ref('')
const creating = ref(false)
const refreshing = ref(false)
const finishing = ref(false)
const busy = computed(() => !!props.singleBusy)
const activeSession = computed(() => session.value && !session.value.finished_at ? session.value : null)
let resultRequest = 0
let timer: ReturnType<typeof setInterval> | null = null

watch(() => !!activeSession.value, value => emit('busy', value), { immediate: true })

const countItems = computed(() => [
  ['listed', '列表'], ['detail_attempted', '详情尝试'], ['detail_obtained', '详情取得'],
  ['content_eligible', '内容合格'], ['identity_verified', '身份已验证'], ['complete', '完整 JD'],
  ['inserted', '新增'], ['updated', '更新'], ['skipped', '跳过'], ['rejected', '拒绝'], ['failed', '失败'],
].map(([key, label]) => ({ key, label, value: formatNumber(session.value?.[key as keyof CollectionBridgeSession] as number | null | undefined) })))

function formatNumber(value?: number | null) {
  return typeof value === 'number' && Number.isFinite(value) ? new Intl.NumberFormat('zh-CN').format(value) : '—'
}
function statusText(value: string) {
  return ({ waiting_for_capture: '等待人工采集', completed: '已完成', stopped: '已停止', error: '错误' } as Record<string, string>)[value] || value
}
function outcomeText(value?: string | null) {
  return ({ listed: '已识别列表', inserted: '新增入库', updated: '更新入库', skipped: '重复跳过', rejected: '已拒绝', failed: '失败', complete: '详情合格' } as Record<string, string>)[value || ''] || value || '未记录'
}
function identityText(value?: string | null) {
  return ({ verified: '身份已验证', pending: '身份待审', unknown: '身份未知' } as Record<string, string>)[value || ''] || '身份未知'
}
function errorText(error: unknown) {
  const response = (error as { response?: { data?: { detail?: unknown; message?: unknown } } } | null)?.response?.data
  const detail = response?.detail || response?.message
  return typeof detail === 'string' ? detail : error instanceof Error ? error.message : String(error)
}

async function loadPairing() {
  pairingError.value = ''
  try {
    pairing.value = await getBridgePairing()
    if (!cityCode.value && bossPlatform.value?.cities[0]) cityCode.value = bossPlatform.value.cities[0].code
    if (!session.value) {
      session.value = pairing.value.sessions.find(item => !item.finished_at) || null
      if (session.value) await refreshSession()
    }
  } catch (error) {
    pairing.value = null
    pairingError.value = `桥接配对信息读取失败：${errorText(error)}`
  }
}

async function createSession() {
  actionError.value = ''
  if (props.singleBusy) return
  const city = bossPlatform.value?.cities.find(item => item.code === cityCode.value)
  if (!pairing.value?.token) {
    ElMessage.warning('桥接令牌或配对信息不可用，请先刷新配对信息。')
    return
  }
  if (!keyword.value.trim() || !city) {
    ElMessage.warning('请填写关键词并选择当前 BOSS 城市。')
    return
  }
  creating.value = true
  try {
    const created = await createBridgeSession({
      platform: 'boss',
      keyword: keyword.value.split(/\s+/).filter(Boolean).join(' '),
      city_name: city.name,
      city_code: city.code,
      pages: 1,
      detail_limit: 5,
      max_jobs: 5,
    })
    session.value = created.session
    results.value = []
    emit('busy', true)
    emit('changed')
    ElMessage.info('桥接任务已创建；请到普通 Edge 中使用扩展显式采集。')
  } catch (error) {
    actionError.value = `创建桥接任务失败：${errorText(error)}`
  } finally {
    creating.value = false
  }
}

async function loadResults(runId: string) {
  const request = ++resultRequest
  results.value = []
  resultsError.value = ''
  resultsLoading.value = true
  try {
    const rows = await getCollectionResults(runId)
    if (request === resultRequest && session.value?.run_id === runId) results.value = rows
  } catch (error) {
    if (request === resultRequest) resultsError.value = `桥接结果读取失败：${errorText(error)}`
  } finally {
    if (request === resultRequest) resultsLoading.value = false
  }
}

async function refreshSession() {
  if (!session.value?.run_id || refreshing.value) return
  const runId = session.value.run_id
  refreshing.value = true
  try {
    const updated = await getBridgeSession(runId)
    if (session.value?.run_id === runId) session.value = updated
    await loadResults(runId)
    emit('changed')
  } catch (error) {
    actionError.value = `桥接任务刷新失败：${errorText(error)}`
  } finally {
    refreshing.value = false
  }
}

async function finishSession(reason?: string) {
  if (!session.value?.run_id || session.value.finished_at || finishing.value) return
  const runId = session.value.run_id
  finishing.value = true
  actionError.value = ''
  try {
    session.value = reason
      ? await finishBridgeSession(runId, reason)
      : await finishBridgeSession(runId)
    emit('busy', false)
    await loadResults(runId)
    emit('changed')
  } catch (error) {
    actionError.value = `桥接任务结束失败：${errorText(error)}`
  } finally {
    finishing.value = false
  }
}

function stopSession() {
  return finishSession('user_stopped')
}

function inspectSession() {
  if (!session.value) return
  emit('inspect', { run_id: session.value.run_id, platform: 'boss', status: session.value.status })
}

async function copyToken() {
  if (!pairing.value?.token) return
  try {
    await navigator.clipboard.writeText(pairing.value.token)
    ElMessage.success('配对令牌已复制')
  } catch {
    ElMessage.warning('浏览器拒绝自动复制，请手动选择令牌文本。')
  }
}

onMounted(async () => {
  await loadPairing()
  timer = setInterval(() => {
    if (activeSession.value && !refreshing.value) void refreshSession()
  }, 5000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
  resultRequest++
})
</script>

<style scoped>
.bridge-panel { margin-top: 18px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.step { display: inline-grid; place-items: center; min-width: 39px; height: 26px; margin-right: 9px; padding: 0 8px; border: 1px solid rgba(95, 143, 187, .16); border-radius: 8px; background: #edf5fb; color: #5f8fbb; font-size: 12px; }
.bridge-setup { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, .8fr); gap: 24px; align-items: end; margin-top: 18px; }
.bridge-form { display: grid; grid-template-columns: 1fr 1fr; gap: 0 18px; }
.bridge-create { padding: 16px; border: 1px solid #d7e7f2; border-radius: 13px; background: linear-gradient(145deg, #fbfeff, #f4f9fd); }
.bridge-create p { margin: 0 0 12px; color: #69808e; font-size: 12px; line-height: 1.7; }
.bridge-session { margin-top: 20px; padding-top: 20px; border-top: 1px solid #e4edf3; }
.bridge-session-head, .results-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.bridge-session-head label { color: #8296a3; font-size: 11px; }
.bridge-session-head p { margin: 4px 0 0; font-size: 13px; }
.bridge-counts { grid-template-columns: repeat(6, minmax(0, 1fr)); }
.bridge-pairing { margin: 18px 0; padding: 14px 16px; border: 1px solid #dde9f1; border-radius: 12px; background: #f8fbfd; }
.bridge-pairing summary { cursor: pointer; color: #4d6f99; font-weight: 600; }
.bridge-pairing ol { margin: 12px 0; padding-left: 22px; color: #69808e; font-size: 12px; line-height: 1.9; }
.pairing-values { display: grid; gap: 8px; font-size: 12px; color: #69808e; }
.pairing-values span { overflow-wrap: anywhere; }
.bridge-actions { display: flex; flex-wrap: wrap; gap: 9px; margin: 16px 0; }
.results-head { margin-top: 22px; }
.results-head h3 { margin: 0; }
.results-head span { color: #8296a3; font-size: 12px; }
.mono { font-family: ui-monospace, Consolas, monospace; overflow-wrap: anywhere; }
.count-grid { display: grid; gap: 10px; margin: 18px 0; }
.count-grid > div { padding: 14px 8px; border: 1px solid rgba(213, 224, 228, .72); border-radius: 11px; background: linear-gradient(160deg, #f9fcfd, #f3f8fa); text-align: center; }
.count-grid strong { display: block; margin-bottom: 5px; color: var(--text); font-size: 21px; }
.count-grid span { color: #69808e; font-size: 11px; }
@media (max-width: 900px) {
  .bridge-setup, .bridge-form { grid-template-columns: 1fr; }
  .bridge-counts { grid-template-columns: repeat(3, 1fr); }
}
</style>
