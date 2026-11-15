<template>
  <section class="panel runtime-panel" aria-label="三平台隔离持续采集">
    <div class="runtime-head">
      <div>
        <h2><span class="step">持续</span>三平台隔离采集</h2>
        <p>一个调度器管理 BOSS、智联、猎聘三个独立 Edge 进程与 Profile；某站受限只暂停该站。</p>
      </div>
      <div class="runtime-actions">
        <el-button data-testid="runtime-refresh" :loading="loading" @click="refresh">刷新</el-button>
        <el-button v-if="allRestricted" data-testid="runtime-reset-checkpoint" type="warning" plain :disabled="!canResetCheckpoint" :loading="acting === 'reset'" @click="resetPlanAndCursor">复位计划与游标</el-button>
        <el-button data-testid="runtime-start" type="primary" :loading="acting === 'start'" :disabled="!canStart" @click="startRuntime">启动持续采集</el-button>
        <el-button data-testid="runtime-stop" type="danger" plain :loading="acting === 'stop'" :disabled="!canStop" @click="stopRuntime">停止全部</el-button>
      </div>
    </div>

    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <el-alert v-if="notice" :title="notice" type="success" :closable="false" show-icon />

    <div class="runtime-grid">
      <article v-for="platform in platformOrder" :key="platform" class="runtime-card" :data-platform="platform">
        <header>
          <div>
            <h3>{{ platformLabels[platform] }}</h3>
            <p class="runtime-platform-state">{{ platformState(platform)?.status || 'idle' }}</p>
          </div>
          <el-tag :type="statusType(platformState(platform)?.status)" effect="plain">{{ statusText(platformState(platform)?.status) }}</el-tag>
        </header>
        <p class="runtime-cursor">
          关键词 #{{ (platformState(platform)?.keyword_index ?? 0) + 1 }} ·
          城市 #{{ (platformState(platform)?.city_index ?? 0) + 1 }} ·
          第 {{ platformState(platform)?.page ?? 1 }} 页
        </p>
        <div class="runtime-counts">
          <span v-for="item in counterItems(platformState(platform))" :key="item.key">
            <strong>{{ item.value }}</strong><small>{{ item.label }}</small>
          </span>
        </div>
        <p v-if="platformState(platform)?.stop_reason" class="runtime-reason">{{ platformState(platform)?.stop_reason }}</p>
        <p v-if="platformState(platform)?.next_run_at" class="hint">下一次页面动作：{{ formatTimestamp(platformState(platform)?.next_run_at) }}</p>
        <el-button
          v-if="['blocked', 'needs_login', 'failed'].includes(platformState(platform)?.status || '')"
          :data-testid="`runtime-resume-${platform}`"
          :loading="acting === platform"
          type="warning"
          plain
          @click="resumeRuntime(platform)"
        >
          {{ platformState(platform)?.status === 'needs_login' ? '完成登录后恢复该站' : '确认排查后恢复该站' }}
        </el-button>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getCollectionRuntimeStatus,
  resumeCollectionRuntime,
  startCollectionRuntime,
  stopCollectionRuntime,
  type CollectionRuntimePlatformState,
  type CollectionRuntimeStatus,
} from '../api/collection'

const platformOrder = ['boss', 'zhaopin', 'liepin'] as const
const platformLabels: Record<string, string> = { boss: 'BOSS直聘', zhaopin: '智联招聘', liepin: '猎聘' }
const runtime = ref<CollectionRuntimeStatus | null>(null)
const loading = ref(false)
const acting = ref('')
const error = ref('')
const notice = ref('')
let request = 0
let timer: ReturnType<typeof setInterval> | null = null
let disposed = false

const canStart = computed(() => !isRunning.value && !allRestricted.value && !acting.value)
const canStop = computed(() => isRunning.value && !acting.value)
const isRunning = computed(() => platformOrder.some(platform => ['running', 'waiting'].includes(platformState(platform)?.status || '')))
const allRestricted = computed(() => Boolean(runtime.value) && platformOrder.every(platform => {
  const status = platformState(platform)?.status
  return status === 'blocked' || status === 'needs_login' || status === 'failed'
}))
const canResetCheckpoint = computed(() => allRestricted.value && !acting.value)

function platformState(platform: string): CollectionRuntimePlatformState | undefined {
  return runtime.value?.platforms?.[platform]
}
function statusText(value?: string) {
  return ({ idle: '未启动', running: '运行中', waiting: '等待中', needs_login: '需登录', blocked: '已阻断', failed: '失败', stopped: '已停止' } as Record<string, string>)[value || 'idle'] || value || '未知'
}
function statusType(value?: string) {
  return value === 'running' ? 'success' : value === 'waiting' ? 'info' : value === 'needs_login' || value === 'blocked' ? 'warning' : value === 'failed' ? 'danger' : 'info'
}
function formatTimestamp(value?: number | null) {
  if (!value) return '—'
  return new Date(value * 1000).toLocaleString()
}
function counterItems(value?: CollectionRuntimePlatformState) {
  const stats = value?.stats || {}
  return [
    ['listed', '列表'], ['detail_attempted', '详情'], ['content_eligible', '内容有效'],
    ['identity_pending', '身份待审'], ['identity_verified', '身份通过'],
    ['inserted', '新增'], ['updated', '更新'], ['skipped', '跳过'], ['rejected', '拒绝'], ['failed', '失败'],
  ].map(([key, label]) => ({ key, label, value: stats[key] ?? 0 }))
}
function apply(value: CollectionRuntimeStatus) {
  runtime.value = value
}
async function refresh() {
  if (loading.value || disposed) return
  const current = ++request
  loading.value = true
  error.value = ''
  try {
    const value = await getCollectionRuntimeStatus()
    if (!disposed && current === request) apply(value)
  } catch (reason) {
    if (!disposed && current === request) error.value = `持续采集状态读取失败：${reason instanceof Error ? reason.message : String(reason)}`
  } finally {
    if (!disposed && current === request) loading.value = false
  }
}
async function startRuntime() {
  if (!canStart.value || disposed) return
  acting.value = 'start'; error.value = ''; notice.value = ''
  try {
    const result = await startCollectionRuntime({})
    apply(result)
    const activeCount = platformOrder.filter(platform => ['running', 'waiting'].includes(result.platforms[platform]?.status || '')).length
    const restricted = platformOrder
      .filter(platform => ['blocked', 'needs_login', 'failed'].includes(result.platforms[platform]?.status || ''))
      .map(platform => platformLabels[platform])
    notice.value = restricted.length
      ? `已为 ${activeCount} 个可运行平台启动 worker；${restricted.join('、')}仍需人工处理。`
      : '三个平台 worker 已启动；需要登录或验证时只暂停对应站点。'
  } catch (reason) {
    error.value = `启动失败：${reason instanceof Error ? reason.message : String(reason)}`
  } finally {
    if (!disposed) acting.value = ''
  }
}
async function resetPlanAndCursor() {
  if (!canResetCheckpoint.value || disposed) return
  try {
    await ElMessageBox.confirm(
      '此操作只复位本地计划与采集游标，并清除运行计数、最近保存身份和运行时间记录；不启动 worker、不访问招聘站，也不会清除受限状态或 STOP 标志。可读取时沿用已保存计划；计划缺失或损坏时使用默认计划。复位后仍需逐站完成人工处理并显式恢复。',
      '复位计划与游标',
      { type: 'warning', confirmButtonText: '复位本地状态', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  acting.value = 'reset'; error.value = ''; notice.value = ''
  try {
    apply(await startCollectionRuntime({ reset_checkpoint: true }))
    notice.value = '本地计划与游标已复位；各站受限状态和 STOP 标志已保留，请逐站处理后再恢复。'
    ElMessage.success('本地计划与游标已复位')
  } catch (reason) {
    error.value = `本地复位失败：${reason instanceof Error ? reason.message : String(reason)}`
  } finally {
    if (!disposed) acting.value = ''
  }
}
async function stopRuntime() {
  if (!canStop.value || disposed) return
  acting.value = 'stop'; error.value = ''; notice.value = ''
  try {
    apply(await stopCollectionRuntime())
    notice.value = '已向三个平台发送停止标记。'
  } catch (reason) {
    error.value = `停止失败：${reason instanceof Error ? reason.message : String(reason)}`
  } finally {
    if (!disposed) acting.value = ''
  }
}
async function resumeRuntime(platform: string) {
  const current = platformState(platform)
  if (!current || !['blocked', 'needs_login', 'failed'].includes(current.status) || acting.value || disposed) return
  acting.value = platform; error.value = ''; notice.value = ''
  try {
    const confirmed = current.status !== 'needs_login'
    apply(await resumeCollectionRuntime(platform, confirmed))
    notice.value = current.status === 'needs_login' ? '已登记登录完成，按安全间隔恢复该站。' : '已登记人工确认，按安全间隔恢复该站。'
    ElMessage.success('恢复请求已登记')
  } catch (reason) {
    error.value = `恢复失败：${reason instanceof Error ? reason.message : String(reason)}`
  } finally {
    if (!disposed) acting.value = ''
  }
}
onMounted(async () => {
  await refresh()
  if (!disposed) timer = setInterval(refresh, 5000)
})
onUnmounted(() => {
  disposed = true
  request++
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.runtime-panel { margin: 18px 0; padding: 22px; border-radius: 16px; }
.runtime-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; flex-wrap: wrap; }
.runtime-head h2 { margin: 0 0 6px; font-size: 18px; }
.runtime-head p { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.7; }
.runtime-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.runtime-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
.runtime-card { padding: 15px; border: 1px solid rgba(100, 112, 150, .16); border-radius: 13px; background: rgba(255,255,255,.62); }
.runtime-card header { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
.runtime-card h3 { margin: 0; font-size: 15px; }
.runtime-platform-state { margin: 4px 0 0; color: var(--muted); font-size: 11px; }
.runtime-cursor { margin: 12px 0; color: #65718c; font-size: 12px; }
.runtime-counts { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; }
.runtime-counts span { display: flex; flex-direction: column; gap: 2px; }
.runtime-counts strong { font-size: 15px; color: #35445f; }
.runtime-counts small { color: var(--muted); font-size: 10px; }
.runtime-reason { color: #a35d3e; font-size: 11px; overflow-wrap: anywhere; }
.el-alert { margin-top: 12px; }
@media (max-width: 1000px) { .runtime-grid { grid-template-columns: 1fr; } }
</style>
