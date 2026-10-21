<template>
  <div class="m2-page">
    <header class="m2-heading"><div><span class="eyebrow">M2 · 历史 JD 分析</span><h1>岗位分析工作台</h1><p>冻结输入，逐条分析，保留证据与未决原因。</p></div><el-button @click="refresh" :loading="refreshing">刷新任务</el-button></header>
    <el-alert title="本地受控预览：MySQL 只读，结果保存在独立 SQLite。前端演示登录不构成生产身份授权。" type="info" :closable="false" show-icon />
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="gap" />

    <section class="m2-card gap" aria-label="选择真实 JD">
      <h2>1. 选择并冻结输入 <small>历史库 {{ catalog?.total ?? '—' }} 条 · 本轮不采集招聘网站</small></h2>
      <div class="selection-grid">
        <label>输入范围<el-select v-model="cohort" aria-label="输入范围"><el-option label="历史库自选" value="history" /><el-option v-for="c in catalog?.cohorts || []" :key="c.name" :label="c.name === 'main120' ? '此前主集成员 · 120 条' : '此前留出成员 · 60 条'" :value="c.name" :disabled="!c.available" /></el-select></label>
        <label>来源平台<el-select v-model="sources" multiple clearable placeholder="全部来源（包括异常来源）" :disabled="cohort !== 'history'" aria-label="来源平台"><el-option v-for="s in catalog?.sources.filter(s => s.source) || []" :key="s.source!" :label="`${s.source} · ${s.total}`" :value="s.source!" /></el-select></label>
        <label>起始 JD ID<el-input-number v-model="idMin" :min="1" :controls="false" :disabled="cohort !== 'history'" placeholder="不限" aria-label="起始 JD ID" /></label>
        <label>结束 JD ID<el-input-number v-model="idMax" :min="1" :controls="false" :disabled="cohort !== 'history'" placeholder="不限" aria-label="结束 JD ID" /></label>
        <label>最多读取数量<el-input-number v-model="limit" :min="1" :max="5000" :disabled="cohort !== 'history'" aria-label="最多读取数量" /></label>
        <el-button type="primary" :disabled="mutating || !catalog" @click="createRun">创建冻结任务</el-button>
      </div>
      <p class="muted">按 ID 升序有界读取。主集/留出选项读取此前固定成员的当前 MySQL 内容，记录与旧快照的差异；版本重放使用本任务已冻结的原始字节。</p>
    </section>

    <section class="m2-card gap" aria-label="分析任务">
      <div class="section-heading"><h2>2. 显式启动分析</h2><el-select :model-value="selectedId" @change="selectRun" placeholder="选择历史任务" class="history-select" aria-label="历史任务"><el-option v-for="r in history" :key="r.run_id" :value="r.run_id" :label="`${r.created_at.slice(0,19)} · ${statusText(r.status)} · ${r.run_id.slice(0,8)}`" /></el-select></div>
      <template v-if="selected">
        <div class="run-meta"><code>{{ selected.run_id }}</code><el-tag :type="tagType(selected.status)">{{ statusText(selected.status) }}</el-tag><span v-if="selected.reason">原因：{{ statusText(selected.reason) }}</span></div>
        <el-button :disabled="mutating || !['completed','completed_with_issues'].includes(selected.status)" :loading="graphLoading" @click="openGraph">生成 / 查看本次候选图谱</el-button>
        <div class="actions"><el-button type="primary" :disabled="!canStart" :loading="mutating" @click="startRun">{{ ['stopped','interrupted','publication_failed'].includes(selected.status) ? '恢复分析' : '开始分析' }}</el-button><el-button :disabled="mutating || !['running','stopping','queued'].includes(selected.status)" @click="stopRun">停止分析</el-button><el-input v-model="revision" aria-label="重放版本" placeholder="版本，例如 v2" class="revision" /><el-button :disabled="mutating || active" @click="replayRun">创建版本重放</el-button><el-button :disabled="!selected.finished_at || mutating" @click="downloadReport">下载本地完整报告</el-button></div>
        <p class="muted">停止在阶段边界生效；已提交结果保留。全部输出仍受规则覆盖和人工审核限制。{{ active ? '任务执行中，请勿关闭后端。' : '' }}</p>
        <div class="stat-grid"><div><strong>{{ selected.summary.input_total }}</strong><span>输入 JD 总量</span></div><div><strong>{{ selected.summary.finalized }}</strong><span>已有最终去向</span></div><div><strong>{{ selected.summary.stage_complete }}</strong><span>四阶段已走完</span></div><div><strong>{{ selected.summary.final_counts.needs_review || 0 }}</strong><span>机器待复核</span></div><div><strong>{{ selected.summary.review?.reviewed_items || 0 }}</strong><span>人工已提交</span></div><div><strong>{{ selected.summary.review?.unreviewed_items ?? selected.summary.input_total }}</strong><span>人工未提交</span></div><div><strong>{{ selected.summary.final_counts.failed || 0 }}</strong><span>真正执行失败</span></div><div><strong>{{ selected.summary.final_counts.input_invalid || 0 }}</strong><span>输入不可解析</span></div></div>
        <el-progress :percentage="Math.round(100 * selected.summary.finalized / selected.summary.input_total)" :stroke-width="8" />
        <p class="metric-note">进度仅表示工程处理覆盖，不是语义准确率。B2“完整”也仅限已知别名和受支持句式；不代表开放域识别完整。</p>
        <div class="summary-grid"><article v-for="(metrics, stage) in stageMetrics" :key="stage"><h3>{{ stageLabels[stage] }}</h3><dl><template v-for="(value, key) in metrics" :key="key"><dt>{{ metricText(String(key), String(stage)) }}</dt><dd>{{ typeof value === 'number' ? value : statusText(String(value)) }}</dd></template></dl></article></div>
        <el-collapse><el-collapse-item title="输入、版本与本地产物" name="provenance"><p>输入 SHA-256：<code>{{ selected.input_sha256 }}</code></p><pre>{{ pretty({ versions: selected.versions, provenance: selected.provenance, artifacts: selected.artifacts, parent_run_id: selected.parent_run_id }) }}</pre></el-collapse-item></el-collapse>
        <el-table :data="pageItems" stripe class="gap" aria-label="逐条 JD 结果"><el-table-column prop="jd_id" label="JD ID" width="90" /><el-table-column prop="source" label="来源" width="95" /><el-table-column label="身份" width="110"><template #default="{ row }"><el-tag effect="plain">{{ identityText(row.identity_status) }}</el-tag></template></el-table-column><el-table-column prop="title" label="原始标题" min-width="200" show-overflow-tooltip /><el-table-column label="机器去向" width="130"><template #default="{ row }"><el-tag :type="tagType(row.final_status)">{{ statusText(row.final_status) }}</el-tag></template></el-table-column><el-table-column label="人工审核" width="115"><template #default="{ row }">{{ statusText(row.human_review?.decision || 'unreviewed') }}</template></el-table-column><el-table-column v-for="stage in stages" :key="stage" :label="stageLabels[stage]" width="108"><template #default="{ row }">{{ statusText(row.stages[stage].status) }}</template></el-table-column><el-table-column label="证据" width="65"><template #default="{ row }">{{ row.evidence.matched }}</template></el-table-column><el-table-column label="详情" width="90" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="inspectItem(row.ordinal)">查看</el-button></template></el-table-column></el-table>
        <el-pagination v-model:current-page="page" :page-size="20" :total="selected.items.length" layout="prev, pager, next, total" class="gap" />
      </template><el-empty v-else description="创建冻结任务或选择历史任务，然后显式开始分析。" />
    </section>

    <el-drawer v-model="drawer" title="JD 原文、阶段结果与证据" size="min(100%, 1080px)" destroy-on-close>
      <p v-if="detailLoading">正在读取本地冻结证据…</p>
      <template v-if="detail"><div class="run-meta"><strong>JD {{ detail.jd_id }} · {{ detail.source ?? '来源缺失' }}</strong><el-tag>{{ statusText(detail.final_status) }}</el-tag><el-tag effect="plain">{{ identityText(detail.identity_status) }}</el-tag></div><h2>{{ detail.title ?? '标题缺失' }}</h2><p>处理原因：{{ statusText(detail.reason || 'pending') }}</p><p class="metric-note">正式统计资格：关闭。B1 未同时满足“有效、范围内”的输入，其后续语义仅为候选证据，不确认为独立岗位需求。</p><p class="muted">输入限制：{{ detail.warnings.map(statusText).join('；') }}</p>
        <el-tabs v-model="detailTab">
          <el-tab-pane label="冻结原文" name="source"><h3>来源记录</h3><pre>{{ pretty({ id: detail.jd_id, source: detail.source, source_detail: detail.input?.source_detail, identity_status: detail.identity_status, content_eligible: detail.content_eligible, identity_evidence: detail.identity_evidence, crawled_at: detail.input?.crawled_at, sha256: detail.input_sha256 }) }}</pre><h3>raw_text</h3><pre class="source-text">{{ detail.input?.raw_text ?? '缺失（SQL NULL 或字段不存在）' }}</pre><el-collapse><el-collapse-item title="其他原始字段（保留空值）"><pre>{{ pretty(detail.input) }}</pre></el-collapse-item></el-collapse></el-tab-pane>
          <el-tab-pane v-for="stage in stages" :key="stage" :label="stageLabels[stage]" :name="stage"><p>阶段：{{ statusText(detail.stages[stage].status) }} · {{ statusText(detail.stages[stage].reason || '') }}</p><p>规则版本：<code>{{ detail.stages[stage].version_id ?? '尚未执行' }}</code></p>
            <template v-if="stage === 'b1' && detail.stages.b1.result"><el-descriptions :column="1" border><el-descriptions-item label="有效性">{{ statusText(detail.stages.b1.result.validity) }}</el-descriptions-item><el-descriptions-item label="范围">{{ statusText(detail.stages.b1.result.scope_status || 'not_applicable') }}</el-descriptions-item><el-descriptions-item label="说明">{{ detail.stages.b1.result.explanation }}</el-descriptions-item><el-descriptions-item label="复核原因">{{ detail.stages.b1.result.review_reasons.join('；') || '无额外复核项' }}</el-descriptions-item></el-descriptions></template>
            <template v-if="stage === 'b2' && detail.stages.b2.result?.body"><p>覆盖：{{ statusText(detail.stages.b2.result.status) }}；识别结果：{{ statusText(detail.stages.b2.result.body.outcome) }}</p><el-table :data="detail.stages.b2.result.body.statements" stripe><el-table-column label="技能" width="150"><template #default="{ row }">{{ row.skills.map((s: any) => s.name).join(' / ') }}</template></el-table-column><el-table-column label="五态" width="105"><template #default="{ row }">{{ statusText(row.state) }}</template></el-table-column><el-table-column prop="reason" label="规则原因" min-width="180" /><el-table-column prop="evidence.quote" label="原文引文" min-width="260" /></el-table><p v-if="!detail.stages.b2.result.body.statements.length">本规则未识别到技能，不代表原文没有技能。</p></template>
            <template v-if="stage === 'b22' && detail.stages.b22.result?.body"><p>规范化技能 {{ detail.stages.b22.result.body.skills.length }}；候选 {{ detail.stages.b22.result.body.candidates.length }}；未解决片段 {{ detail.stages.b22.result.body.unresolved_fragments.length }}。候选准入关闭。</p><el-table :data="detail.stages.b22.result.body.candidates"><el-table-column prop="raw_name" label="候选原名" /><el-table-column label="审核原因"><template #default="{ row }">{{ row.review_reasons.join('；') }}</template></el-table-column><el-table-column prop="evidence.quote" label="来源证据" /></el-table></template>
            <template v-if="stage === 'b3' && detail.stages.b3.result?.body"><p>分类状态：{{ statusText(detail.stages.b3.result.body.resolution) }}；全部待审核，标准岗位尚未发布。</p><p>原因：{{ detail.stages.b3.result.body.reasons.join('；') || '有限职责规则建议，等待人工审核' }}</p><el-table :data="detail.stages.b3.result.body.candidates"><el-table-column prop="family_id" label="职业大类候选" /><el-table-column label="职责证据"><template #default="{ row }">{{ row.clues.map((c: any) => c.evidence.quote).join('；') }}</template></el-table-column></el-table></template>
            <h3>原文位置与审核上下文</h3><p class="muted">位置为 Python 字符索引 [start,end)，对应冻结字段；引文匹配只证明可回源，不证明语义正确。</p><div v-for="(ev, index) in evidenceRows(detail.stages[stage].result)" :key="index" class="evidence-row"><code>{{ ev.field }} [{{ ev.start }}, {{ ev.end }})</code><blockquote>{{ ev.quote }}</blockquote></div><el-empty v-if="!evidenceRows(detail.stages[stage].result).length" description="当前阶段没有可展示的原文引文；查看阶段原因。" /><el-collapse><el-collapse-item title="完整阶段 JSON（含组合、上下文、复核原因与原生运行 ID）"><pre>{{ pretty(detail.stages[stage]) }}</pre></el-collapse-item></el-collapse>
          </el-tab-pane>
        </el-tabs>
        <section class="review-panel gap" aria-label="人工复核">
          <div class="section-heading"><div><h2>人工复核</h2><p class="muted">人工结论单独追加保存，不覆盖机器预测、原文或历史报告。</p></div><el-button :disabled="!selected || !detail || reviewExporting" :loading="reviewExporting" @click="downloadReviews">导出人工审核 JSON</el-button></div>
          <p>自动状态：<el-tag :type="tagType(detail.final_status)">{{ statusText(detail.final_status) }}</el-tag> · 当前人工状态：<el-tag effect="plain">{{ statusText(detail.human_review?.decision || 'unreviewed') }}</el-tag></p>
          <p>机器结果摘要：<code>{{ detail.machine_sha256 || '尚未生成' }}</code></p>
          <div class="review-form">
            <label>审核决定<el-select v-model="reviewDecision" placeholder="选择人工决定"><el-option label="接受机器结果" value="accepted" /><el-option label="拒绝机器结果" value="rejected" /><el-option label="需要继续核对" value="needs_followup" /></el-select></label>
            <label>审核人<el-input v-model="reviewReviewer" maxlength="80" placeholder="必须由实际审核人填写" /></label>
            <label class="review-note">备注<el-input v-model="reviewNote" type="textarea" :rows="3" maxlength="4000" show-word-limit placeholder="记录判断依据、需要修正的内容或待补证据" /></label>
            <el-button type="primary" :disabled="!canSubmitReview" :loading="reviewSaving" @click="submitReview">记录人工判断</el-button>
          </div>
          <el-alert title="审核提交只代表本机录入的自述判断，不验证人员身份，也不会把机器预测升级为已确认需求或正式岗位。" type="info" :closable="false" />
          <el-table v-if="detail.reviews?.length" :data="detail.reviews" stripe class="gap" aria-label="人工审核历史"><el-table-column prop="reviewed_at" label="时间" min-width="180" /><el-table-column prop="reviewer" label="审核人" width="140" /><el-table-column label="决定" width="130"><template #default="{ row }">{{ statusText(row.decision) }}</template></el-table-column><el-table-column prop="note" label="备注" min-width="260" /><el-table-column label="机器摘要" width="140"><template #default="{ row }"><code>{{ row.machine_sha256.slice(0, 12) }}…</code></template></el-table-column></el-table>
          <el-empty v-else description="尚无人工审核事件；系统不会自动填写真值。" />
        </section>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { createM2Run, exportM2Reviews, generateM2Graph, getM2Item, getM2Report, getM2Run, getM2Runs, getM2Sources, replayM2Run, reviewM2Item, startM2Run, stopM2Run, type M2History, type M2Item, type M2ReviewDecision, type M2Run, type M2Sources } from '../api/m2'

const catalog = ref<M2Sources | null>(null), history = ref<M2History[]>([]), selected = ref<M2Run | null>(null)
const selectedId = ref(''), detail = ref<M2Item | null>(null), drawer = ref(false), detailLoading = ref(false), detailTab = ref('source')
const sources = ref<string[]>([]), cohort = ref('history'), idMin = ref<number>(), idMax = ref<number>(), limit = ref(5), revision = ref('v1'), page = ref(1)
const error = ref(''), refreshing = ref(false), mutating = ref(false)
const graphLoading = ref(false)
const reviewDecision = ref<M2ReviewDecision | ''>(''), reviewReviewer = ref(''), reviewNote = ref('')
const reviewSaving = ref(false), reviewExporting = ref(false)
const stages = ['b1','b2','b22','b3']
const stageLabels: Record<string, string> = { b1:'B1 筛选', b2:'B2 语义', b22:'B2.2 治理', b3:'B3 候选', evidence:'证据审计', identity:'身份可信度', content:'内容资格', review:'人工复核' }
let disposed = false, runRequest = 0, itemRequest = 0, timer: ReturnType<typeof setInterval> | undefined
const active = computed(() => selected.value && ['running','stopping'].includes(selected.value.status))
const canStart = computed(() => !mutating.value && selected.value && ['queued','stopped','interrupted','publication_failed'].includes(selected.value.status) && !history.value.some(r => ['running','stopping'].includes(r.status)))
const pageItems = computed(() => selected.value?.items.slice((page.value - 1) * 20, page.value * 20) || [])
const stageMetrics = computed(() => Object.fromEntries(['b1','b2','b22','b3','evidence','identity','content','review'].map(s => [s, (selected.value?.summary as any)?.[s] || {}])))
const canSubmitReview = computed(() => !!detail.value?.machine_sha256 && ['completed','completed_with_issues'].includes(selected.value?.status || '') && !!reviewDecision.value && !!reviewReviewer.value.trim() && !reviewSaving.value)
const text: Record<string, string> = {
  queued:'待开始', running:'执行中', stopping:'正在停止', stopped:'已停止', interrupted:'已中断，可恢复', publication_failed:'报告保存失败，可恢复', completed:'已完成', completed_with_issues:'处理结束，存在限制', pending:'待处理', saved:'已保存', blocked:'未执行', failed:'执行失败', processed:'完整处理', partial:'部分处理', needs_review:'机器待复核', input_invalid:'输入异常', required:'明确要求', preferred:'加分优先', mentioned:'仅提及', not_required:'明确不要求', uncertain:'待判断', valid:'有效', invalid:'无效', undetermined:'待复核', not_evaluated:'未评估', not_applicable:'不适用', in_scope:'范围内', out_of_scope:'范围外', input_record_invalid:'原始字段不满足解析契约', historical_member_missing:'历史成员已不在当前库', user_requested_stop:'用户请求停止', process_interrupted:'后端进程中断', workflow_execution_failed:'编排执行失败，请检查本地服务', bounded_rules_and_pending_classification:'有限规则分析，分类/语义待人工复核', bounded_semantic_scope:'规则覆盖有限', skills_identified:'识别到技能陈述', no_recognized_skills:'本规则未识别技能', proposed:'已生成候选', unresolved:'未决', unknown:'无法分类', pending_review:'待审核', unreviewed:'人工未审核', accepted:'人工接受', rejected:'人工拒绝', needs_followup:'人工需跟进', missing_source:'来源缺失', missing_job_title:'标题缺失', missing_raw_text:'正文缺失', missing_duties:'无独立职责字段', missing_experience:'无独立经验字段', source_unrecognized:'来源未识别', historical_detail_completeness_not_verified:'历史记录的网页详情完整性未核验',
}
const metrics: Record<string,string> = {valid:'有效 JD',invalid:'无效 JD',undetermined:'有效性待复核',in_scope:'范围内 JD',out_of_scope:'范围外 JD',needs_review:'范围待复核 JD',not_applicable:'范围不适用 JD',not_evaluated:'未评估 JD',failed:'失败 JD',blocked:'未执行 JD',pending:'待处理 JD',running:'执行中 JD',completed:'受支持语法完整 JD',partial:'部分处理 JD',no_recognized_skills:'无已识别技能 JD',unresolved_jds:'有未决内容 JD',processed:'治理已处理 JD',candidate_jds:'有候选 JD',candidates:'候选项数',semantic_conflict_jds:'已检查的语义冲突 JD',catalog_conflict_assessment:'目录治理冲突评估',unresolved_fragments:'未解决片段数',pending_review:'待审核 JD',unable_to_classify:'无法分类 JD',outputs_with_evidence:'有原文引文的阶段输出',outputs_without_evidence:'无引文的阶段输出',matched_spans:'已匹配原文位置',invalid_spans:'位置校验异常',unparseable_jds:'不可解析 JD',statements_required:'明确要求陈述',statements_preferred:'加分优先陈述',statements_mentioned:'仅提及陈述',statements_not_required:'明确不要求陈述',statements_uncertain:'待判断陈述'}
function statusText(value: string) { return text[value] || value }
function metricText(value: string, stage?: string) {
  if (stage === 'identity') return identityText(value)
  if (stage === 'content') return ({ eligible: '内容合格', ineligible: '内容不合格', unknown: '内容未知' } as Record<string, string>)[value] || value
  return metrics[value] || statusText(value)
}
function identityText(value?: string | null) { return ({ verified: '身份已验证', pending: '身份待审', unknown: '身份未知' } as Record<string, string>)[value || ''] || '身份未知' }
function tagType(value: string): 'danger' | 'warning' | 'success' | 'info' { return value === 'failed' ? 'danger' : ['needs_review','partial','input_invalid','completed_with_issues'].includes(value) ? 'warning' : ['processed','completed'].includes(value) ? 'success' : 'info' }
function pretty(value: unknown) { return JSON.stringify(value, null, 2) }
function message(e: any) { const detail = e?.response?.data?.detail; return typeof detail === 'string' ? detail : e instanceof Error ? e.message : '请求失败' }
function evidenceRows(value: any) {
  const found = new Map<string, any>()
  function walk(node: any) {
    if (!node || typeof node !== 'object') return
    if (typeof node.quote === 'string' && typeof node.start === 'number' && typeof node.end === 'number' && node.field) found.set(JSON.stringify([node.field,node.start,node.end,node.quote]), node)
    Object.values(node).forEach(walk)
  }
  walk(value); return [...found.values()]
}
function saveRun(value: M2Run) {
  selected.value = value; selectedId.value = value.run_id
  history.value = [value, ...history.value.filter(r => r.run_id !== value.run_id)]
}
async function selectRun(id: string) {
  const request = ++runRequest; ++itemRequest; selectedId.value = id; selected.value = null; detail.value = null; drawer.value = false; page.value = 1; error.value = ''
  try { const value = await getM2Run(id); if (!disposed && request === runRequest) { selected.value = value; revision.value = value.versions.revision } }
  catch (e) { if (!disposed && request === runRequest) error.value = message(e) }
}
async function refresh() {
  if (refreshing.value || disposed) return
  refreshing.value = true
  const request = runRequest, id = selectedId.value
  try {
    const [sourceData, runs] = await Promise.all([getM2Sources(), getM2Runs()])
    if (disposed) return
    catalog.value = sourceData; history.value = runs
    if (id && request === runRequest) { const value = await getM2Run(id); if (!disposed && request === runRequest && selectedId.value === id) selected.value = value }
  } catch (e) { if (!disposed) error.value = message(e) }
  finally { refreshing.value = false }
}
async function createRun() {
  if (mutating.value) return
  const preset = cohort.value !== 'history'
  if (!preset && (!Number.isInteger(limit.value) || limit.value < 1 || limit.value > 5000 || (idMin.value != null && idMax.value != null && idMin.value > idMax.value))) { error.value = '请检查数量上限和 ID 范围'; return }
  const request = ++runRequest
  mutating.value = true; error.value = ''; ++itemRequest; detail.value = null; drawer.value = false
  try { const value = await createM2Run({ sources: preset ? [] : sources.value, id_min: preset ? null : idMin.value ?? null, id_max: preset ? null : idMax.value ?? null, limit: preset ? cohort.value === 'main120' ? 120 : 60 : limit.value, cohort: cohort.value }); if (!disposed && request === runRequest) { saveRun(value); page.value = 1 } }
  catch (e) { if (!disposed && request === runRequest) error.value = message(e) }
  finally { mutating.value = false }
}
async function action(fn: (id: string) => Promise<M2Run>) {
  if (!selected.value || mutating.value) return
  const id = selected.value.run_id, request = ++runRequest
  mutating.value = true; error.value = ''
  try { const value = await fn(id); if (!disposed && request === runRequest && selectedId.value === id) saveRun(value) }
  catch (e) { if (!disposed && request === runRequest) error.value = message(e) }
  finally { mutating.value = false }
}
async function startRun() { if (canStart.value) await action(startM2Run) }
async function openGraph() {
  if (!selected.value || graphLoading.value || mutating.value || !['completed','completed_with_issues'].includes(selected.value.status)) return
  const id = selected.value.run_id, request = runRequest
  graphLoading.value = true; error.value = ''
  try {
    const graph = await generateM2Graph(id)
    if (!disposed && request === runRequest && selectedId.value === id && graph.run_id === id) window.location.assign(graph.url)
  } catch (e) { if (!disposed && selected.value?.run_id === id) error.value = message(e) }
  finally { graphLoading.value = false }
}
async function stopRun() { await action(stopM2Run) }
async function replayRun() { if (!active.value) await action(id => replayM2Run(id, revision.value)) }
async function inspectItem(ordinal: number) {
  if (!selected.value) return
  const id = selected.value.run_id, request = ++itemRequest
  detail.value = null; detailLoading.value = true; drawer.value = true; detailTab.value = 'source'; error.value = ''
  reviewDecision.value = ''; reviewReviewer.value = ''; reviewNote.value = ''
  try { const value = await getM2Item(id, ordinal); if (!disposed && request === itemRequest && selectedId.value === id) detail.value = value }
  catch (e) { if (!disposed && request === itemRequest) error.value = message(e) }
  finally { if (request === itemRequest) detailLoading.value = false }
}
async function submitReview() {
  if (!selected.value || !detail.value || !canSubmitReview.value || !reviewDecision.value) return
  const id = selected.value.run_id, ordinal = detail.value.ordinal, machine = detail.value.machine_sha256
  const request = itemRequest
  reviewSaving.value = true; error.value = ''
  try {
    const value = await reviewM2Item(id, ordinal, {
      decision: reviewDecision.value,
      reviewer: reviewReviewer.value.trim(),
      note: reviewNote.value,
      machine_sha256: machine || '',
    })
    if (!disposed && request === itemRequest && selectedId.value === id && detail.value?.ordinal === ordinal) {
      detail.value = value
      reviewDecision.value = ''; reviewNote.value = ''
      const refreshed = await getM2Run(id)
      if (!disposed && request === itemRequest && selectedId.value === id) selected.value = refreshed
    }
  } catch (e) { if (!disposed && request === itemRequest) error.value = message(e) }
  finally { reviewSaving.value = false }
}
async function downloadReviews() {
  if (!selected.value || reviewExporting.value) return
  reviewExporting.value = true; error.value = ''
  try {
    const value = await exportM2Reviews(selected.value.run_id)
    if (disposed) return
    const url = URL.createObjectURL(new Blob([pretty(value)], { type: 'application/json;charset=utf-8' }))
    const link = document.createElement('a'); link.href = url; link.download = `m2-reviews-${selected.value.run_id}.json`; link.click(); URL.revokeObjectURL(url)
  } catch (e) { if (!disposed) error.value = message(e) }
  finally { reviewExporting.value = false }
}
async function downloadReport() {
  if (!selected.value) return
  try {
    const report = await getM2Report(selected.value.run_id)
    if (disposed) return
    const url = URL.createObjectURL(new Blob([pretty(report)], { type: 'application/json;charset=utf-8' }))
    const link = document.createElement('a'); link.href = url; link.download = `m2-${report.run_id}.json`; link.click(); URL.revokeObjectURL(url)
  } catch (e) { if (!disposed) error.value = message(e) }
}
onMounted(async () => { await refresh(); if (!disposed) timer = setInterval(refresh, 2500) })
onUnmounted(() => { disposed = true; ++runRequest; ++itemRequest; if (timer !== undefined) clearInterval(timer) })
</script>

<style scoped>
.m2-page{max-width:1600px;margin:auto;color:#18344b}.m2-heading,.section-heading,.run-meta,.actions{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}.m2-heading{margin-bottom:22px}.eyebrow{font-size:12px;letter-spacing:1.3px;color:#397a94}h1{font-size:28px;margin:8px 0}h2{font-size:18px;margin:0 0 18px}h3{font-size:15px}p{line-height:1.7}small,.muted{font-size:12px;color:#62778a;font-weight:400}.gap{margin-top:20px}.m2-card{background:#fff;border:1px solid #dde8ee;border-radius:16px;padding:24px;box-shadow:0 4px 20px #18344b05}.selection-grid{display:grid;grid-template-columns:1.35fr 1.7fr 1fr 1fr 1fr auto;align-items:end;gap:12px}label{font-size:12px;color:#516d80;display:flex;flex-direction:column;gap:8px}label .el-select,label .el-input-number{width:100%}.history-select{width:440px;max-width:100%}.run-meta{justify-content:flex-start;margin:14px 0}.actions{justify-content:flex-start}.revision{width:135px}.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}.stat-grid>div{background:#f1f7fa;border-radius:10px;padding:16px}.stat-grid strong{display:block;font-size:26px;color:#25667c}.stat-grid span{font-size:12px;color:#526e80}.metric-note{background:#fff8e8;border-left:3px solid #d3a044;padding:10px 14px;font-size:12px}.summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:20px 0}.summary-grid article{border:1px solid #e1eaf0;padding:14px;border-radius:10px}dl{display:grid;grid-template-columns:1fr auto;gap:8px;font-size:12px}dd{margin:0;font-weight:600}.review-panel{border-top:1px solid #dde8ee;padding-top:22px}.review-form{display:grid;grid-template-columns:.8fr 1fr 2fr auto;align-items:end;gap:12px;margin:16px 0}.review-form .el-select,.review-form .el-input{width:100%}.review-note{grid-column:span 1}code{font-size:12px;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.7 Consolas,monospace;background:#f4f7fa;padding:16px;border-radius:8px;max-height:600px;overflow:auto}.source-text{font-family:inherit;font-size:14px}.evidence-row{border-bottom:1px solid #e5edf2;padding:12px 0}.evidence-row blockquote{white-space:pre-wrap;margin:8px 0;font-size:13px;line-height:1.7;overflow-wrap:anywhere}@media(max-width:1100px){.selection-grid,.review-form{grid-template-columns:repeat(3,1fr)}.stat-grid,.summary-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:700px){.selection-grid,.stat-grid,.summary-grid,.review-form{grid-template-columns:repeat(2,minmax(0,1fr))}.review-note{grid-column:span 2}.m2-card{padding:16px}.summary-grid article{grid-column:span 2}}
</style>
