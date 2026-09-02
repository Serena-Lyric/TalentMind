<template>
  <section ref="rootRef" class="nebula-page">
    <div class="nebula-stars"></div>
    <header class="nebula-header">
      <div class="nebula-title"><span>岗位星云图谱</span><b>· Career Nebula</b></div>
      <div class="nebula-meta"><span>{{ graphData.nodes.length }} 个节点</span><i></i><span>{{ graphData.edges.length }} 条关联</span></div>
    </header>

    <aside class="nebula-control panel-glass">
      <label class="nebula-label">搜索</label>
      <div class="nebula-search">
        <el-icon><Search /></el-icon>
        <input v-model="searchKeyword" placeholder="输入岗位或技能..." @keydown.enter="focusFirstMatch" />
        <button v-if="searchKeyword" type="button" @click="searchKeyword = ''">×</button>
      </div>
      <p v-if="searchKeyword" class="search-hint">{{ searchMatches.length ? `找到 ${searchMatches.length} 个节点` : '没有匹配节点' }}</p>

      <label class="nebula-label">节点类型</label>
      <div class="nebula-filters">
        <button v-for="filter in filters" :key="filter.kind" type="button" :class="{ off: !filter.active }" @click="filter.active = !filter.active">
          <i :style="{ background: filter.color }"></i>{{ filter.label }}
        </button>
      </div>

      <label class="nebula-label">图例</label>
      <div class="nebula-legend">
        <span><i class="legend-job"></i>岗位节点</span>
        <span><i class="legend-skill"></i>技能节点</span>
        <span><i class="legend-industry"></i>行业节点</span>
        <span><i class="legend-edge"></i>岗位-技能关联</span>
        <span><i class="legend-edge dashed"></i>岗位间关联</span>
      </div>

      <div class="nebula-tools">
        <button type="button" @click="resetView"><el-icon><Refresh /></el-icon>重置视图</button>
        <button type="button" @click="loadGraph"><el-icon><RefreshRight /></el-icon>刷新数据</button>
      </div>
    </aside>

    <div ref="canvasWrapRef" class="nebula-canvas-wrap">
      <canvas ref="canvasRef" @click="onCanvasClick" @pointerdown="onPointerDown" @pointermove="onPointerMove" @pointerup="onPointerUp" @pointerleave="onPointerUp" @wheel.prevent="onWheel"></canvas>
      <div v-if="loading" class="nebula-state"><el-icon class="is-loading"><Loading /></el-icon><span>正在加载图谱数据...</span></div>
      <div v-else-if="!graphData.nodes.length" class="nebula-state"><el-icon><DataAnalysis /></el-icon><span>暂无图谱数据</span></div>
    </div>

    <aside v-if="selectedNode" class="nebula-detail panel-glass">
      <div class="detail-head">
        <div><small>{{ nodeKindLabel(selectedNode.kind) }}</small><h3>{{ selectedNode.label }}</h3><p v-if="selectedNode.name_en && selectedNode.name_en !== selectedNode.label" class="detail-en">{{ selectedNode.name_en }}</p></div>
        <button type="button" aria-label="关闭详情" @click="selectedNode = null; highlightIds.clear(); draw()">×</button>
      </div>
      <div class="detail-kpis"><span><b>{{ connectedCount }}</b><small>关联节点</small></span><span><b>{{ selectedNode.jobs || selectedNode.size || 0 }}</b><small>{{ selectedNode.kind === 'job' ? '来源 JD' : '关联岗位' }}</small></span></div>
      <div v-if="selectedNode.kind === 'job'" class="detail-section"><label>分类 / 演化</label><p>{{ selectedNode.category || '—' }} · {{ selectedNode.is_emerging ? '新一代岗位' : '现有岗位' }}<span v-if="selectedNode.evolution?.stage"> · {{ selectedNode.evolution.stage }}</span></p></div>
      <div v-if="selectedNode.kind === 'job'" class="detail-section"><label>来源平台</label><p>{{ selectedNode.platform_label || '—' }}</p></div>
      <div v-if="selectedNode.kind === 'job' && selectedNode.core_duties" class="detail-section"><label>核心职责</label><p>{{ selectedNode.core_duties }}</p></div>
      <div v-if="selectedNode.kind === 'job' && selectedNode.required_skills?.length" class="detail-section"><label>必备技能</label><p>{{ selectedNode.required_skills.join('、') }}</p></div>
      <div v-if="selectedNode.kind === 'job' && selectedNode.bonus_skills?.length" class="detail-section"><label>加分技能</label><p>{{ selectedNode.bonus_skills.join('、') }}</p></div>
      <div v-if="selectedNode.kind === 'job' && selectedNode.scenarios?.length" class="detail-section"><label>应用场景</label><p>{{ selectedNode.scenarios.join('、') }}</p></div>
      <div v-if="selectedNode.status" class="detail-section"><label>状态</label><p>{{ selectedNode.status === 'stable' ? '稳定' : selectedNode.status === 'emerging' ? '新一代' : selectedNode.status }}</p></div>
      <div v-if="selectedNode.kind !== 'job'" class="detail-section"><label>节点名称</label><p>{{ selectedNode.label }}</p></div>
      <div class="detail-section"><label>使用提示</label><p>已高亮该节点的直接关联，点击空白区域可清除高亮。</p></div>
    </aside>

    <div class="nebula-hint">点击节点查看详情&nbsp;&nbsp;·&nbsp;&nbsp;滚轮缩放&nbsp;&nbsp;·&nbsp;&nbsp;拖拽平移</div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { DataAnalysis, Loading, Refresh, RefreshRight, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getGraphData, type GraphData, type GraphNode } from '../api/graph'

interface Point { x: number; y: number }
interface DrawNode extends GraphNode { point: Point }

const rootRef = ref<HTMLElement | null>(null)
const canvasWrapRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const loading = ref(false)
const graphData = ref<GraphData>({ nodes: [], edges: [], stats: { totalNodes: 0, totalEdges: 0, added: 0, removed: 0, changed: 0 } })
const searchKeyword = ref('')
const selectedNode = ref<GraphNode | null>(null)
const filters = reactive([
  { kind: 'job' as const, label: '岗位', color: '#4da6ff', active: true },
  { kind: 'skill' as const, label: '技能', color: '#2ee66b', active: true },
  { kind: 'industry' as const, label: '行业', color: '#c77dff', active: true },
])

const layout = new Map<string, Point>()
const nodeById = new Map<string, DrawNode>()
const drawNodes = ref<DrawNode[]>([])
const DEFAULT_EDGE_LIMIT = 900
const highlightIds = ref<Set<string>>(new Set())
const transform = reactive({ scale: 1, x: 0, y: 0 })
const drag = reactive({ active: false, moved: false, startX: 0, startY: 0, originX: 0, originY: 0 })
let resizeObserver: ResizeObserver | null = null

const activeKinds = computed(() => new Set(filters.filter(item => item.active).map(item => item.kind)))
const searchMatches = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return []
  return drawNodes.value.filter(node => node.label.toLowerCase().includes(keyword) || node.id.toLowerCase().includes(keyword))
})
const connectedCount = computed(() => {
  if (!selectedNode.value) return 0
  return graphData.value.edges.filter(edge => edge.source === selectedNode.value?.id || edge.target === selectedNode.value?.id).length
})

const colors: Record<string, string> = { job: '#4da6ff', skill: '#2ee66b', industry: '#c77dff' }

function nodeKindLabel(kind: GraphNode['kind']) { return kind === 'job' ? '岗位节点' : kind === 'skill' ? '技能节点' : '行业节点' }
function nodeSize(node: GraphNode) { return node.kind === 'job' ? Math.max(7, Math.min(18, (node.size || 14) * .42)) : node.kind === 'industry' ? 13 : Math.max(3.5, Math.min(8, (node.size || 8) * .32)) }
function nodeLabel(node: GraphNode) {
  const maxChars = node.kind === 'job' ? Math.max(5, Math.min(12, Math.floor(nodeSize(node) * .8))) : 9
  return node.label.length > maxChars ? `${node.label.slice(0, maxChars - 1)}…` : node.label
}

function buildLayout() {
  layout.clear()
  const nodes = graphData.value.nodes
  const jobs = nodes.filter(node => node.kind === 'job').sort((a, b) => a.id.localeCompare(b.id))
  const industries = nodes.filter(node => node.kind === 'industry').sort((a, b) => a.id.localeCompare(b.id))
  const skills = nodes.filter(node => node.kind === 'skill').sort((a, b) => a.id.localeCompare(b.id))
  const jobIds = new Set(jobs.map(node => node.id))
  const skillIds = new Set(skills.map(node => node.id))
  jobs.forEach((job, index) => {
    const radius = 150 * Math.sqrt(index + .6)
    const angle = index * 2.39996323
    layout.set(job.id, { x: radius * Math.cos(angle), y: radius * Math.sin(angle) })
  })
  industries.forEach((node, index) => layout.set(node.id, { x: -420 + index * 110, y: -280 + (index % 2) * 70 }))

  const skillLinks = new Map<string, string[]>()
  graphData.value.edges.forEach((edge) => {
    const jobId = jobIds.has(edge.source) ? edge.source : jobIds.has(edge.target) ? edge.target : ''
    const skillId = skillIds.has(edge.source) ? edge.source : skillIds.has(edge.target) ? edge.target : ''
    if (jobId && skillId) {
      const list = skillLinks.get(jobId) || []
      list.push(skillId)
      skillLinks.set(jobId, list)
    }
  })
  skillLinks.forEach((skillIds, jobId) => {
    const parent = layout.get(jobId)
    if (!parent) return
    const unique = [...new Set(skillIds)].sort()
    unique.forEach((skillId, index) => {
      if (layout.has(skillId)) return
      const ring = Math.floor(index / 14)
      const slot = index % 14
      const angle = (slot / 14) * Math.PI * 2 + ring * .42
      const distance = 50 + ring * 28
      layout.set(skillId, { x: parent.x + Math.cos(angle) * distance, y: parent.y + Math.sin(angle) * distance })
    })
  })
  skills.forEach((node, index) => {
    if (!layout.has(node.id)) {
      const radius = 520 + (index % 4) * 90
      const angle = index * 2.39996323
      layout.set(node.id, { x: radius * Math.cos(angle), y: radius * Math.sin(angle) })
    }
  })
  nodes.forEach((node, index) => {
    if (!layout.has(node.id)) layout.set(node.id, { x: (index % 10) * 90, y: Math.floor(index / 10) * 90 })
  })
  drawNodes.value = nodes.map(node => ({ ...node, point: layout.get(node.id) || { x: 0, y: 0 } }))
  nodeById.clear()
  drawNodes.value.forEach(node => nodeById.set(node.id, node))
}

function resizeCanvas() {
  const canvas = canvasRef.value
  const wrap = canvasWrapRef.value
  if (!canvas || !wrap) return
  const ratio = window.devicePixelRatio || 1
  canvas.width = Math.floor(wrap.clientWidth * ratio)
  canvas.height = Math.floor(wrap.clientHeight * ratio)
  canvas.style.width = `${wrap.clientWidth}px`
  canvas.style.height = `${wrap.clientHeight}px`
  draw()
}

function worldToScreen(point: Point) {
  const canvas = canvasRef.value
  if (!canvas) return { x: 0, y: 0 }
  return { x: canvas.clientWidth / 2 + (point.x + transform.x) * transform.scale, y: canvas.clientHeight / 2 + (point.y + transform.y) * transform.scale }
}
function screenToWorld(x: number, y: number) {
  const canvas = canvasRef.value
  if (!canvas) return { x: 0, y: 0 }
  return { x: (x - canvas.clientWidth / 2) / transform.scale - transform.x, y: (y - canvas.clientHeight / 2) / transform.scale - transform.y }
}
function visibleNode(node: DrawNode) { return activeKinds.value.has(node.kind) }

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const ratio = window.devicePixelRatio || 1
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight)
  const nodes = drawNodes.value.filter(visibleNode)
  const highlights = highlightIds.value
  const hasHighlight = highlights.size > 0
  ctx.save()
  ctx.lineWidth = .7
  graphData.value.edges.forEach((edge, index) => {
    const source = nodeById.get(edge.source)
    const target = nodeById.get(edge.target)
    if (!source || !target || !visibleNode(source) || !visibleNode(target)) return
    if (!hasHighlight && index >= DEFAULT_EDGE_LIMIT) return
    if (hasHighlight && !(highlights.has(source.id) && highlights.has(target.id))) return
    const sourcePoint = worldToScreen(source.point)
    const targetPoint = worldToScreen(target.point)
    const active = true
    ctx.beginPath(); ctx.moveTo(sourcePoint.x, sourcePoint.y); ctx.lineTo(targetPoint.x, targetPoint.y)
    ctx.strokeStyle = active ? (edge.kind.includes('similar') ? 'rgba(142,137,196,.25)' : 'rgba(79,162,255,.27)') : 'rgba(75,79,128,.06)'
    ctx.setLineDash(edge.kind.includes('similar') ? [4, 5] : [])
    ctx.stroke()
  })
  ctx.restore()
  nodes.forEach(node => {
    const point = worldToScreen(node.point)
    const size = nodeSize(node) * Math.max(.72, transform.scale)
    const color = colors[node.kind]
    const active = !hasHighlight || highlights.has(node.id)
    const match = searchKeyword.value && searchMatches.value.some(item => item.id === node.id)
    ctx.save()
    ctx.globalAlpha = active ? 1 : .12
    ctx.shadowColor = color
    ctx.shadowBlur = node.kind === 'skill' ? 8 : 16
    ctx.fillStyle = color
    ctx.beginPath(); ctx.arc(point.x, point.y, size, 0, Math.PI * 2); ctx.fill()
    ctx.shadowBlur = 0
    ctx.lineWidth = match ? 2.5 : 1.2
    ctx.strokeStyle = match ? '#fff' : 'rgba(255,255,255,.5)'
    ctx.stroke()
    if (node.kind === 'job' || match || (selectedNode.value && selectedNode.value.id === node.id)) {
      ctx.font = `${node.kind === 'job' ? 9 : 10}px "Microsoft YaHei", sans-serif`
      ctx.fillStyle = active ? 'rgba(232,239,255,.82)' : 'rgba(180,188,225,.25)'
      ctx.textAlign = 'center'; ctx.fillText(nodeLabel(node), point.x, point.y + size + 13)
    }
    ctx.restore()
  })
}

function nodeAt(x: number, y: number) {
  const world = screenToWorld(x, y)
  return drawNodes.value.filter(visibleNode).slice().reverse().find(node => {
    const size = nodeSize(node) + 7 / transform.scale
    return Math.hypot(node.point.x - world.x, node.point.y - world.y) <= size
  })
}
function highlightNode(node: GraphNode | null) {
  if (!node) { highlightIds.value = new Set(); return }
  const ids = new Set<string>([node.id])
  graphData.value.edges.forEach((edge) => {
    if (edge.source === node.id) ids.add(edge.target)
    if (edge.target === node.id) ids.add(edge.source)
  })
  highlightIds.value = ids
}
function onCanvasClick(event: MouseEvent) {
  if (drag.moved) { drag.moved = false; return }
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  const node = nodeAt(event.clientX - rect.left, event.clientY - rect.top)
  selectedNode.value = node || null
  highlightNode(node || null)
  draw()
}
function onPointerDown(event: PointerEvent) {
  drag.active = true; drag.moved = false; drag.startX = event.clientX; drag.startY = event.clientY; drag.originX = transform.x; drag.originY = transform.y
  canvasRef.value?.setPointerCapture(event.pointerId)
}
function onPointerMove(event: PointerEvent) {
  if (!drag.active) return
  const dx = event.clientX - drag.startX; const dy = event.clientY - drag.startY
  drag.moved = drag.moved || Math.abs(dx) > 3 || Math.abs(dy) > 3
  transform.x = drag.originX + dx / transform.scale; transform.y = drag.originY + dy / transform.scale; draw()
}
function onPointerUp() { drag.active = false }
function onWheel(event: WheelEvent) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  const before = screenToWorld(event.clientX - rect.left, event.clientY - rect.top)
  transform.scale = Math.min(2.7, Math.max(.45, transform.scale * (event.deltaY > 0 ? .9 : 1.1)))
  const after = screenToWorld(event.clientX - rect.left, event.clientY - rect.top)
  transform.x += after.x - before.x; transform.y += after.y - before.y; draw()
}
function resetView() { transform.scale = 1; transform.x = 0; transform.y = 0; selectedNode.value = null; highlightIds.value = new Set(); draw() }
function focusFirstMatch() {
  const node = searchMatches.value[0]
  if (!node) { ElMessage.warning('没有匹配节点'); return }
  selectedNode.value = node; highlightNode(node); transform.x = -node.point.x; transform.y = -node.point.y; draw()
}
async function loadGraph() {
  loading.value = true
  try {
    graphData.value = await getGraphData('2026', 'all')
    buildLayout(); await nextTick(); resizeCanvas()
  } catch { ElMessage.error('图谱数据加载失败') }
  finally { loading.value = false; draw() }
}
watch([activeKinds, searchKeyword], () => draw(), { deep: true })
onMounted(() => { resizeObserver = new ResizeObserver(resizeCanvas); if (canvasWrapRef.value) resizeObserver.observe(canvasWrapRef.value); loadGraph() })
onUnmounted(() => resizeObserver?.disconnect())
</script>

<style scoped>
.nebula-page { position: relative; width: 100%; height: calc(100vh - 126px); min-height: 620px; overflow: hidden; border: 1px solid #171733; border-radius: 3px; background: #050511; color: #dbe2ff; box-shadow: 0 18px 40px rgba(20, 16, 45, .12); }
.nebula-stars { position: absolute; inset: 0; opacity: .75; pointer-events: none; background: radial-gradient(circle at 50% 48%, rgba(48, 45, 116, .24), transparent 38%), radial-gradient(1px 1px at 11% 25%, #fff, transparent 70%), radial-gradient(1px 1px at 31% 64%, #8693e8, transparent 70%), radial-gradient(1px 1px at 74% 19%, #fff, transparent 70%), radial-gradient(1px 1px at 88% 57%, #7c8be4, transparent 70%), radial-gradient(1px 1px at 63% 82%, #fff, transparent 70%), radial-gradient(1px 1px at 21% 86%, #6d80d5, transparent 70%); }
.nebula-header { position: absolute; top: 0; left: 0; right: 0; z-index: 5; display: flex; align-items: center; justify-content: center; height: 56px; border-bottom: 1px solid rgba(76, 75, 139, .24); background: rgba(5, 5, 17, .76); }
.nebula-title { color: #4da6ff; font-size: 20px; font-weight: 700; letter-spacing: 2px; text-shadow: 0 0 14px rgba(77, 166, 255, .35); }
.nebula-title b { color: #7adf77; font-size: 18px; }
.nebula-meta { position: absolute; right: 22px; display: flex; align-items: center; gap: 10px; color: #777aa8; font-size: 11px; }
.nebula-meta i { width: 4px; height: 4px; border-radius: 50%; background: #4da6ff; }
.panel-glass { border: 1px solid rgba(105, 106, 189, .27); background: rgba(9, 9, 33, .83); border-radius: 14px; box-shadow: 0 10px 30px rgba(0, 0, 0, .28); backdrop-filter: blur(12px); }
.nebula-control { position: absolute; top: 68px; left: 16px; z-index: 6; width: 244px; padding: 16px; }
.nebula-label { display: block; margin: 0 0 8px; color: #777aa8; font-size: 11px; letter-spacing: 1px; }
.nebula-search { display: flex; align-items: center; gap: 8px; height: 34px; padding: 0 10px; border: 1px solid rgba(88, 89, 163, .34); border-radius: 10px; background: rgba(19, 19, 53, .72); color: #7681d3; }
.nebula-search input { min-width: 0; flex: 1; border: 0; outline: 0; background: transparent; color: #dbe2ff; font-size: 12px; }
.nebula-search input::placeholder { color: #62668f; }
.nebula-search button, .detail-head button { border: 0; background: transparent; color: #7b80a9; font-size: 18px; }
.search-hint { margin: 6px 0 12px; color: #7b80a9; font-size: 10px; }
.nebula-filters { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 20px; }
.nebula-filters button { display: inline-flex; align-items: center; gap: 6px; padding: 6px 9px; border: 1px solid rgba(93, 94, 172, .45); border-radius: 10px; background: rgba(30, 30, 74, .7); color: #d5dcff; font-size: 11px; }
.nebula-filters button.off { opacity: .35; }
.nebula-filters i { width: 8px; height: 8px; border-radius: 50%; }
.nebula-legend { display: grid; gap: 8px; padding-bottom: 12px; }
.nebula-legend span { display: flex; align-items: center; color: #a1a4c2; font-size: 11px; }
.nebula-legend i { display: inline-block; width: 10px; height: 10px; margin-right: 8px; border-radius: 50%; }
.nebula-legend .legend-job { background: #4da6ff; box-shadow: 0 0 9px #4da6ff; }
.nebula-legend .legend-skill { background: #2ee66b; box-shadow: 0 0 9px #2ee66b; }
.nebula-legend .legend-industry { background: #c77dff; box-shadow: 0 0 9px #c77dff; }
.nebula-legend .legend-edge { width: 18px; height: 2px; border-radius: 0; background: #4da6ff; }
.nebula-legend .legend-edge.dashed { height: 0; border-top: 2px dashed #777aa8; }
.nebula-tools { display: flex; gap: 8px; padding-top: 12px; border-top: 1px solid rgba(105, 106, 189, .18); }
.nebula-tools button { display: inline-flex; align-items: center; gap: 5px; padding: 5px 6px; border: 0; background: transparent; color: #8287b4; font-size: 10px; }
.nebula-tools button:hover { color: #fff; }
.nebula-canvas-wrap { position: absolute; inset: 56px 0 0; z-index: 1; }
.nebula-canvas-wrap canvas { display: block; width: 100%; height: 100%; cursor: grab; }
.nebula-canvas-wrap canvas:active { cursor: grabbing; }
.nebula-state { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 9px; color: #7679a8; font-size: 13px; pointer-events: none; }
.nebula-detail { position: absolute; top: 68px; right: 16px; z-index: 6; width: min(360px, calc(100% - 32px)); max-height: calc(100% - 92px); overflow-y: auto; padding: 16px; scrollbar-width: thin; }
.detail-head { display: flex; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid rgba(105, 106, 189, .2); }
.detail-head small, .detail-section label { color: #777aa8; font-size: 10px; letter-spacing: 1px; }
.detail-head h3 { margin: 5px 0 0; color: #f4f6ff; font-size: 16px; line-height: 1.4; overflow-wrap: anywhere; }.detail-en { margin: 4px 0 0; color: #8f96c6; font-size: 11px; line-height: 1.5; overflow-wrap: anywhere; }
.detail-kpis { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 14px 0; }
.detail-kpis span { padding: 10px; border-radius: 9px; background: rgba(75, 90, 187, .15); text-align: center; }
.detail-kpis b { display: block; color: #69b9ff; font-size: 19px; }
.detail-kpis small { color: #878ab7; font-size: 10px; }
.detail-section { margin-top: 13px; }
.detail-section p { margin: 5px 0 0; color: #babfe0; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; word-break: break-word; }
.nebula-hint { position: absolute; right: 0; bottom: 18px; left: 0; z-index: 3; color: rgba(190, 195, 237, .4); font-size: 11px; letter-spacing: 1px; text-align: center; pointer-events: none; }
@media (max-width: 800px) { .nebula-page { height: calc(100vh - 110px); min-height: 560px; } .nebula-control { width: 210px; } .nebula-detail { right: 10px; width: calc(100% - 20px); max-height: calc(100% - 82px); } .nebula-title { font-size: 15px; letter-spacing: 1px; } .nebula-title b { font-size: 13px; } .nebula-meta { display: none; } }
</style>