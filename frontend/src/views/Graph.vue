<template>
  <div class="graph-page">
    <!-- 骨架屏 -->
    <div v-if="loading" class="sk-wrap">
      <div class="sk-bar"></div>
      <div class="sk-body"><div class="sk-canvas"></div><div class="sk-side"></div></div>
    </div>
    <template v-else>

    <!-- 顶部筛选控制区 -->
    <div class="top-bar">
      <div class="top-left">
        <div class="title-with-icon">
          <div class="title-ill">
            <svg width="42" height="42" viewBox="0 0 42 42" fill="none">
              <circle cx="21" cy="21" r="18" fill="#FDF5F0" stroke="#D98B6E" stroke-width="1.2"/>
              <circle cx="14" cy="15" r="4.5" fill="#B8A0D4" opacity="0.5"/>
              <circle cx="28" cy="13" r="3.5" fill="#D98B6E" opacity="0.5"/>
              <circle cx="21" cy="28" r="4" fill="#8BBFA0" opacity="0.5"/>
              <line x1="14" y1="15" x2="28" y2="13" stroke="#D98B6E" stroke-width="1" opacity="0.35"/>
              <line x1="14" y1="15" x2="21" y2="28" stroke="#8BBFA0" stroke-width="1" opacity="0.35"/>
              <line x1="28" y1="13" x2="21" y2="28" stroke="#B8A0D4" stroke-width="1" opacity="0.35"/>
            </svg>
          </div>
          <h1>全景能力图谱</h1>
        </div>
        <el-select v-model="focusJob" placeholder="聚焦岗位" size="small" style="width:170px" @change="onFilterChange">
          <el-option v-for="j in graphJobs" :key="j.value" :label="j.label" :value="j.value" />
        </el-select>
        <el-select v-model="layoutType" size="small" style="width:110px" @change="changeLayout">
          <el-option label="力导向布局" value="force" /><el-option label="环形布局" value="circular" /><el-option label="树形布局" value="dagre" />
        </el-select>
        <el-switch v-model="compareMode" active-text="双年对比" size="small" @change="onFilterChange" />
        <el-select v-model="yearA" size="small" style="width:80px" :disabled="!compareMode" @change="onFilterChange"><el-option v-for="y in graphYears" :key="y" :label="y" :value="y" /></el-select>
        <span v-if="compareMode" class="vs-text">vs</span>
        <el-select v-model="yearB" size="small" style="width:80px" :disabled="!compareMode" @change="onFilterChange"><el-option v-for="y in graphYears" :key="y" :label="y" :value="y" /></el-select>
      </div>
      <div class="top-right">
        <el-input v-model="searchSkill" placeholder="搜索技能节点" :prefix-icon="Search" size="small" clearable style="width:170px" @clear="clearSearch" @keyup.enter="focusNode" />
        <el-button class="btn-ghost-sm" size="small" @click="saveSnapshot"><el-icon><FolderChecked /></el-icon>保存快照</el-button>
        <div class="top-deco-ill">
          <svg width="120" height="36" viewBox="0 0 120 36" fill="none">
            <circle cx="16" cy="14" r="6" fill="#B8A0D4" opacity="0.2"/>
            <circle cx="32" cy="10" r="4.5" fill="#D98B6E" opacity="0.22"/>
            <circle cx="24" cy="26" r="5" fill="#8BBFA0" opacity="0.18"/>
            <line x1="16" y1="14" x2="32" y2="10" stroke="#D98B6E" stroke-width="0.6" opacity="0.2"/>
            <line x1="16" y1="14" x2="24" y2="26" stroke="#8BBFA0" stroke-width="0.6" opacity="0.2"/>
            <line x1="32" y1="10" x2="24" y2="26" stroke="#B8A0D4" stroke-width="0.6" opacity="0.2"/>
            <circle cx="54" cy="18" r="9" fill="#FDF5F0" stroke="#D98B6E" stroke-width="0.6"/>
            <circle cx="51" cy="16" r="1.2" fill="#777" opacity="0.3"/>
            <circle cx="57" cy="16" r="1.2" fill="#777" opacity="0.3"/>
            <path d="M52 20 Q54 22 56 20" stroke="#C09080" stroke-width="0.5" fill="none" opacity="0.4"/>
            <path d="M47 26 Q47 23 54 23 Q61 23 61 26 L62 34 Q62 36 54 36 Q46 36 46 34 Z" fill="#D98B6E" opacity="0.1"/>
            <path d="M49 29 L43 24" stroke="#F5D5C8" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="42" cy="23.5" r="1.5" fill="#F5D5C8"/>
            <circle cx="78" cy="12" r="4" fill="#B8A0D4" opacity="0.15"/>
            <circle cx="95" cy="8" r="3" fill="#D98B6E" opacity="0.18"/>
            <circle cx="88" cy="24" r="3.5" fill="#8BBFA0" opacity="0.15"/>
            <line x1="78" y1="12" x2="95" y2="8" stroke="#D98B6E" stroke-width="0.5" opacity="0.15"/>
            <line x1="78" y1="12" x2="88" y2="24" stroke="#8BBFA0" stroke-width="0.5" opacity="0.15"/>
          </svg>
        </div>
        <el-dropdown @command="exportAs">
          <el-button class="btn-coral-sm" size="small"><el-icon><Download /></el-icon>导出</el-button>
          <template #dropdown><el-dropdown-menu><el-dropdown-item command="png">导出 PNG</el-dropdown-item><el-dropdown-item command="svg">导出 SVG</el-dropdown-item><el-dropdown-item command="excel">导出 Excel</el-dropdown-item></el-dropdown-menu></template>
        </el-dropdown>
      </div>
    </div>

    <!-- 图例 -->
    <div class="legend-bar">
      <span v-for="lg in legends" :key="lg.key" class="lg-item" :class="{ hidden: hiddenKinds.includes(lg.key) }" @click="toggleLegend(lg.key)">
        <i :style="{ background: lg.color, borderStyle: lg.dashed ? 'dashed' : 'solid' }"></i>{{ lg.label }}
      </span>
    </div>

    <!-- 主体：图谱 + 侧面板 -->
    <div class="main-body">
      <section class="panel canvas-panel">
        <div ref="graphContainer" class="graph-canvas"></div>
        <div class="canvas-footer">
          <span>节点 {{ graphStats.totalNodes }} · 连线 {{ graphStats.totalEdges }}</span>
          <span v-if="graphStats.added" class="s-added">+{{ graphStats.added }} 新增</span>
          <span v-if="graphStats.removed" class="s-removed">-{{ graphStats.removed }} 淘汰</span>
          <span v-if="graphStats.changed" class="s-changed">~{{ graphStats.changed }} 变更</span>
        </div>
      </section>

      <!-- 右侧详情面板 -->
      <aside class="panel side-panel" v-if="selectedNodes.length">
        <template v-if="selectedNodes.length === 1">
          <div class="side-head">
            <span class="kind-tag" :class="selNode.kind">{{ kindLabel(selNode.kind) }}</span>
            <h2>{{ selNode.label }}</h2>
            <el-tag v-if="selNode.status === 'added'" type="success" size="small" effect="light">新增</el-tag>
            <el-tag v-else-if="selNode.status === 'removed'" type="info" size="small" effect="light">衰退</el-tag>
            <el-tag v-else-if="selNode.status === 'changed'" type="warning" size="small" effect="light">变更</el-tag>
          </div>
          <p class="side-desc">{{ selNode.desc || selNode.label + '相关岗位与技能关联' }}</p>
          <el-tabs v-model="sideTab" class="side-tabs">
            <el-tab-pane label="基础指标" name="metrics">
              <div class="metrics-grid">
                <div><span>关联岗位</span><b>{{ selNode.jobs || '—' }}</b></div>
                <div><span>需求热度</span><b>{{ selNode.size ? (selNode.size * 2) + '%' : '—' }}</b></div>
                <div><span>增速</span><b :class="(selNode.growth||'').startsWith('+') ? 'pos' : 'neg'">{{ selNode.growth || '—' }}</b></div>
                <div><span>技能等级</span><b>{{ selNode.level === 'basic' ? '基础' : selNode.level === 'advanced' ? '进阶' : '—' }}</b></div>
              </div>
            </el-tab-pane>
            <el-tab-pane label="岗位雷达" name="radar">
              <div ref="sideRadarRef" style="height:220px"></div>
            </el-tab-pane>
            <el-tab-pane label="学习路径" name="path">
              <div class="learn-path">
                <div class="lp-step" v-for="(p, i) in learnPath" :key="i"><div class="lp-num">{{ i+1 }}</div><div><strong>{{ p.title }}</strong><p>{{ p.desc }}</p></div></div>
              </div>
            </el-tab-pane>
            <el-tab-pane label="替代技能" name="replace">
              <div class="replace-list">
                <div class="rp-item" v-for="r in replacements" :key="r.name"><span>{{ r.name }}</span><el-tag size="small" :type="r.type" effect="plain">{{ r.reason }}</el-tag></div>
              </div>
            </el-tab-pane>
          </el-tabs>
          <div class="side-actions">
            <el-button class="btn-coral-sm" size="small" @click="$router.push('/learning')">学习路径</el-button>
            <el-button class="btn-ghost-sm" size="small" @click="$router.push('/jobs')">查看岗位</el-button>
          </div>
        </template>
        <template v-else>
          <div class="side-head">
            <h2>多节点对比</h2>
            <el-tag effect="light" size="small">已选 {{ selectedNodes.length }} 个</el-tag>
          </div>
          <div class="compare-list">
            <div v-for="n in selectedNodes" :key="n.id" class="cmp-item">
              <span class="cmp-dot" :style="{ background: n.color }"></span>
              <span>{{ n.label }}</span>
              <span class="cmp-val">{{ n.growth || '—' }}</span>
            </div>
          </div>
          <div ref="sideRadarRef" style="height:240px"></div>
          <div class="side-actions">
            <el-button class="btn-coral-sm" size="small" @click="$router.push('/learning')">批量学习</el-button>
            <el-button class="btn-ghost-sm" size="small" @click="selectedNodes = []">清空选择</el-button>
          </div>
        </template>
      </aside>
    </div>

    </template>
  </div>
</template>
<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Download, FolderChecked } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { Graph } from '@antv/g6'
import * as echarts from 'echarts'
import { graphJobs, graphYears, graphSnapshots, skillRadar8D } from '../data/mock'

const router = useRouter()
const loading = ref(true)
const focusJob = ref('all')
const layoutType = ref('force')
const compareMode = ref(false)
const yearA = ref('2026')
const yearB = ref('2024')
const searchSkill = ref('')
const hoverLegend = ref('')
const hiddenKinds = ref<string[]>([])
const selectedNodes = ref<any[]>([])
const sideTab = ref('metrics')
const graphStats = reactive({ totalNodes: 0, totalEdges: 0, added: 0, removed: 0, changed: 0 })

const graphContainer = ref<HTMLElement | null>(null)
const sideRadarRef = ref<HTMLElement | null>(null)
let graph: Graph | null = null
let sideRadar: echarts.ECharts | null = null

const currentYear = computed(() => compareMode.value ? yearA.value : '2026')
const currentData = computed(() => {
  const snap = graphSnapshots[currentYear.value] || graphSnapshots['2026']
  let nodes = snap.nodes.filter((n: any) => !hiddenKinds.value.includes(n.kind))
  let edges = snap.edges.filter((e: any) => {
    const sn = nodes.find((n: any) => n.id === e.source)
    const tn = nodes.find((n: any) => n.id === e.target)
    return sn && tn
  })
  if (focusJob.value !== 'all') {
    const jobNode = nodes.find((n: any) => n.kind === 'job' && n.label.includes(focusJobLabel.value))
    if (jobNode) {
      const related = new Set<string>()
      related.add(jobNode.id)
      edges.forEach((e: any) => { if (e.source === jobNode.id) related.add(e.target); if (e.target === jobNode.id) related.add(e.source) })
      nodes = nodes.filter((n: any) => related.has(n.id) || n.kind === 'industry')
      edges = edges.filter((e: any) => related.has(e.source) && related.has(e.target))
    }
  }
  return { nodes, edges }
})
const focusJobLabel = computed(() => (graphJobs as any[]).find(j => j.value === focusJob.value)?.label || '')
const selNode = computed(() => selectedNodes.value[0] || {})

// Morandi color palette for legends
const legends = [
  { key: 'industry', label: '行业赛道', color: '#B8A0D4' },
  { key: 'job', label: '岗位', color: '#D98B6E' },
  { key: 'skill-added', label: '新增技能', color: '#8BBFA0' },
  { key: 'skill-changed', label: '变更技能', color: '#D4C088' },
  { key: 'skill-stable', label: '稳定技能', color: '#8CA0B8' },
  { key: 'skill-removed', label: '淘汰技能', color: '#C0A0A0', dashed: true }
]

// Morandi node color map
const nodeColorMap: Record<string, string> = {
  industry: '#B8A0D4',
  job: '#D98B6E',
  'skill-added': '#8BBFA0',
  'skill-changed': '#D4C088',
  'skill-stable': '#8CA0B8',
  'skill-removed': '#C0A0A0'
}

function getNodeColor(n: any): string {
  if (n.kind === 'industry') return nodeColorMap.industry
  if (n.kind === 'job') return nodeColorMap.job
  if (n.status === 'added') return nodeColorMap['skill-added']
  if (n.status === 'changed') return nodeColorMap['skill-changed']
  if (n.status === 'removed') return nodeColorMap['skill-removed']
  return nodeColorMap['skill-stable']
}

const learnPath = computed(() => {
  const name = selNode.value.label || ''
  if (name.includes('Vue') || name.includes('React') || name.includes('前端')) return [
    { title: 'JavaScript 基础夯实', desc: 'ES6+语法、异步编程、模块化' },
    { title: '框架核心原理', desc: name + '响应式系统、虚拟DOM、编译优化' },
    { title: '工程化实战', desc: 'Vite构建、TypeScript、CI/CD集成' },
    { title: '性能优化项目', desc: '首屏优化、代码分割、缓存策略' }
  ]
  if (name.includes('Python') || name.includes('算法') || name.includes('AI') || name.includes('大模型') || name.includes('RAG') || name.includes('Agent')) return [
    { title: 'Python 进阶', desc: '数据结构、并发编程、类型注解' },
    { title: '机器学习基础', desc: '经典算法、特征工程、模型评估' },
    { title: '深度学习实战', desc: 'PyTorch框架、模型训练与调优' },
    { title: '大模型应用', desc: name + '微调、RAG系统、Agent框架' }
  ]
  return [
    { title: '基础知识学习', desc: name + '核心概念与原理' },
    { title: '进阶技能提升', desc: '实战项目与最佳实践' },
    { title: '高级应用拓展', desc: '架构设计与性能优化' }
  ]
})

const replacements = computed(() => {
  const name = selNode.value.label || ''
  const map: Record<string, any[]> = {
    'Vue2': [{ name: 'Vue3', type: 'success', reason: '推荐升级' }, { name: 'React', type: '', reason: '替代方案' }],
    'jQuery': [{ name: 'Vue3', type: 'success', reason: '现代替代' }, { name: '原生JS', type: '', reason: '轻量替代' }],
    'TensorFlow': [{ name: 'PyTorch', type: 'success', reason: '主流替代' }, { name: 'JAX', type: '', reason: '新兴方案' }],
    'TypeScript': [{ name: 'JavaScript', type: 'info', reason: '降级方案' }],
    'Vue3': [{ name: 'React', type: '', reason: '替代方案' }, { name: 'Svelte', type: '', reason: '新兴方案' }]
  }
  return map[name] || [{ name: '暂无替代', type: 'info', reason: '核心技能' }]
})

function kindLabel(k: string) { return { industry: '行业赛道', job: '岗位', skill: '技能' }[k] || k }
function toggleLegend(key: string) {
  const skillKey = key.startsWith('skill-') ? 'skill' : key
  const i = hiddenKinds.value.indexOf(skillKey)
  i >= 0 ? hiddenKinds.value.splice(i, 1) : hiddenKinds.value.push(skillKey)
  graph?.destroy(); nextTick(initGraph)
}

async function initGraph() {
  if (!graphContainer.value) return
  const data = currentData.value
  const w = graphContainer.value.clientWidth
  const h = graphContainer.value.clientHeight || 520

  graph = new Graph({
    container: graphContainer.value,
    width: w,
    height: h,
    data: {
      nodes: data.nodes.map((n: any) => ({
        id: n.id,
        style: {
          size: n.kind === 'industry' ? 40 : n.kind === 'job' ? 28 : 20,
          fill: getNodeColor(n),
          stroke: getNodeColor(n) + '60',
          lineWidth: 1.5,
          opacity: n.status === 'removed' ? 0.5 : 1,
          labelText: n.label,
          labelFontSize: n.kind === 'industry' ? 12 : n.kind === 'job' ? 10 : 9,
          labelFill: '#555559',
          labelFontWeight: n.kind === 'industry' ? 'bold' : 'normal',
          cursor: 'pointer',
          ...(n.status === 'removed' ? { lineDash: [4, 4] } : {})
        },
        data: n
      })),
      edges: data.edges.map((e: any) => ({
        id: e.source + '-' + e.target,
        source: e.source,
        target: e.target,
        style: {
          stroke: e.kind === 'industry-job' ? '#D98B6E40' : '#B8C4D060',
          lineWidth: e.kind === 'industry-job' ? 1.8 : 1,
          lineDash: e.kind === 'industry-job' ? [] : [5, 4],
          endArrow: { path: 'M 0,0 L 5,2.5 L 5,-2.5 Z', fill: '#C0B0A0' },
          cursor: 'pointer'
        }
      }))
    },
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', 'click-select'],
    layout: getLayoutConfig()
  })

  graph.on('node:click', (evt: any) => {
    const nd = evt.target?.data?.data || evt.target?.data || {}
    if (!nd.id) return
    if (evt.nativeEvent?.shiftKey) {
      const idx = selectedNodes.value.findIndex((n: any) => n.id === nd.id)
      idx >= 0 ? selectedNodes.value.splice(idx, 1) : selectedNodes.value.push(nd)
    } else {
      selectedNodes.value = [nd]
    }
    nextTick(updateSideRadar)
  })

  graph.on('node:dblclick', (evt: any) => {
    const nd = evt.target?.data?.data || evt.target?.data || {}
    if (nd.kind === 'skill') router.push({ path: '/jobs', query: { skill: nd.label } })
  })

  await graph.render()
  try { await graph.fitView(20) } catch (e) { /* ignore */ }
  graphStats.totalNodes = data.nodes.length
  graphStats.totalEdges = data.edges.length
  graphStats.added = data.stats?.added || 0
  graphStats.removed = data.stats?.removed || 0
  graphStats.changed = data.stats?.changed || 0
}

function getLayoutConfig() {
  if (layoutType.value === 'circular') return { type: 'circular', radius: 200 }
  if (layoutType.value === 'dagre') return { type: 'dagre', rankdir: 'TB', nodesep: 30, ranksep: 60 }
  return { type: 'force', preventOverlap: true, nodeSize: 30, linkDistance: 120 }
}

async function changeLayout() { graph?.destroy(); await nextTick(); await initGraph() }
async function onFilterChange() { graph?.destroy(); await nextTick(); await initGraph() }
async function focusNode() {
  if (!searchSkill.value || !graph) return
  const data = currentData.value
  const target = data.nodes.find((n: any) => n.label.toLowerCase().includes(searchSkill.value.toLowerCase()))
  if (target) {
    try { await graph.focusElement(target.id) } catch (e) { /* fallback */ }
    selectedNodes.value = [target]
    nextTick(updateSideRadar)
    ElMessage.success('已定位: ' + target.label)
  } else { ElMessage.warning('未找到匹配节点') }
}
function clearSearch() { searchSkill.value = '' }
function saveSnapshot() { ElMessage.success('布局快照已保存') }
function exportAs(cmd: string) {
  if (cmd === 'png' && graph) {
    const canvas = graphContainer.value?.querySelector('canvas')
    if (canvas) { const a = document.createElement('a'); a.href = canvas.toDataURL('image/png'); a.download = '能力图谱.png'; a.click() }
    ElMessage.success('PNG 已导出')
  } else if (cmd === 'svg') { ElMessage.success('SVG 已导出') }
  else if (cmd === 'excel') { ElMessage.success('Excel 已导出') }
}

function updateSideRadar() {
  if (!sideRadarRef.value) return
  if (sideRadar) sideRadar.dispose()
  sideRadar = echarts.init(sideRadarRef.value)
  const dims = skillRadar8D.dimensions
  const nodes = selectedNodes.value.filter((n: any) => n.kind === 'skill')
  if (!nodes.length) {
    sideRadar.setOption({ radar: { indicator: dims.map(d => ({ name: d, max: 100 })), shape: 'polygon' }, series: [{ type: 'radar', data: [] }] })
    return
  }
  const colors = ['#D98B6E', '#8BBFA0', '#D4C088', '#B8A0D4', '#8CA0B8']
  sideRadar.setOption({
    tooltip: {}, legend: { data: nodes.map(n => n.label), bottom: 0, textStyle: { fontSize: 10 } },
    radar: { indicator: dims.map(d => ({ name: d, max: 100 })), shape: 'polygon', splitNumber: 4, axisName: { color: '#77777E', fontSize: 9 } },
    series: [{
      type: 'radar',
      data: nodes.map((n: any, i: number) => ({
        name: n.label,
        value: (skillRadar8D.data as any)[n.label] || dims.map(() => Math.round(Math.random() * 60 + 30)),
        lineStyle: { color: colors[i % colors.length], width: 2 },
        itemStyle: { color: colors[i % colors.length] },
        areaStyle: { color: colors[i % colors.length] + '20' }
      }))
    }]
  })
}

function handleResize() { graph?.resize(); sideRadar?.resize() }

onMounted(async () => {
  setTimeout(async () => { loading.value = false; await nextTick(); await initGraph() }, 400)
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => { window.removeEventListener('resize', handleResize); graph?.destroy(); sideRadar?.dispose() })
</script>
<style scoped>
.graph-page {
  max-width: 1440px;
  margin: auto;
  position: relative;
}

/* 骨架屏 */
.sk-wrap { padding: 20px 0; }
.sk-bar { height: 48px; background: linear-gradient(90deg, #F5F0EA 25%, #EDE5DC 50%, #F5F0EA 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 16px; margin-bottom: 16px; }
.sk-body { display: grid; grid-template-columns: 1fr 280px; gap: 18px; }
.sk-canvas { height: 520px; background: linear-gradient(90deg, #F5F0EA 25%, #EDE5DC 50%, #F5F0EA 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 16px; }
.sk-side { height: 520px; background: linear-gradient(90deg, #F5F0EA 25%, #EDE5DC 50%, #F5F0EA 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 16px; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

/* 顶部栏 */
.top-bar {
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 10px; margin-bottom: 14px;
  padding: 14px 18px; background: #fff;
  border: none; border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.top-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.title-with-icon { display: flex; align-items: center; gap: 10px; margin-right: 6px; }
.title-with-icon h1 { font-size: 20px; font-weight: 600; color: #333338; margin: 0; white-space: nowrap; }
.top-right { display: flex; align-items: center; gap: 8px; }
.vs-text { color: #77777E; font-size: 12px; }

/* 按钮 */
.btn-ghost-sm {
  background: #FDFBF7; border: 1px solid #E8DDD4; color: #77777E;
  border-radius: 20px; font-size: 12px;
}
.btn-ghost-sm:hover { background: #F5EDE5; border-color: #D9CFC6; color: #555559; }
.btn-coral-sm {
  background: #D98B6E; border: none; color: #fff;
  border-radius: 20px; font-size: 12px;
  box-shadow: 0 2px 8px rgba(217,139,110,0.2);
}
.btn-coral-sm:hover { background: #C87A5E; }

/* 顶部装饰插画 */
.top-deco-ill { display: flex; align-items: center; flex-shrink: 0; opacity: 0.85; }
.legend-bar { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.lg-item { display: flex; align-items: center; gap: 5px; font-size: 12px; color: #77777E; cursor: pointer; transition: opacity 0.2s; user-select: none; }
.lg-item.hidden { opacity: 0.35; text-decoration: line-through; }
.lg-item i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; border: 2px solid transparent; }
.lg-item:hover { color: #D98B6E; }

/* 主体 */
.main-body { display: grid; grid-template-columns: 1fr 300px; gap: 16px; margin-bottom: 19px; }
.panel {
  background: #fff; border: none; border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.canvas-panel { padding: 18px; overflow: hidden; }
.graph-canvas { width: 100%; height: 520px; border-radius: 12px; background: #fff; }
.canvas-footer { display: flex; gap: 14px; margin-top: 10px; font-size: 12px; color: #77777E; }
.s-added { color: #8BBFA0; }
.s-removed { color: #C0A0A0; }
.s-changed { color: #D4C088; }

/* 侧面板 */
.side-panel { padding: 20px; overflow-y: auto; max-height: 620px; }
.side-head { margin-bottom: 14px; }
.side-head h2 { margin: 8px 0 6px; font-size: 17px; color: #333338; font-weight: 600; }
.kind-tag { font-size: 11px; padding: 3px 10px; border-radius: 8px; color: #fff; font-weight: 500; }
.kind-tag.industry { background: #B8A0D4; }
.kind-tag.job { background: #D98B6E; }
.kind-tag.skill { background: #8BBFA0; }
.side-desc { font-size: 13px; color: #77777E; line-height: 1.6; margin-bottom: 14px; }
.side-tabs { margin-bottom: 12px; }
.metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.metrics-grid div { background: #FDFBF7; padding: 12px; border-radius: 12px; text-align: center; }
.metrics-grid span { font-size: 11px; color: #77777E; display: block; margin-bottom: 4px; }
.metrics-grid b { font-size: 16px; color: #333338; }
.pos { color: #8BBFA0 !important; }
.neg { color: #C0A0A0 !important; }
.side-actions { display: flex; gap: 8px; margin-top: 14px; }

/* 学习路径 */
.learn-path { display: flex; flex-direction: column; gap: 12px; }
.lp-step { display: flex; gap: 10px; align-items: flex-start; }
.lp-num { width: 24px; height: 24px; border-radius: 50%; background: #D98B6E; color: #fff; display: grid; place-items: center; font-size: 11px; font-weight: 700; flex-shrink: 0; }
.lp-step strong { font-size: 13px; color: #333338; display: block; }
.lp-step p { font-size: 11px; color: #77777E; margin: 2px 0 0; }

/* 替代技能 */
.replace-list { display: flex; flex-direction: column; gap: 8px; }
.rp-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #FDFBF7; border-radius: 12px; }
.rp-item span:first-child { font-size: 13px; font-weight: 500; color: #555559; }

/* 多节点对比 */
.compare-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.cmp-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: #FDFBF7; border-radius: 10px; font-size: 13px; color: #555559; }
.cmp-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.cmp-val { margin-left: auto; font-weight: 600; color: #D98B6E; }

@media (max-width: 1050px) { .main-body { grid-template-columns: 1fr; } .side-panel { max-height: none; } }
@media (max-width: 760px) { .top-deco-ill { display: none; } }
</style>