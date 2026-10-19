<template>
  <section ref="rootRef" class="nebula-page">
    <canvas ref="galaxyRef" class="galaxy-background" aria-hidden="true"></canvas>
    <header class="nebula-header">
      <div class="nebula-title"><span>岗位星云图谱</span><b>· Career Nebula</b></div>
      <div class="nebula-meta"><span>{{ graphData.nodes.length }} 个节点</span><i></i><span>{{ graphData.edges.length }} 条关联</span></div>
    </header>

    <aside v-show="!props.panelsHidden" class="nebula-control panel-glass" tabindex="0" aria-label="图谱控制，可滚动">
      <p class="snapshot-note">探索岗位、技能与历史场景<br />单击星体显示直接关联；点击空白取消。</p>
      <label class="nebula-label">搜索</label>
      <div class="nebula-search">
        <el-icon><Search /></el-icon>
        <input v-model="searchKeyword" placeholder="输入岗位或技能..." @keydown.enter="onSearchEnter" />
        <button v-if="searchKeyword" type="button" @click="searchKeyword = ''">×</button>
      </div>
      <p v-if="searchKeyword" class="search-hint">{{ searchMatches.length ? `找到 ${searchMatches.length} 个节点` : '没有匹配节点' }}</p>
      <div v-if="searchKeyword.trim()" class="nebula-search-nav">
        <button type="button" aria-label="上一个搜索结果" :disabled="loading || !searchMatches.length" @click="stepSearch(-1)">‹</button>
        <span aria-live="polite">{{ searchIndex < 0 ? 0 : searchIndex + 1 }} / {{ searchMatches.length }}</span>
        <button type="button" aria-label="下一个搜索结果" :disabled="loading || !searchMatches.length" @click="stepSearch(1)">›</button>
      </div>

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
        <span><i class="legend-industry"></i>历史场景（旧投影）</span>
        <span><i class="legend-edge"></i>岗位-技能关联</span>
        <span><i class="legend-edge scenario"></i>岗位-场景关联</span>
        <span><i class="legend-edge dashed"></i>历史 RELATED_TO</span>
      </div>

      <label class="nebula-label">分析图层</label>
      <label class="snapshot-note"><input v-model="showDerived" type="checkbox" />显示候选派生相似（{{ artifact?.derived_edges?.length ?? 0 }}）</label>
      <p class="snapshot-note">{{ spatialMode && stellarMode ? '蓝色斜角标识岗位，绿色横标识技能，紫色纵标识历史场景。' : '蓝色岗位、绿色技能、紫色历史场景。' }}星体外观不代表职业重要性；装饰星尘不计入知识节点。</p>
      <p class="snapshot-note" aria-live="polite">{{ relationSummary }}</p>
      <p v-if="showDerived" class="snapshot-note">{{ derivedSummary }}</p>
      <p class="snapshot-note">{{ levelSummary }}</p>
      <div class="nebula-tools">
        <button type="button" aria-label="放大图谱" @click="zoomView(-1)">＋ 放大</button>
        <button type="button" aria-label="缩小图谱" @click="zoomView(1)">− 缩小</button>
      </div>
      <div class="nebula-tools">
        <button type="button" @click="resetView"><el-icon><Refresh /></el-icon>重置视图</button>
        <button type="button" @click="loadGraph"><el-icon><RefreshRight /></el-icon>刷新数据</button>
      </div>
      <div v-if="savedView" class="nebula-tools">
        <button type="button" @click="returnToView">返回原视角</button>
      </div>
      <details class="snapshot-note technical-info"><summary>技术信息 / 版本与诊断</summary>
      <p class="snapshot-note">已核验历史交接快照<br />非实时数据库 · 非新版标准岗位目录</p>
      <p v-if="visual !== 'p22'" class="snapshot-note reference-mark">受控回放：{{ visual === 'p1a2' ? 'P1-A.2 原知识点 shader' : 'P2.1 视觉' }}<br />同历史输入 / 同布局 / 同投影，非原独立站相机</p>
      <details class="snapshot-note layout-provenance"><summary>布局来源（候选，非职业分类）</summary><p>Jaccard 0.10 + Leiden · PR32@377e9b8<br />layout-v1 · seed 42。只用于候选空间布局；默认不显示社区分析层，不映射八大职业大类。</p></details>
      <a class="fallback-link" href="#/graph?graphRenderer=legacy">切换旧 Canvas</a>
      <details class="snapshot-note"><summary>视觉回退 / 受控对照</summary><p><a href="?graphCamera=fixed&graphVisual=p21#/graph">P2.1视觉回退</a> · <a href="?graphCamera=fixed&graphVisual=p22#/graph">P2.2固定投影</a> · <a href="?graphStars=p23#/graph">P2.3星点外观</a> · <a href="?#/graph">P2.4恒星</a></p><p>P1-A.2原shader回放通过graphVisual=p1a2；对照视图统一使用graphCompare=overview/middle/near。仅作比较，不改变数据。</p></details>
      <details v-if="spatialMode" class="snapshot-note"><summary>三维操作与空间说明</summary><p>左拖旋转 · 右拖平移 · WASD屏幕平移 · Q/E左/右滚转 · 滚轮缩放 · R恢复全景。点击星体原位选择。</p><p>display-depth-v1 为确定性展示深度，空间距离不代表已验证的岗位相似性；八大领域沿用B3职业大类，历史岗位未自动归类。旋臂不代表关系，社区分析默认关闭。</p></details>
      <details v-if="relationAudit" class="snapshot-note relation-audit"><summary>关系显示逐项核对</summary><p>当前范围 {{ relationAudit.scope }} / 全图 {{ graphData.edges.length }}。缺项不等于业务上没有关联。</p><div v-for="(label,key) in auditLabels" :key="key">{{ label }}：{{ relationAudit[key] }}</div><p>以下分类互斥，和已提交数量相加等于当前范围。直连只按类型隐藏，不受LOD、视口或预算删除。</p></details>
        <label v-if="spatialMode && stellarMode">恒星外观预设
          <select v-model="stellarPreset" aria-label="恒星外观预设"><option value="">稳定 ID 混合</option><option v-for="type in STELLAR_TYPES" :key="type" :value="type">{{ stellarNames[type] }}</option></select>
        </label>
        <p>外观采用自行编写的程序化材质，四类仅为视觉预设；不对应职业重要性、需求、JD 数量或质量。</p>
      </details>
    </aside>

    <div ref="canvasWrapRef" class="nebula-canvas-wrap">
      <canvas ref="canvasRef" tabindex="0" aria-label="知识银河，左拖旋转，右拖平移，滚轮缩放" @contextmenu.prevent @click="onCanvasClick" @pointerdown="onPointerDown" @pointermove="onPointerMove" @pointerup="onPointerUp" @pointercancel="onPointerUp" @pointerleave="onPointerLeave" @wheel="onWheel"></canvas>
      <div v-if="loading" class="nebula-state"><el-icon class="is-loading"><Loading /></el-icon><span>正在加载图谱数据...</span></div>
      <div v-else-if="!graphData.nodes.length" class="nebula-state"><el-icon><DataAnalysis /></el-icon><span>{{ loadError || "暂无图谱数据" }}</span><a href="#/graph?graphRenderer=legacy">旧 Canvas 回退</a></div>
    </div>

    <div v-if="webglError" class="renderer-error">银河渲染不可用。<a href="#/graph?graphRenderer=legacy">切换旧 Canvas</a></div>
    <aside v-if="selectedNode" v-show="!props.panelsHidden" class="nebula-detail panel-glass" tabindex="0" aria-label="节点详情，可滚动">
      <div class="detail-head">
        <div><small>{{ nodeKindLabel(selectedNode.kind) }}</small><h3>{{ selectedNode.label }}</h3><p v-if="selectedNode.name_en && selectedNode.name_en !== selectedNode.label" class="detail-en">{{ selectedNode.name_en }}</p></div>
        <button type="button" aria-label="关闭详情" @click="clearSelection">×</button>
      </div>
      <div class="detail-kpis"><span><b>{{ connectedCount }}</b><small>历史直接关系</small></span><span><b>{{ connectedNodeCount }}</b><small>不同邻接节点</small></span></div>
      <p v-if="spatialMode && stellarMode" class="snapshot-note">外观：{{ stellarNames[stellarProfile(selectedNode.id,stellarPreset || undefined).type] }} · 仅视觉分配</p>
      <div class="nebula-tools"><button type="button" @click="viewAllConnections">定位全部关联</button><button v-if="spatialMode && stellarMode" type="button" @click="inspectStar">近距离观察</button></div>
      <div v-if="selectedNode.kind === 'job'" class="detail-section"><label>历史分类 / 演化（旧口径）</label><p>{{ selectedNode.category || '—' }} · {{ selectedNode.is_emerging ? '新一代岗位' : '现有岗位' }}<span v-if="selectedNode.evolution?.stage"> · {{ selectedNode.evolution.stage }}</span></p></div>
      <div v-if="selectedNode.kind === 'job'" class="detail-section"><label>来源平台</label><p>{{ selectedNode.platform_label || '—' }}</p></div>
      <div v-if="selectedNode.kind === 'job' && selectedNode.core_duties" class="detail-section"><label>核心职责</label><p>{{ selectedNode.core_duties }}</p></div>
      <div v-if="selectedNode.kind === 'job' && selectedNode.required_skills?.length" class="detail-section"><label>历史必备（非新版五态）</label><p>{{ selectedNode.required_skills.join('、') }}</p></div>
      <div v-if="selectedNode.kind === 'job' && selectedNode.bonus_skills?.length" class="detail-section"><label>历史加分（非新版五态）</label><p>{{ selectedNode.bonus_skills.join('、') }}</p></div>
      <div v-if="selectedNode.kind === 'job' && selectedNode.scenarios?.length" class="detail-section"><label>历史 scenarios 原文（旧口径）</label><p>{{ selectedNode.scenarios.join('、') }}</p></div>
      <div v-if="selectedNode.status" class="detail-section"><label>状态</label><p>{{ selectedNode.status === 'stable' ? '稳定' : selectedNode.status === 'emerging' ? '新一代' : selectedNode.status }}</p></div>
      <div v-if="selectedNode.kind !== 'job'" class="detail-section"><label>节点名称</label><p>{{ selectedNode.label }}</p></div>
      <div class="detail-section"><label>直接关联 · 每页 30 条</label>
        <p>共 {{ directEdges.length }} 条；类型过滤隐藏 {{ directEdges.length - typeVisibleDirect }} 条</p>
        <ol class="connection-list" :start="connectionPage * 30 + 1">
          <li v-for="edge in connectionRows" :key="edge.sourceIndex" :class="{ 'edge-focused': focusedEdgeIndex === edge.sourceIndex }" @mouseenter="focusRelation(edge.sourceIndex)" @mouseleave="focusRelation(null)">
            <button type="button" :disabled="connectionHidden(edge)" @click="selectConnection(edge)">{{ nodeById.get(edge.source === selectedNode.id ? edge.target : edge.source)?.label }}</button>
            <small v-if="connectionHidden(edge)">另一端类型当前隐藏；原关系仍在数据中。</small>
            <button v-if="connectionHidden(edge)" type="button" @click="showConnection(edge)">显示该类型并选中</button>
            <small>{{ relationName(edge.kind) }} · {{ nodeKindLabel(nodeById.get(edge.source === selectedNode.id ? edge.target : edge.source)?.kind || 'job') }}</small>
            <button class="edge-focus-button" :disabled="connectionHidden(edge)" :aria-label="`高亮原关系 ${edge.sourceIndex}`" @focus="focusRelation(edge.sourceIndex)" @blur="focusRelation(null)" @click="focusRelation(edge.sourceIndex)">高亮这条原边</button>
            <details><summary>原始关系 / 来源索引 {{ edge.sourceIndex }}</summary><pre>{{ JSON.stringify(edge.raw, null, 2) }}</pre></details>
            <small v-if="edge.raw?.source_indices">来源索引 {{ JSON.stringify(edge.raw.source_indices) }}</small>
          </li>
        </ol>
        <div class="nebula-search-nav"><button aria-label="上一页关联" :disabled="connectionPage === 0" @click="connectionPage--">‹</button><span>{{ connectionPage + 1 }} / {{ Math.max(1, Math.ceil(directEdges.length / 30)) }}</span><button aria-label="下一页关联" :disabled="(connectionPage + 1) * 30 >= directEdges.length" @click="connectionPage++">›</button></div>
      </div>
      <details class="detail-section"><summary>技术信息 / 身份与来源</summary><p>{{ selectedNode.id }}<br />graph.json → nodes[{{ selectedNode.sourceIndex }}]</p><p>历史 job_count：{{ selectedNode.raw?.job_count ?? '未提供' }}（不等于直连数量）</p><details class="layout-provenance"><summary>候选布局说明</summary><p>社区：{{ communityLabel }}。这是算法布局归属，不是审核后的职业分类。</p></details></details>
      <details class="detail-section"><summary>原始节点属性（历史快照）</summary><pre>{{ JSON.stringify(selectedNode.raw, null, 2) }}</pre></details>
      <div class="detail-section"><label>使用提示</label><p>已高亮该节点的直接关联，点击空白区域可清除高亮。画布外的关联可通过“定位全部关联”查看。</p></div>
    </aside>

    <div class="nebula-hint">{{ spatialMode ? '左拖旋转 · 右拖 / WASD 平移 · Q/E 滚转 · 滚轮缩放 · R 全景 · 单击选择' : '点击节点查看详情 · 滚轮缩放 · 拖拽平移' }}</div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, shallowRef, watch } from 'vue'
import { DataAnalysis, Loading, Refresh, RefreshRight, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { type GraphData, type GraphNode, type GraphEdge } from '../api/graph'
import { loadHistoricalGraph, visibleKnowledgeIds, type LayoutArtifact } from '../graph/historicalSnapshot'

import type { Point } from '../graph/nebulaViewport'
import { selectEdgePlan, edgeAppearance, segmentInBounds, type Bounds } from '../graph/nebulaEdges'
import { toScreen, toWorld, focusTransform, searchNodes, resolveSelection, availableGraphArea, nextSearchIndex, nextZoomScale, type Transform } from '../graph/nebulaViewport'

import { nodeAppearance, selectLabels, type LabelCandidate } from '../graph/nebulaPresentation'
import { starAppearance, createStarSprites, paintStar, placeStarLabels } from '../graph/starPresentation'
import { planRelations, fanControls, curveIntersects } from '../graph/relationReadability'
import { comparisonSettings } from '../graph/comparisonView'
import { cameraKey, type GalaxyCamera, type CameraState } from '../graph/galaxy/camera'
import type { SpatialKnowledge } from '../graph/galaxy/knowledge'
import { stellarProfile, stellarNames, STELLAR_TYPES, type StellarType } from '../graph/galaxy/stellarAppearance'

const comparison=comparisonSettings(window.location.search)
const visual=comparison.visual
let overview = !comparison.transform
let fittedScale = 1
let lastFit: { area: Bounds; points: number; outside: number } | null = null

const query = new URLSearchParams(window.location.search)
const stellarMode=query.get('graphStars')!=='p23'
const stellarPreset=ref<StellarType|''>('')
const spatialMode=query.get('graphCamera')!=='fixed'&&visual==='p22'&&!comparison.preset
const cameraRig=shallowRef<GalaxyCamera|null>(null)
let spatialKnowledge:SpatialKnowledge|null=null,spatialDirty=true,disposed=false,composing=false
const cameraKeys=new Set<string>()
let savedCamera:CameraState|null=null
let statsTimer:ReturnType<typeof setInterval>|null=null
const debug = query.get('nebulaDebug') === '1' || Boolean(comparison.preset)
let layoutMs = 0
let loadGeneration = 0
interface DrawNode extends GraphNode { point: Point }

const props = defineProps<{ panelsHidden?: boolean; immersive?: boolean }>()
let lastSize = { width: 0, height: 0, immersive: false }

const rootRef = ref<HTMLElement | null>(null)
const canvasWrapRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const galaxyRef = ref<HTMLCanvasElement | null>(null)
let galaxy: {resize:(w:number,h:number)=>void;dispose:()=>void;stats:()=>unknown;reference:(nodes:DrawNode[],ids:Set<string>,selected:string|null)=>void} | null = null
let starSprites:ReturnType<typeof createStarSprites>|null=null
const artifact = shallowRef<LayoutArtifact | null>(null)
const meta = computed(() => new Map(artifact.value?.nodes.map(n=>[n.id,n]) || []))
const showDerived = ref(false)
const loadError = ref('')
const webglError = ref(false)
const relationSummary = ref('')
const relationAudit = shallowRef<ReturnType<typeof planRelations>['audit']|null>(null)
const auditLabels={interactionHidden:'未选择，按交互隐藏',invalidEndpoint:'无有效端点',typeHidden:'按类型隐藏',lodHidden:'LOD折叠',unplaced:'缺少有效坐标',viewportHidden:'视口外省略',lengthHidden:'长度策略省略',budgetHidden:'视觉预算截断'}
const focusedEdgeIndex=ref<number|null>(null)
function focusRelation(index:number|null|undefined){focusedEdgeIndex.value=index??null;draw()}
const derivedSummary = ref('')
const levelSummary = ref('')
const connectionPage = ref(0)
const loading = ref(false)
const graphData = shallowRef<GraphData>({ nodes: [], edges: [], stats: { totalNodes: 0, totalEdges: 0, added: 0, removed: 0, changed: 0 } })
const searchKeyword = ref('')
const searchIndex = ref(-1)
const selectedNode = ref<GraphNode | null>(null)
const hoveredId = ref<string | null>(null)
const filters = reactive([
  { kind: 'job' as const, label: '岗位', color: '#4da6ff', active: true },
  { kind: 'skill' as const, label: '技能', color: '#2ee66b', active: true },
  { kind: 'industry' as const, label: '历史场景', color: '#c77dff', active: true },
])

const nodeById = new Map<string, DrawNode>()
const drawNodes = shallowRef<DrawNode[]>([])
const worldPositions=computed(()=>new Map(drawNodes.value.map(node=>[node.id,node.point])))
const highlightIds = ref<Set<string>>(new Set())
const transform = reactive({ scale: 1, x: 0, y: 0 })
const savedView = ref<{ transform: Transform; fittedScale: number; overview: boolean } | null>(null)
const drag = reactive({ active: false, moved: false, startX: 0, startY: 0, originX: 0, originY: 0, lastX:0,lastY:0,button:0 })
let resizeObserver: ResizeObserver | null = null

const activeKinds = computed(() => new Set(filters.filter(item => item.active).map(item => item.kind)))
const searchMatches = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return []
  return searchNodes(drawNodes.value, keyword, activeKinds.value)
})
const searchMatchIds = computed(() => new Set(searchMatches.value.map(node => node.id)))
const connectedCount = computed(() => {
  if (!selectedNode.value) return 0
  return graphData.value.edges.filter(edge => edge.source === selectedNode.value?.id || edge.target === selectedNode.value?.id).length
})

const directEdges = computed(() => graphData.value.edges.filter(e=> e.source===selectedNode.value?.id || e.target===selectedNode.value?.id))
const focusedEdgeIds=computed(()=>{
  const edge=focusedEdgeIndex.value===null?undefined:directEdges.value.find(e=>e.sourceIndex===focusedEdgeIndex.value)
  return new Set(edge?[edge.source,edge.target]:[])
})
const connectionRows = computed(() => directEdges.value.slice(connectionPage.value*30,(connectionPage.value+1)*30))
const connectedNodeCount = computed(() => new Set(directEdges.value.map(e=>e.source===selectedNode.value?.id?e.target:e.source)).size)
const typeVisibleDirect = computed(() => directEdges.value.filter(e=>activeKinds.value.has(nodeById.get(e.source)!.kind)&&activeKinds.value.has(nodeById.get(e.target)!.kind)).length)
const communityLabel = computed(() => {
  const info=meta.value.get(selectedNode.value?.id || '')
  if(!info) return '未参与'
  if(selectedNode.value?.kind==='job') return info.community?`候选 ${info.community.slice(0,8)}`:'孤点 / 无社区'
  return info.communities?.length?`${info.communities.length} 个关联社区（不独占归类）`:'无关联社区'
})
const knowledgeIds = computed(() => visibleKnowledgeIds(graphData.value.nodes,meta.value,transform.scale,new Set([...highlightIds.value,...searchMatchIds.value])))
function selectConnection(edge:GraphEdge) {
  if(connectionHidden(edge)){ElMessage.info('另一端类型当前隐藏，请先显式显示该类型');return}
  const id=edge.source===selectedNode.value?.id?edge.target:edge.source
  highlightNode(nodeById.get(id) || null);nextTick(draw)
}
function connectionHidden(edge:GraphEdge) {
  const id=edge.source===selectedNode.value?.id?edge.target:edge.source,node=nodeById.get(id)
  return Boolean(node&&!activeKinds.value.has(node.kind))
}
async function showConnection(edge:GraphEdge) {
  const id=edge.source===selectedNode.value?.id?edge.target:edge.source,node=nodeById.get(id)
  if(!node)return
  overview=false
  const filter=filters.find(f=>f.kind===node.kind);if(filter)filter.active=true
  await nextTick();selectConnection(edge)
}
function measureInteraction(name:string,start:number) {
  if(!debug || typeof requestAnimationFrame!=='function')return
  requestAnimationFrame(()=>{if(rootRef.value)rootRef.value.dataset.interaction=JSON.stringify({name,handlerToNextFrameMs:performance.now()-start})})
}
const colors: Record<string, string> = { job: '#4da6ff', skill: '#2ee66b', industry: '#c77dff' }

function relationName(kind:string){return kind==='REQUIRES'?'岗位技能关联':kind==='APPLIES_TO'?'历史场景关联':kind==='RELATED_TO'?'历史岗位关联':kind}
function nodeKindLabel(kind: GraphNode['kind']) { return kind === 'job' ? '岗位节点' : kind === 'skill' ? '技能节点' : '历史场景（旧 Industry 投影）' }
function appearanceFor(node:GraphNode,selected=false,matched=false,hovered=false){const activeHover=hovered||(focusedEdgeIndex.value!==null&&focusedEdgeIds.value.has(node.id));return visual==='p22'?starAppearance(node.kind,transform.scale,selected,matched,activeHover):nodeAppearance(node.kind,nodeSize(node),transform.scale,selected,matched,activeHover)}
function nodeSize(node: GraphNode) { return node.kind === 'job' ? Math.max(7, Math.min(18, (node.size || 14) * .42)) : node.kind === 'industry' ? 13 : Math.max(3.5, Math.min(8, (node.size || 8) * .32)) }
function nodeLabel(node: GraphNode) {
  const maxChars = node.kind === 'job' ? Math.max(5, Math.min(12, Math.floor(nodeSize(node) * .8))) : 9
  return node.label.length > maxChars ? `${node.label.slice(0, maxChars - 1)}…` : node.label
}

async function buildLayout(data: GraphData, generation: number) {
  const start = performance.now()
  const nodes = data.nodes
  const layout = new Map(artifact.value?.nodes.map(n=>[n.id,{x:n.x,y:n.y}]) || [])
  if (generation !== loadGeneration) return
  layoutMs = performance.now() - start
  graphData.value = data
  searchIndex.value = -1
  drawNodes.value = nodes.map(node => ({ ...node, point: layout.get(node.id) || { x: 0, y: 0 } }))
  nodeById.clear()
  drawNodes.value.forEach(node => nodeById.set(node.id, node))
  if(spatialKnowledge)spatialKnowledge.setData(nodes,data.edges,artifact.value!.nodes)
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
  galaxy?.resize(wrap.clientWidth,wrap.clientHeight)
  const changed = lastSize.width !== wrap.clientWidth || lastSize.height !== wrap.clientHeight
  const modeChanged = lastSize.immersive !== Boolean(props.immersive)
  lastSize = { width: wrap.clientWidth, height: wrap.clientHeight, immersive: Boolean(props.immersive) }
  if (changed && !modeChanged && overview && !selectedNode.value) fitGraph()
  draw()
}

function worldToScreen(point: Point) {
  const canvas = canvasRef.value
  if (!canvas) return { x: 0, y: 0 }
  return toScreen(point, { width: canvas.clientWidth, height: canvas.clientHeight }, transform)
}
function screenToWorld(x: number, y: number) {
  const canvas = canvasRef.value
  if (!canvas) return { x: 0, y: 0 }
  return toWorld({ x, y }, { width: canvas.clientWidth, height: canvas.clientHeight }, transform)
}
function visibleNode(node: DrawNode) { return activeKinds.value.has(node.kind) && knowledgeIds.value.has(node.id) }

function draw() {
  if(cameraRig.value&&spatialKnowledge){spatialDirty=true;return}
  const start = performance.now()
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const ratio = window.devicePixelRatio || 1
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight)
  const nodes = drawNodes.value.filter(visibleNode)
  if(visual==='p1a2')galaxy?.reference(drawNodes.value,new Set(nodes.map(n=>n.id)),selectedNode.value?.id || null)
  const highlights = highlightIds.value
  const hasHighlight = highlights.size > 0
  const topLeft = screenToWorld(0, 0)
  const bottomRight = screenToWorld(canvas.clientWidth, canvas.clientHeight)
  const viewport = { left: topLeft.x, top: topLeft.y, right: bottomRight.x, bottom: bottomRight.y }
  const positions = worldPositions.value
  const edgePlan = planRelations(graphData.value.edges, graphData.value.nodes, positions, {
    activeKinds: activeKinds.value, visibleIds:knowledgeIds.value, selectedId: selectedNode.value?.id, viewport, scale: transform.scale,preserveLongNear:visual==='p22',
  })
  relationAudit.value=edgePlan.audit
  const edges = edgePlan.edges
  levelSummary.value = `当前知识层 ${nodes.length} / ${graphData.value.nodes.length}；远景折叠度一技能，近景、搜索与选中邻接自动展开。`
  const curves=visual==='p22'&&selectedNode.value?fanControls(edges,new Map(nodes.map(n=>[n.id,worldToScreen(n.point)])),selectedNode.value.id):new Map<GraphEdge,Point>()
  const focusedEdge=focusedEdgeIndex.value===null?undefined:directEdges.value.find(e=>e.sourceIndex===focusedEdgeIndex.value)
  const focusedIds=new Set(focusedEdge?[focusedEdge.source,focusedEdge.target]:[])
  const screenBounds={left:0,right:canvas.clientWidth,top:0,bottom:canvas.clientHeight}
  let submitted = 0; let painted = 0
  const drawnSourceIndices:number[]=[]
  ctx.save()
  ctx.lineWidth = .7
  edges.forEach((edge) => {
    const source = nodeById.get(edge.source)
    const target = nodeById.get(edge.target)
    if (!source || !target || !visibleNode(source) || !visibleNode(target)) return
    const sourcePoint = worldToScreen(source.point)
    const targetPoint = worldToScreen(target.point)
    submitted++
    const control=curves.get(edge)
    if(control?curveIntersects(sourcePoint,control,targetPoint,screenBounds):segmentInBounds(source.point,target.point,viewport))painted++
    if(edge.sourceIndex!==undefined)drawnSourceIndices.push(edge.sourceIndex)
    ctx.beginPath();ctx.moveTo(sourcePoint.x,sourcePoint.y)
    if(control)ctx.quadraticCurveTo(control.x,control.y,targetPoint.x,targetPoint.y)
    else ctx.lineTo(targetPoint.x,targetPoint.y)
    const style = edgeAppearance(edge, nodeById, transform.scale, Boolean(selectedNode.value), Math.hypot(sourcePoint.x-targetPoint.x,sourcePoint.y-targetPoint.y))
    const exact=focusedEdge===edge
    ctx.strokeStyle=exact?'#f3f7ff':style.color
    ctx.globalAlpha=focusedEdge?(exact ? .95 : .1):(visual==='p22'&&selectedNode.value&&edges.length>64 ? .3 : style.alpha)
    ctx.lineWidth=exact?1.8:(visual==='p22'&&selectedNode.value&&edges.length>64 ? .65 : style.width);ctx.setLineDash(style.dash)
    ctx.stroke()
  })
  ctx.restore()
  relationSummary.value=selectedNode.value
    ? directEdges.value.length?`历史直连 ${directEdges.value.length} · 类型可见 ${typeVisibleDirect.value} · 提交 ${submitted} · 画布相交 ${painted}。无预算截断；指向关联行可高亮原边，主动定位全部关联可适配视口。`:'当前历史快照没有该节点的直接关系记录。'
    : `未选择星体，历史关系按交互隐藏 ${edgePlan.audit.interactionHidden} / ${graphData.value.edges.length}。历史关系 ${graphData.value.edges.length} · 提交 ${submitted} · 画布相交 ${painted}。类型隐藏 ${edgePlan.audit.typeHidden} / LOD折叠 ${edgePlan.audit.lodHidden} / 预算截断 ${edgePlan.audit.budgetHidden}；其余原因可展开核对。`
  let derivedSubmitted=0
  if(showDerived.value && artifact.value?.derived_edges) {
    const derived=artifact.value.derived_edges.map(e=>({...e,kind:'candidate_similarity'}))
    const plan=selectEdgePlan(derived,nodes,positions,{activeKinds:activeKinds.value,viewport,scale:transform.scale,limit:160})
    ctx.save();ctx.strokeStyle='#ffb86b';ctx.globalAlpha=.32;ctx.lineWidth=.8;ctx.setLineDash([3,6])
    for(const edge of plan.edges) {
      const a=nodeById.get(edge.source),b=nodeById.get(edge.target)
      if(!a||!b||!visibleNode(a)||!visibleNode(b))continue
      const p=worldToScreen(a.point),q=worldToScreen(b.point)
      ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.stroke();derivedSubmitted++
    }
    ctx.restore()
    derivedSummary.value=`派生相似：提交 ${derivedSubmitted} / 视口候选 ${plan.candidates} / 总量 ${derived.length}；按节点层级、视口、长度及分层预算显示，近景补全。`
  }
  const matchIds = searchMatchIds.value
  const labels: (LabelCandidate & { text: string; x: number; y: number; font: string; active: boolean;alternatives?:Bounds[] })[] = []
  const starObstacles:{id:string;bounds:Bounds}[]=[]
  nodes.forEach(node => {
    const point = worldToScreen(node.point)
    const match = Boolean(searchKeyword.value) && matchIds.has(node.id)
    const selected = selectedNode.value?.id === node.id
    const hovered = hoveredId.value === node.id
    const appearance = appearanceFor(node,selected,match,hovered||focusedIds.has(node.id))
    const size = appearance.radius
    if ((point.x + size < 0 || point.y + size < 0 || point.x - size > canvas.clientWidth || point.y - size > canvas.clientHeight)) return
    starObstacles.push({id:node.id,bounds:{left:point.x-size-2,right:point.x+size+2,top:point.y-size-2,bottom:point.y+size+2}})
    const color = colors[node.kind]
    const active = !hasHighlight || highlights.has(node.id)
    ctx.save()
    ctx.globalAlpha = active ? 1 : .82
    if(visual==='p22')paintStar(ctx,point.x,point.y,starAppearance(node.kind,transform.scale,selected,match,hovered||focusedIds.has(node.id)),color,starSprites?.get(node.kind,appearance.radius))
    else if(visual==='p21') {
      ctx.shadowColor=color;ctx.shadowBlur=appearance.shadow;ctx.fillStyle=color
      ctx.beginPath();ctx.arc(point.x,point.y,size,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0
      ctx.lineWidth=match?2.5:1.2;ctx.strokeStyle=match?'#fff':'rgba(255,255,255,.5)'
      if(appearance.outline)ctx.stroke()
    }
    if (appearance.label) {
      ctx.font = `${visual==='p22'?(selected||hovered||focusedIds.has(node.id)?11:10):node.kind==='job'?9:10}px "Microsoft YaHei", sans-serif`
      const maxChars=selected||hovered||focusedIds.has(node.id)?32:transform.scale>=1.25?18:12
      const text=visual==='p22'?(node.label.length>maxChars?node.label.slice(0,maxChars-1)+'…':node.label):nodeLabel(node)
      const y = point.y + size + 13
      {
        const halfWidth = ctx.measureText(text).width / 2 + 3
        labels.push({ id: node.id, text, x: point.x, y, font: ctx.font, active,
          priority: selected ? 4 : hovered||focusedIds.has(node.id) ? 3 : match ? 2 : node.kind === 'job' ? 1 : 0,
          bounds: { left: point.x - halfWidth, right: point.x + halfWidth, top: y - 11, bottom: y + 3 },
          alternatives:[{left:point.x+size+7,right:point.x+size+7+2*halfWidth,top:point.y-7,bottom:point.y+7},{left:point.x-halfWidth,right:point.x+halfWidth,top:point.y-size-21,bottom:point.y-size-7},{left:point.x-size-7-2*halfWidth,right:point.x-size-7,top:point.y-7,bottom:point.y+7}],
        })
      }
    }
    ctx.restore()
  })
  const labelBounds={left:0,right:canvas.clientWidth,top:0,bottom:canvas.clientHeight}
  const placements=visual==='p22'?placeStarLabels(labels,labelBounds,graphPanels(),starObstacles,transform.scale<.35?12:transform.scale<.9?70:140):null
  const labelIds=placements?new Set(placements.keys()):selectLabels(labels,labelBounds,graphPanels())
  for (const label of labels) {
    if (!labelIds.has(label.id)) continue
    const placed=placements?.get(label.id);if(placed){label.x=(placed.left+placed.right)/2;label.y=placed.bottom-3}
    ctx.font = label.font; ctx.textAlign = 'center'
    ctx.strokeStyle='rgba(0,0,5,.95)';ctx.lineWidth=3;ctx.strokeText(label.text,label.x,label.y)
    ctx.fillStyle = label.active ? 'rgba(232,239,255,.82)' : 'rgba(180,188,225,.25)'
    ctx.fillText(label.text, label.x, label.y)
  }
  if (debug && rootRef.value) rootRef.value.dataset.nebula = JSON.stringify({
    mode:`galaxy-${visual}`,visual,comparison:comparison.preset,frozen:comparison.frozen,totalEdges:graphData.value.edges.length,
    relationshipAudit:edgePlan.audit,drawnSourceIndices,focusedEdgeIndex:focusedEdgeIndex.value,curvedEdges:curves.size,
    snapshot: artifact.value?.snapshot_sha256_lf, algorithm:artifact.value?.parameters,
    derivedSubmitted, derivedTotal:artifact.value?.derived_edges?.length || 0, visibleNodes:nodes.length,
    galaxy:galaxy?.stats(),
    candidates: edgePlan.candidates, visibleDirect: edgePlan.visibleDirect,
    direct: selectedNode.value ? { dataDegree: edgePlan.dataDegree, typeFiltered: edgePlan.typeFilteredDirect, drawable: edgePlan.visibleDirect, submitted, intersecting: painted } : null,
    submitted, painted, selectedId: selectedNode.value?.id || null,
    panelsHidden: Boolean(props.panelsHidden), immersive: Boolean(props.immersive),
    overview, lastFit, fittedScale, savedView: Boolean(savedView.value), hoveredId: hoveredId.value,
    labels: { candidates: labels.length, drawn: labelIds.size }, search: { index: searchIndex.value, count: searchMatches.value.length },
    activeKinds: [...activeKinds.value], transform: { ...transform }, layoutMs, drawMs: performance.now() - start,
    selectedScreen:selectedNode.value?worldToScreen(nodeById.get(selectedNode.value.id)!.point):null,
  })
}

function nodeAt(x: number, y: number) {
  if(cameraRig.value&&spatialKnowledge){const id=spatialKnowledge.pick(x,y);return id?nodeById.get(id):undefined}
  const world = screenToWorld(x, y)
  const matchIds = searchMatchIds.value
  let closest:DrawNode|undefined, best=Infinity
  for(const node of drawNodes.value) {
    if(!visibleNode(node))continue
    const id=node.id
    const distance=Math.hypot(world.x-node.point.x,world.y-node.point.y)*transform.scale
    const radius=appearanceFor(node,selectedNode.value?.id===id,matchIds.has(id),hoveredId.value===id).radius
    if(distance<=radius+7 && (distance<best || (distance===best && id<(closest?.id || '')))) {closest=node;best=distance}
  }
  return closest
}
function highlightNode(node: GraphNode | null) {
  const selection = resolveSelection(node?.id, graphData.value.nodes, graphData.value.edges)
  selectedNode.value = selection.node; highlightIds.value = selection.ids
  connectionPage.value = 0;focusedEdgeIndex.value=null
}
function graphPanels() {
  const canvas = canvasRef.value
  if (!canvas || props.panelsHidden) return []
  const rect = canvas.getBoundingClientRect()
  return [...(rootRef.value?.querySelectorAll('.nebula-control, .nebula-detail') || [])].map(panel => {
    const box = panel.getBoundingClientRect()
    return { left: box.left - rect.left, right: box.right - rect.left, top: box.top - rect.top, bottom: box.bottom - rect.top }
  })
}
function graphArea() {
  const canvas = canvasRef.value
  return availableGraphArea({ width: canvas?.clientWidth || 0, height: canvas?.clientHeight || 0 }, graphPanels())
}
function fitPoints(points: Point[]) {
  const canvas = canvasRef.value
  if (!canvas) return
  const view = { width: canvas.clientWidth, height: canvas.clientHeight }
  const area = graphArea()
  Object.assign(transform, focusTransform(points, view, area))
  fittedScale = transform.scale
  const outside = points.filter(point => {
    const screen = toScreen(point, view, transform)
    return screen.x < area.left || screen.x > area.right || screen.y < area.top || screen.y > area.bottom
  }).length
  lastFit = { area, points: points.length, outside }
}
function fitGraph() {
  if(cameraRig.value){cameraRig.value.reset(graphArea());spatialDirty=true;return}
  fitPoints(drawNodes.value.filter(node => activeKinds.value.has(node.kind)).map(node => node.point))
}
function focusNeighborhood() {
  if (!selectedNode.value) return
  overview = false
  const neighborhood=drawNodes.value.filter(node=>highlightIds.value.has(node.id)&&activeKinds.value.has(node.kind))
  if(cameraRig.value&&spatialKnowledge){cameraRig.value.fit(neighborhood.map(n=>spatialKnowledge!.positions.get(n.id)!),graphArea());spatialDirty=true;return}
  fitPoints(neighborhood.map(node => node.point))
}
async function viewAllConnections() {
  const interactionStart=performance.now()
  if (!selectedNode.value) return
  if (!savedView.value) savedView.value = { transform: { ...transform }, fittedScale, overview }
  if(cameraRig.value&&!savedCamera)savedCamera=cameraRig.value.capture()
  await nextTick()
  focusNeighborhood(); draw()
  measureInteraction('all-connections',interactionStart)
}
async function inspectStar() {
  if(!cameraRig.value||!spatialKnowledge||!selectedNode.value)return
  if(!savedView.value)savedView.value={transform:{...transform},fittedScale,overview}
  if(!savedCamera)savedCamera=cameraRig.value.capture()
  overview=false
  await nextTick()
  cameraRig.value.fit([spatialKnowledge.positions.get(selectedNode.value.id)!],graphArea())
  draw()
}
function returnToView() {
  const interactionStart=performance.now()
  if (!savedView.value) return
  if(cameraRig.value&&savedCamera){cameraRig.value.restore(savedCamera);savedCamera=null}
  Object.assign(transform, savedView.value.transform)
  fittedScale = savedView.value.fittedScale; overview = savedView.value.overview
  savedView.value = null; lastFit = null
  draw()
  measureInteraction('return-view',interactionStart)
}
async function clearSelection() {
  selectedNode.value = null; highlightIds.value = new Set(); searchIndex.value = -1
  focusedEdgeIndex.value=null
  overview = false
  await nextTick()
  draw()
}
async function onCanvasClick(event: MouseEvent) {
  const interactionStart=performance.now()
  if (drag.moved) { drag.moved = false; return }
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  const node = nodeAt(event.clientX - rect.left, event.clientY - rect.top)
  searchIndex.value = -1; overview = false
  selectedNode.value = node || null
  highlightNode(node || null)
  await nextTick()
  draw()
  measureInteraction('node-click',interactionStart)
}
function onPointerDown(event: PointerEvent) {
  if(event.button!==0&&event.button!==2)return
  drag.active = true; drag.moved = false; drag.startX = event.clientX; drag.startY = event.clientY; drag.originX = transform.x; drag.originY = transform.y
  drag.lastX=event.clientX;drag.lastY=event.clientY;drag.button=event.button
  canvasRef.value?.focus?.({preventScroll:true})
  canvasRef.value?.setPointerCapture(event.pointerId)
}
function onPointerMove(event: PointerEvent) {
  if (!drag.active) {
    const rect = canvasRef.value?.getBoundingClientRect()
    if (!rect) return
    const id = nodeAt(event.clientX - rect.left, event.clientY - rect.top)?.id || null
    if (id !== hoveredId.value) { hoveredId.value = id; draw() }
    return
  }
  const dx = event.clientX - drag.startX; const dy = event.clientY - drag.startY
  drag.moved = drag.moved || Math.abs(dx) > 3 || Math.abs(dy) > 3
  if (drag.moved) overview = false
  if(cameraRig.value){if(!drag.moved)return;const dx=event.clientX-drag.lastX,dy=event.clientY-drag.lastY;drag.lastX=event.clientX;drag.lastY=event.clientY;if(drag.button===2)cameraRig.value.pan(dx,dy);else cameraRig.value.orbit(dx,dy);draw();return}
  transform.x = drag.originX + dx / transform.scale; transform.y = drag.originY + dy / transform.scale; draw()
}
function onPointerUp() { drag.active = false }
function onPointerLeave() { if(!drag.active&&hoveredId.value) { hoveredId.value = null; draw() } }
function zoomView(direction:1|-1) {
  const canvas=canvasRef.value,rect=canvas?.getBoundingClientRect()
  if(canvas&&rect)onWheel({clientX:rect.left+canvas.clientWidth/2,clientY:rect.top+canvas.clientHeight/2,deltaY:direction})
}
function onWheel(event: Pick<WheelEvent,'clientX'|'clientY'|'deltaY'>&Partial<WheelEvent>) {
  if(event.ctrlKey||event.metaKey||event.altKey)return
  event.preventDefault?.()
  const interactionStart=performance.now()
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  overview = false
  if(cameraRig.value){cameraRig.value.zoom(event.deltaY>0?1:-1);draw();measureInteraction('zoom',interactionStart);return}
  const before = screenToWorld(event.clientX - rect.left, event.clientY - rect.top)
  transform.scale = nextZoomScale(transform.scale, event.deltaY <= 0, fittedScale)
  const after = screenToWorld(event.clientX - rect.left, event.clientY - rect.top)
  transform.x += after.x - before.x; transform.y += after.y - before.y; draw()
  measureInteraction('zoom',interactionStart)
}
async function resetView() {
  selectedNode.value = null; highlightIds.value = new Set()
  searchIndex.value = -1; savedView.value = null
  savedCamera=null;cameraKeys.clear()
  overview = true; await nextTick(); fitGraph()
  draw()
}
function onSearchEnter(event: KeyboardEvent) {
  if (event.isComposing || event.keyCode === 229 || event.ctrlKey || event.altKey || event.metaKey || event.repeat) return
  event.preventDefault()
  if (!event.isComposing) stepSearch(event.shiftKey ? -1 : 1)
}
async function stepSearch(direction: 1 | -1) {
  const interactionStart=performance.now()
  if (loading.value) { ElMessage.info('图谱数据加载中'); return }
  if (!searchKeyword.value.trim()) { ElMessage.info('请输入岗位或技能'); return }
  searchIndex.value = nextSearchIndex(searchIndex.value, searchMatches.value.length, direction)
  const node = searchMatches.value[searchIndex.value]
  if (!node) { ElMessage.warning('没有匹配节点'); return }
  selectedNode.value = node; highlightNode(node)
  overview = false
  await nextTick()
  const area = graphArea()
  if(cameraRig.value&&spatialKnowledge){cameraRig.value.focus(spatialKnowledge.positions.get(node.id)!,area);draw();flushSpatial(0);measureInteraction('search-next',interactionStart);return}
  const point = worldToScreen(node.point)
  if (point.x < area.left + 20 || point.x > area.right - 20 || point.y < area.top + 20 || point.y > area.bottom - 20) {
    transform.x += ((area.left + area.right) / 2 - point.x) / transform.scale
    transform.y += ((area.top + area.bottom) / 2 - point.y) / transform.scale
  }
  draw()
  measureInteraction('search-next',interactionStart)
}
async function loadGraph() {
  const generation = ++loadGeneration
  loading.value = true
  try {
    const result = await loadHistoricalGraph()
    const data = result.graph
    if (generation !== loadGeneration) return
    artifact.value = result.artifact
    if(comparison.transform){Object.assign(transform,comparison.transform);overview=false;fittedScale=comparison.transform.scale}
    await buildLayout(data, generation)
    if (generation !== loadGeneration) return
    savedView.value = null;savedCamera=null; highlightNode(selectedNode.value)
    await nextTick()
    resizeCanvas()
    if (overview && !selectedNode.value) fitGraph()
  } catch(error) { if (generation === loadGeneration) {loadError.value=String(error);ElMessage.error('历史快照或版本校验失败')} }
  finally { if (generation === loadGeneration) { loading.value = false; draw() } }
}
// 快照只属于当前选中身份；同步失效，避免同一轮改选后展开误用旧快照。
watch(() => selectedNode.value?.id, () => { savedView.value = null;savedCamera=null }, { flush: 'sync' })
watch(activeKinds, async () => {
  searchIndex.value = -1
  if (selectedNode.value && !activeKinds.value.has(selectedNode.value.kind)) {
    selectedNode.value = null; highlightIds.value = new Set()
  }
  await nextTick()
  if (overview) fitGraph()
  draw()
}, { deep: true })
watch(() => props.panelsHidden, async () => { await nextTick(); draw() })
watch(searchKeyword, async () => { searchIndex.value = -1; await nextTick(); draw() })
watch(showDerived,draw)
watch(stellarPreset,draw)
function cameraKeydown(event:KeyboardEvent){
  if(!cameraRig.value)return
  const key=cameraKey(event,composing)
  if(!key){if(event.ctrlKey||event.metaKey||event.altKey||event.shiftKey)cameraKeys.clear();return}
  event.preventDefault()
  if(key==='r'){if(!event.repeat)resetView();return}
  cameraKeys.add(key);overview=false
}
function cameraKeyup(event:KeyboardEvent){cameraKeys.delete(event.key.toLowerCase())}
function clearCameraKeys(){cameraKeys.clear();drag.active=false}
function compositionStart(){composing=true;clearCameraKeys()}
function compositionEnd(){composing=false}
function flushSpatial(delta:number){
  const rig=cameraRig.value,knowledge=spatialKnowledge,canvas=canvasRef.value
  if(!rig||!knowledge||!canvas||!graphData.value.nodes.length)return
  if(cameraKeys.size){
    const speed=delta*300
    const dx=((cameraKeys.has('a')?1:0)-(cameraKeys.has('d')?1:0))*speed,dy=((cameraKeys.has('w')?1:0)-(cameraKeys.has('s')?1:0))*speed
    if(dx||dy)rig.pan(dx,dy)
    if(cameraKeys.has('q')||cameraKeys.has('e'))rig.rollBy(((cameraKeys.has('q')?1:0)-(cameraKeys.has('e')?1:0))*delta*1.2)
    spatialDirty=true
  }
  if(rig.update(delta))spatialDirty=true
  if(!spatialDirty)return
  spatialDirty=false
  Object.assign(transform,{scale:rig.scale})
  const focusedEdge=directEdges.value.find(e=>e.sourceIndex===focusedEdgeIndex.value)
  const result=knowledge.update(canvas,{activeKinds:activeKinds.value,selectedId:selectedNode.value?.id,focusIds:highlightIds.value,priority:new Set([...highlightIds.value,...searchMatchIds.value]),matches:searchMatchIds.value,hoveredId:hoveredId.value,focusedEdge,stellarPreset:stellarPreset.value||undefined,panels:graphPanels(),showDerived:showDerived.value,derived:showDerived.value?(artifact.value?.derived_edges||[]).map(e=>({...e,kind:'candidate_similarity'})):[]})
  relationAudit.value=result.audit
  relationSummary.value=selectedNode.value?`直接关系 ${result.audit.scope} · 类型隐藏 ${result.audit.typeHidden} · 提交 ${result.submitted} · 视锥候选 ${result.intersecting}。其他星体仍可选中。`:`未选择星体 · 历史关系隐藏 ${result.audit.interactionHidden} / ${graphData.value.edges.length} · 提交 0。单击任意星体显示直接关联。`
  derivedSummary.value=`派生相似：提交 ${result.derivedSubmitted} / 总量 ${artifact.value?.derived_edges?.length||0}（独立候选层）`
  levelSummary.value=`当前知识层 ${result.visibleNodes} / ${graphData.value.nodes.length}；展示深度不代表语义距离。`
  if(debug&&rootRef.value)rootRef.value.dataset.nebula=JSON.stringify({...result,mode:stellarMode?'galaxy-p24':'galaxy-p23-stars',visual:'p22',snapshot:artifact.value?.snapshot_sha256_lf,totalEdges:graphData.value.edges.length,relationshipAudit:result.audit,selectedId:selectedNode.value?.id||null,selectedScreen:selectedNode.value?knowledge.projected(selectedNode.value.id):null,focusedEdgeIndex:focusedEdgeIndex.value,camera:rig.capture(),galaxy:galaxy?.stats(),hoveredId:hoveredId.value,savedView:Boolean(savedView.value),activeKinds:[...activeKinds.value],search:{index:searchIndex.value,count:searchMatches.value.length},panelsHidden:Boolean(props.panelsHidden),immersive:Boolean(props.immersive),direct:selectedNode.value?{dataDegree:directEdges.value.length,typeFiltered:typeVisibleDirect.value,submitted:result.submitted,intersecting:result.intersecting}:null})
}
onMounted(async () => {
  starSprites=createStarSprites(colors)
  resizeObserver = new ResizeObserver(resizeCanvas); if (canvasWrapRef.value) resizeObserver.observe(canvasWrapRef.value)
  loadGraph()
  window.addEventListener('keydown',cameraKeydown);window.addEventListener('keyup',cameraKeyup);window.addEventListener('blur',clearCameraKeys);window.addEventListener('compositionstart',compositionStart);window.addEventListener('compositionend',compositionEnd);document.addEventListener('visibilitychange',clearCameraKeys)
  try {
    const {createGalaxyBackground}=await import('../graph/galaxy/background')
    if(disposed||!galaxyRef.value)return
    if(spatialMode){const {createSpatialKnowledge}=await import('../graph/galaxy/knowledge');if(disposed)return;cameraRig.value=(await import('../graph/galaxy/camera')).createGalaxyCamera();spatialKnowledge=createSpatialKnowledge(cameraRig.value,stellarMode);if(graphData.value.nodes.length)spatialKnowledge.setData(graphData.value.nodes,graphData.value.edges,artifact.value!.nodes)}
    galaxy=createGalaxyBackground(galaxyRef.value,()=>transform,()=>{webglError.value=true},{visual,frozen:comparison.frozen,diagnostics:debug,spatial:cameraRig.value&&spatialKnowledge?{rig:cameraRig.value,group:spatialKnowledge.group,frame:flushSpatial,pointLimit:spatialKnowledge.setPointLimit}:undefined})
    resizeCanvas()
    if(cameraRig.value)fitGraph()
    if(debug)statsTimer=setInterval(()=>{if(rootRef.value)rootRef.value.dataset.galaxyStats=JSON.stringify(galaxy?.stats())},500)
  } catch {webglError.value=true}
})
onUnmounted(() => { disposed=true;loadGeneration++;clearCameraKeys();if(statsTimer)clearInterval(statsTimer);resizeObserver?.disconnect();spatialKnowledge?.dispose();galaxy?.dispose();cameraRig.value?.dispose();starSprites?.clear();window.removeEventListener('keydown',cameraKeydown);window.removeEventListener('keyup',cameraKeyup);window.removeEventListener('blur',clearCameraKeys);window.removeEventListener('compositionstart',compositionStart);window.removeEventListener('compositionend',compositionEnd);document.removeEventListener('visibilitychange',clearCameraKeys) })
</script>

<style scoped>
.technical-info {margin-top:16px;border-top:1px solid rgba(105,106,189,.18);padding-top:12px}.technical-info summary,.detail-section summary{cursor:pointer}.technical-info select{max-width:100%;background:#15152d;color:#dbe2ff;border:1px solid #45456b;border-radius:5px;padding:4px;margin-top:6px}
.reference-mark {color:#ffd7a0}.layout-provenance{font-size:11px;color:#a4afcb;margin:8px 0 12px}.layout-provenance summary,.relation-audit summary{cursor:pointer}.layout-provenance p{line-height:1.6}
.connection-list .edge-focused{background:rgba(150,190,255,.12);border-radius:6px}.connection-list .edge-focus-button{font-size:10px;color:#dfedff;text-decoration:underline;margin:4px 0}.connection-list details{font-size:10px;color:#a4afcb}.connection-list summary{cursor:pointer}

.galaxy-background { position:absolute;inset:56px 0 0;width:100%;height:calc(100% - 56px);pointer-events:none; }
.snapshot-note {font-size:11px;line-height:1.6;color:#a4afcb;margin:6px 0 12px}
.fallback-link {display:block;color:#bcd9ff;font-size:12px;margin-bottom:16px}
.renderer-error {position:absolute;bottom:45px;left:280px;color:#ffd19b;z-index:5}
.nebula-state a {pointer-events:auto;color:#bcd9ff}
.connection-list {padding-left:22px;font-size:11px}.connection-list li{margin:8px 0}.connection-list button{background:none;border:0;color:#badcff;text-align:left;padding:0}.connection-list small{display:block;color:#99a8c8;overflow-wrap:anywhere}
.detail-section pre {white-space:pre-wrap;overflow-wrap:anywhere;font-size:10px}

.nebula-page { position: relative; width: 100%; height: calc(100vh - 126px); min-height: 620px; overflow: hidden; border: 1px solid #171733; border-radius: 3px; background: #050511; color: #dbe2ff; box-shadow: 0 18px 40px rgba(20, 16, 45, .12); }
.nebula-stars { position: absolute; inset: 0; opacity: .75; pointer-events: none; background: radial-gradient(circle at 50% 48%, rgba(48, 45, 116, .24), transparent 38%), radial-gradient(1px 1px at 11% 25%, #fff, transparent 70%), radial-gradient(1px 1px at 31% 64%, #8693e8, transparent 70%), radial-gradient(1px 1px at 74% 19%, #fff, transparent 70%), radial-gradient(1px 1px at 88% 57%, #7c8be4, transparent 70%), radial-gradient(1px 1px at 63% 82%, #fff, transparent 70%), radial-gradient(1px 1px at 21% 86%, #6d80d5, transparent 70%); }
.nebula-header { position: absolute; top: 0; left: 0; right: 0; z-index: 5; display: flex; align-items: center; justify-content: center; height: 56px; border-bottom: 1px solid rgba(76, 75, 139, .24); background: rgba(5, 5, 17, .76); }
.nebula-title { color: #4da6ff; font-size: 20px; font-weight: 700; letter-spacing: 2px; text-shadow: 0 0 14px rgba(77, 166, 255, .35); }
.nebula-title b { color: #7adf77; font-size: 18px; }
.nebula-meta { position: absolute; right: 22px; display: flex; align-items: center; gap: 10px; color: #777aa8; font-size: 11px; }
.nebula-meta i { width: 4px; height: 4px; border-radius: 50%; background: #4da6ff; }
.panel-glass { border: 1px solid rgba(105, 106, 189, .27); background: rgba(9, 9, 33, .83); border-radius: 14px; box-shadow: 0 10px 30px rgba(0, 0, 0, .28); backdrop-filter: blur(12px); }
.nebula-control { position: absolute; top: 68px; left: 16px; z-index: 6; width: 244px; max-height: calc(100% - 92px); overflow-y: auto; padding: 16px; scrollbar-width:none;-ms-overflow-style:none; }
.nebula-control::-webkit-scrollbar { display:none;width:0;height:0; }
.nebula-label { display: block; margin: 0 0 8px; color: #777aa8; font-size: 11px; letter-spacing: 1px; }
.nebula-search { display: flex; align-items: center; gap: 8px; height: 34px; padding: 0 10px; border: 1px solid rgba(88, 89, 163, .34); border-radius: 10px; background: rgba(19, 19, 53, .72); color: #7681d3; }
.nebula-search input { min-width: 0; flex: 1; border: 0; outline: 0; background: transparent; color: #dbe2ff; font-size: 12px; }
.nebula-search input::placeholder { color: #62668f; }
.nebula-search button, .detail-head button { border: 0; background: transparent; color: #7b80a9; font-size: 18px; }
.search-hint { margin: 6px 0 12px; color: #7b80a9; font-size: 10px; }
.nebula-search-nav { display: flex; align-items: center; justify-content: space-between; margin: -6px 0 12px; color: #a1a4c2; font-size: 10px; }
.nebula-search-nav button { width: 26px; height: 23px; border: 1px solid rgba(88, 89, 163, .34); border-radius: 6px; background: rgba(19, 19, 53, .72); color: #dbe2ff; cursor: pointer; }
.nebula-search-nav button:disabled { opacity: .35; cursor: default; }
.nebula-filters { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 20px; }
.nebula-filters button { display: inline-flex; align-items: center; gap: 6px; padding: 6px 9px; border: 1px solid rgba(93, 94, 172, .45); border-radius: 10px; background: rgba(30, 30, 74, .7); color: #d5dcff; font-size: 11px; }
.nebula-filters button.off { opacity: .35; }
.nebula-filters i { width: 8px; height: 8px; border-radius: 50%; }
.nebula-legend { display: grid; gap: 8px; padding-bottom: 12px; }
.nebula-legend span { display: flex; align-items: center; color: #a1a4c2; font-size: 11px; }
.nebula-legend i { display: inline-block; width: 10px; height: 10px; margin-right: 8px; border-radius: 50%; }
.nebula-legend .legend-job { border-radius:1px;transform:rotate(45deg);background: #4da6ff; box-shadow: 0 0 9px #4da6ff; }
.nebula-legend .legend-skill { height:3px;border-radius:0;background: #2ee66b; box-shadow: 0 0 9px #2ee66b; }
.nebula-legend .legend-industry { width:3px;margin-left:3px;margin-right:12px;border-radius:0;background: #c77dff; box-shadow: 0 0 9px #c77dff; }
.nebula-legend .legend-edge { width: 18px; height: 2px; border-radius: 0; background: #4da6ff; }
.nebula-legend .legend-edge.dashed { height: 0; border-top: 2px dashed #777aa8; }
.nebula-legend .legend-edge.scenario { height: 0; border-top: 1px dotted #c77dff; background: transparent; }
.nebula-tools { display: flex; gap: 8px; padding-top: 12px; border-top: 1px solid rgba(105, 106, 189, .18); }
.nebula-tools button { display: inline-flex; align-items: center; gap: 5px; padding: 5px 6px; border: 0; background: transparent; color: #8287b4; font-size: 10px; }
.nebula-tools button:hover { color: #fff; }
.nebula-canvas-wrap { position: absolute; inset: 56px 0 0; z-index: 1; }
.nebula-canvas-wrap canvas { display: block; width: 100%; height: 100%; cursor: grab;touch-action:none; }
.nebula-canvas-wrap canvas:active { cursor: grabbing; }
.nebula-state { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 9px; color: #7679a8; font-size: 13px; pointer-events: none; }
.nebula-detail { position: absolute; top: 68px; right: 16px; z-index: 6; width: min(360px, calc(100% - 32px)); max-height: calc(100% - 92px); overflow-y: auto; padding: 16px; scrollbar-width: none; }
.nebula-detail::-webkit-scrollbar { display: none; }
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
@media (max-width: 1000px) {
  .nebula-control { max-height: calc((100% - 104px) / 2); }
  .nebula-detail { top: auto; bottom: 12px; max-height: calc((100% - 104px) / 2); }
}
</style>
