<template>
  <div class="graph-panorama">
    <!-- 顶部控制栏 -->
    <div class="control-bar">
      <div class="control-left">
        <h3>新一代信息技术岗位全景图谱</h3>
        <el-tag type="info" size="small">技能点级别</el-tag>
      </div>
      <div class="control-right">
        <!-- 视图切换 -->
        <div class="view-switcher">
          <el-radio-group v-model="currentView" size="small">
            <el-radio-button value="force">力导向图</el-radio-button>
            <el-radio-button value="tree">树状图</el-radio-button>
            <el-radio-button value="radial">环形图</el-radio-button>
            <el-radio-button value="sankey">桑基图</el-radio-button>
            <el-radio-button value="nebula">星云图</el-radio-button>
          </el-radio-group>
        </div>
        
        <!-- 筛选器 -->
        <div class="filters">
          <el-select v-model="selectedTrack" placeholder="技术栈" clearable size="small" style="width: 120px">
            <el-option v-for="t in trackOptions" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
          <el-select v-model="selectedLevel" placeholder="级别" clearable size="small" style="width: 100px">
            <el-option label="初级" value="junior" />
            <el-option label="中级" value="middle" />
            <el-option label="高级" value="senior" />
            <el-option label="专家" value="expert" />
          </el-select>
        </div>
        
        <!-- 操作按钮 -->
        <el-button size="small" class="btn-ghost" @click="refreshGraph">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button size="small" class="btn-ghost" @click="exportGraph">
          <el-icon><Download /></el-icon>导出
        </el-button>
      </div>
    </div>

    <!-- 图谱主体 -->
    <div class="graph-container">
      <!-- 力导向图 -->
      <div v-show="currentView === 'force'" ref="forceRef" class="graph-canvas"></div>
      
      <!-- 树状图 -->
      <div v-show="currentView === 'tree'" ref="treeRef" class="graph-canvas"></div>
      
      <!-- 环形图 -->
      <div v-show="currentView === 'radial'" ref="radialRef" class="graph-canvas"></div>
      
      <!-- 桑基图 -->
      <div v-show="currentView === 'sankey'" ref="sankeyRef" class="graph-canvas"></div>
      
      <!-- 星云图 -->
      <div v-show="currentView === 'nebula'" ref="nebulaRef" class="graph-canvas nebula-canvas">
        <canvas ref="nebulaCanvas" class="nebula-canvas-element"></canvas>
        <div class="nebula-controls">
          <el-button size="small" @click="resetNebulaView">重置视图</el-button>
          <el-button size="small" @click="toggleNebulaLabels">切换标签</el-button>
        </div>
      </div>
      
      <!-- 图例 -->
      <div class="graph-legend">
        <div class="legend-title">图例</div>
        <div class="legend-items">
          <div v-for="item in legendItems" :key="item.label" class="legend-item">
            <span class="legend-dot" :style="{ background: item.color }"></span>
            <span class="legend-label">{{ item.label }}</span>
          </div>
        </div>
      </div>
      
      <!-- 节点详情面板 -->
      <div v-if="selectedNode" class="node-detail">
        <div class="detail-header">
          <h4>{{ selectedNode.label }}</h4>
          <el-button text @click="selectedNode = null">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
        <div class="detail-body">
          <div class="detail-row">
            <span class="detail-label">类型</span>
            <el-tag :type="getNodeTypeTag(selectedNode.kind)" size="small">
              {{ getNodeTypeLabel(selectedNode.kind) }}
            </el-tag>
          </div>
          <div v-if="selectedNode.kind === 'skill'" class="detail-row">
            <span class="detail-label">需求量</span>
            <span class="detail-value">{{ selectedNode.jobs || 0 }} 个岗位</span>
          </div>
          <div v-if="selectedNode.kind === 'skill'" class="detail-row">
            <span class="detail-label">增长趋势</span>
            <span class="detail-value" :class="selectedNode.growth && selectedNode.growth.startsWith('+') ? 'up' : 'down'">
              {{ selectedNode.growth || '稳定' }}
            </span>
          </div>
          <div v-if="selectedNode.status" class="detail-row">
            <span class="detail-label">状态</span>
            <el-tag :type="selectedNode.status === 'stable' ? 'success' : selectedNode.status === 'growing' ? 'warning' : 'danger'" size="small">
              {{ selectedNode.status === 'stable' ? '稳定' : selectedNode.status === 'growing' ? '增长' : '下降' }}
            </el-tag>
          </div>
          <div class="detail-row">
            <span class="detail-label">关联数</span>
            <span class="detail-value">{{ getNodeLinks(selectedNode.id) }} 个</span>
          </div>
        </div>
        <div class="detail-actions">
          <el-button size="small" type="primary" @click="highlightRelated(selectedNode.id)">
            高亮关联
          </el-button>
          <el-button size="small" @click="focusNode(selectedNode.id)">
            聚焦节点
          </el-button>
        </div>
      </div>
    </div>

    <!-- 底部统计 -->
    <div class="graph-stats">
      <div class="stat-item">
        <span class="stat-label">总节点数</span>
        <span class="stat-value">{{ graphStats.totalNodes }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">总边数</span>
        <span class="stat-value">{{ graphStats.totalEdges }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">新增节点</span>
        <span class="stat-value up">+{{ graphStats.added }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">移除节点</span>
        <span class="stat-value down">-{{ graphStats.removed }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">变更节点</span>
        <span class="stat-value">{{ graphStats.changed }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { Refresh, Download, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getGraphData } from '../api/graph'
import * as echarts from 'echarts'
import { computeNebulaLayout, DEFAULT_NEBULA_CONFIG } from '@/utils/algorithms/nebula-layout'

// 类型定义
interface GraphNode {
  id: string
  label: string
  kind: 'industry' | 'job' | 'skill'
  size: number
  color: string
  parent?: string
  status?: string
  jobs?: number
  growth?: string
}

interface GraphEdge {
  source: string
  target: string
  kind: string
}

interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: {
    totalNodes: number
    totalEdges: number
    added: number
    removed: number
    changed: number
  }
}

// 状态
const currentView = ref<'force' | 'tree' | 'radial' | 'sankey' | 'nebula'>('force')
const selectedTrack = ref('')
const selectedLevel = ref('')
const selectedNode = ref<GraphNode | null>(null)

// 图表引用
const forceRef = ref<HTMLElement>()
const treeRef = ref<HTMLElement>()
const radialRef = ref<HTMLElement>()
const sankeyRef = ref<HTMLElement>()
const nebulaRef = ref<HTMLElement>()
const nebulaCanvas = ref<HTMLCanvasElement>()

// 图表实例
let forceChart: echarts.ECharts | null = null
let treeChart: echarts.ECharts | null = null
let radialChart: echarts.ECharts | null = null
let sankeyChart: echarts.ECharts | null = null

// 星云图相关
let nebulaCtx: CanvasRenderingContext2D | null = null
let nebulaLayout: Record<string, { x: number; y: number }> = {}
let nebulaZoom = 1
let nebulaOffsetX = 0
let nebulaOffsetY = 0
let showNebulaLabels = true

// 图谱数据
const graphData = ref<GraphData>({
  nodes: [],
  edges: [],
  stats: { totalNodes: 0, totalEdges: 0, added: 0, removed: 0, changed: 0 }
})

const graphStats = ref({ totalNodes: 0, totalEdges: 0, added: 0, removed: 0, changed: 0 })

// 图例
const legendItems = [
  { label: '行业', color: '#7c5cff' },
  { label: '岗位', color: '#E07B6D' },
  { label: '技能', color: '#8CA0B8' }
]

// 技术栈选项
const trackOptions = [
  { value: 'ai', label: '人工智能' },
  { value: 'bigdata', label: '大数据' },
  { value: 'cloud', label: '云计算' },
  { value: 'iot', label: '物联网' },
  { value: 'security', label: '网络安全' },
  { value: 'dev', label: '软件开发' }
]

// 加载图谱数据
async function loadGraphData() {
  try {
    const data = await getGraphData()
    graphData.value = data
    graphStats.value = data.stats
  } catch (error) {
    console.error('加载图谱数据失败:', error)
    ElMessage.error('加载图谱数据失败')
  }
}

// 初始化力导向图
function initForceChart() {
  if (!forceRef.value) return
  
  forceChart = echarts.init(forceRef.value)
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: function(params: any) {
        if (params.dataType === 'node') {
          var node = params.data
          var html = '<div style="font-weight: 600; margin-bottom: 8px;">' + node.label + '</div>'
          html += '<div>类型：' + getNodeTypeLabel(node.kind) + '</div>'
          if (node.jobs) html += '<div>需求量：' + node.jobs + ' 个岗位</div>'
          if (node.growth) html += '<div>增长趋势：' + node.growth + '</div>'
          return html
        }
        return ''
      }
    },
    series: [{
      type: 'graph',
      layout: 'force',
      data: graphData.value.nodes.map(function(n) {
        return Object.assign({}, n, {
          symbolSize: n.size,
          itemStyle: { color: n.color }
        })
      }),
      links: graphData.value.edges.map(function(e) {
        return {
          source: e.source,
          target: e.target,
          lineStyle: { color: '#E8DDD4', width: 1 }
        }
      }),
      categories: [
        { name: '行业', itemStyle: { color: '#7c5cff' } },
        { name: '岗位', itemStyle: { color: '#E07B6D' } },
        { name: '技能', itemStyle: { color: '#8CA0B8' } }
      ],
      roam: true,
      draggable: true,
      force: {
        repulsion: 200,
        gravity: 0.1,
        edgeLength: 150
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 3 }
      },
      label: {
        show: true,
        position: 'right',
        fontSize: 12
      }
    }]
  }
  
  forceChart.setOption(option)
  
  // 点击事件
  forceChart.on('click', function(params: any) {
    if (params.dataType === 'node') {
      selectedNode.value = params.data
    }
  })
}

// 初始化树状图
function initTreeChart() {
  if (!treeRef.value) return
  
  treeChart = echarts.init(treeRef.value)
  
  // 构建树结构
  var treeData = buildTreeData()
  
  var option = {
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove'
    },
    series: [{
      type: 'tree',
      data: [treeData],
      top: '5%',
      left: '10%',
      bottom: '5%',
      right: '20%',
      symbolSize: 12,
      orient: 'LR',
      label: {
        position: 'left',
        verticalAlign: 'middle',
        align: 'right',
        fontSize: 12
      },
      leaves: {
        label: {
          position: 'right',
          verticalAlign: 'middle',
          align: 'left'
        }
      },
      expandAndCollapse: true,
      animationDuration: 550,
      animationDurationUpdate: 750
    }]
  }
  
  treeChart.setOption(option)
}

// 初始化环形图
function initRadialChart() {
  if (!radialRef.value) return

  radialChart = echarts.init(radialRef.value)

  const industries = graphData.value.nodes.filter(function(n) { return n.kind === 'industry' })
  const jobs = graphData.value.nodes.filter(function(n) { return n.kind === 'job' })
  const skills = graphData.value.nodes.filter(function(n) { return n.kind === 'skill' })
  const slices = industries.length
    ? industries.map(function(n) {
        return {
          value: jobs.filter(function(job) { return job.parent === n.id }).length,
          name: n.label,
          itemStyle: { color: n.color }
        }
      })
    : [
        { value: jobs.length, name: '岗位', itemStyle: { color: '#D98B6E' } },
        { value: skills.length, name: '技能', itemStyle: { color: '#8CA0B8' } }
      ]

  radialChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      data: slices.map(function(n) { return n.name })
    },
    series: [{
      name: industries.length ? '岗位分布' : '图谱节点分布',
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 10,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: false,
        position: 'center'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 20,
          fontWeight: 'bold'
        }
      },
      labelLine: {
        show: false
      },
      data: slices
    }]
  })
}

// 初始化桑基图
function initSankeyChart() {
  if (!sankeyRef.value) return
  
  sankeyChart = echarts.init(sankeyRef.value)
  
  // 构建桑基图数据
  var sankeyNodes = graphData.value.nodes.map(function(n) {
    return {
      name: n.label,
      itemStyle: { color: n.color }
    }
  })
  
  var sankeyLinks = graphData.value.edges.map(function(e) {
    var source = graphData.value.nodes.find(function(n) { return n.id === e.source })
    var target = graphData.value.nodes.find(function(n) { return n.id === e.target })
    return {
      source: source ? source.label : e.source,
      target: target ? target.label : e.target,
      value: 1
    }
  })
  
  var option = {
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove'
    },
    series: [{
      type: 'sankey',
      layout: 'none',
      emphasis: {
        focus: 'adjacency'
      },
      data: sankeyNodes,
      links: sankeyLinks,
      lineStyle: {
        color: 'gradient',
        curveness: 0.5
      }
    }]
  }
  
  sankeyChart.setOption(option)
}

// 初始化星云图
function initNebulaChart() {
  if (!nebulaCanvas.value || !nebulaRef.value) return
  
  // 设置canvas尺寸
  const container = nebulaRef.value
  nebulaCanvas.value.width = container.clientWidth
  nebulaCanvas.value.height = container.clientHeight
  
  nebulaCtx = nebulaCanvas.value.getContext('2d')
  if (!nebulaCtx) return
  
  // 转换数据格式为星云布局算法需要的格式
  const nodes = graphData.value.nodes.map(n => ({
    id: n.id,
    type: n.kind === 'job' ? 'job' as const : 'skill' as const,
    name: n.label,
    importance: n.kind === 'industry' ? 3 : n.kind === 'job' ? 2 : 1
  }))
  
  const edges = graphData.value.edges.map(e => ({
    source: e.source,
    target: e.target,
    // 后端统一返回小写关系名；星云布局算法使用正式图谱关系名。
    type: e.kind.toLowerCase() === 'requires' || e.kind === 'job-skill' ? 'REQUIRES' : 'RELATED'
  }))
  
  // 计算布局
  nebulaLayout = computeNebulaLayout(nodes, edges, DEFAULT_NEBULA_CONFIG)
  
  // 绘制星云图
  drawNebula()
}

// 绘制星云图
function drawNebula() {
  if (!nebulaCtx || !nebulaCanvas.value) return
  
  const ctx = nebulaCtx
  const canvas = nebulaCanvas.value
  const width = canvas.width
  const height = canvas.height
  
  // 清空画布
  ctx.clearRect(0, 0, width, height)
  
  // 绘制深空背景
  const gradient = ctx.createRadialGradient(width/2, height/2, 0, width/2, height/2, Math.max(width, height)/2)
  gradient.addColorStop(0, '#0d0d2b')
  gradient.addColorStop(0.5, '#080818')
  gradient.addColorStop(1, '#030310')
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, width, height)
  
  // 绘制星星背景
  for (let i = 0; i < 100; i++) {
    const x = Math.random() * width
    const y = Math.random() * height
    const size = Math.random() * 1.5
    const opacity = Math.random() * 0.5 + 0.2
    ctx.fillStyle = `rgba(255, 255, 255, ${opacity})`
    ctx.beginPath()
    ctx.arc(x, y, size, 0, Math.PI * 2)
    ctx.fill()
  }
  
  // 应用变换
  ctx.save()
  ctx.translate(width/2 + nebulaOffsetX, height/2 + nebulaOffsetY)
  ctx.scale(nebulaZoom, nebulaZoom)
  
  // 绘制边
  graphData.value.edges.forEach(edge => {
    const sourcePos = nebulaLayout[edge.source]
    const targetPos = nebulaLayout[edge.target]
    if (!sourcePos || !targetPos) return
    
    ctx.beginPath()
    ctx.moveTo(sourcePos.x, sourcePos.y)
    ctx.lineTo(targetPos.x, targetPos.y)
    ctx.strokeStyle = 'rgba(80, 80, 160, 0.3)'
    ctx.lineWidth = 1
    ctx.stroke()
  })
  
  // 绘制节点
  graphData.value.nodes.forEach(node => {
    const pos = nebulaLayout[node.id]
    if (!pos) return
    
    // 绘制光晕效果
    const glowRadius = node.size * 1.5
    const glow = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, glowRadius)
    glow.addColorStop(0, node.color + '40')
    glow.addColorStop(1, 'transparent')
    ctx.fillStyle = glow
    ctx.beginPath()
    ctx.arc(pos.x, pos.y, glowRadius, 0, Math.PI * 2)
    ctx.fill()
    
    // 绘制节点
    ctx.beginPath()
    ctx.arc(pos.x, pos.y, node.size / 2, 0, Math.PI * 2)
    ctx.fillStyle = node.color
    ctx.fill()
    
    // 绘制边框
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)'
    ctx.lineWidth = 1
    ctx.stroke()
    
    // 绘制标签
    if (showNebulaLabels) {
      ctx.fillStyle = '#ffffff'
      ctx.font = '12px Microsoft YaHei'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillText(node.label, pos.x, pos.y + node.size/2 + 5)
    }
  })
  
  ctx.restore()
}

// 重置星云视图
function resetNebulaView() {
  nebulaZoom = 1
  nebulaOffsetX = 0
  nebulaOffsetY = 0
  drawNebula()
}

// 切换星云标签显示
function toggleNebulaLabels() {
  showNebulaLabels = !showNebulaLabels
  drawNebula()
}

// 构建树结构数据
function buildTreeData(): any {
  const industries = graphData.value.nodes.filter(function(n) { return n.kind === 'industry' })
  const jobs = graphData.value.nodes.filter(function(n) { return n.kind === 'job' })

  const buildJobTree = function(job: GraphNode) {
    return {
      name: job.label,
      itemStyle: { color: job.color },
      children: graphData.value.edges
        .filter(function(e) {
          return e.source === job.id && (e.kind === 'requires' || e.kind === 'job-skill')
        })
        .map(function(e) {
          var skill = graphData.value.nodes.find(function(n) { return n.id === e.target })
          return {
            name: skill ? skill.label : e.target,
            itemStyle: { color: skill ? skill.color : '#8CA0B8' }
          }
        })
    }
  }

  return {
    name: '岗位能力图谱',
    children: industries.length
      ? industries.map(function(ind) {
          return {
            name: ind.label,
            itemStyle: { color: ind.color },
            children: jobs
              .filter(function(job) { return job.parent === ind.id })
              .map(buildJobTree)
          }
        })
      : jobs.map(buildJobTree)
  }
}

// 获取节点类型标签
function getNodeTypeTag(kind: string) {
  var map: Record<string, string> = {
    'industry': '',
    'job': 'danger',
    'skill': 'info'
  }
  return map[kind] || ''
}

// 获取节点类型标签文本
function getNodeTypeLabel(kind: string) {
  var map: Record<string, string> = {
    'industry': '行业',
    'job': '岗位',
    'skill': '技能'
  }
  return map[kind] || kind
}

// 获取节点关联数
function getNodeLinks(nodeId: string) {
  return graphData.value.edges.filter(function(e) { return e.source === nodeId || e.target === nodeId }).length
}

// 高亮关联节点
function highlightRelated(nodeId: string) {
  if (!forceChart) return
  
  var relatedIds = new Set<string>()
  graphData.value.edges.forEach(function(e) {
    if (e.source === nodeId) relatedIds.add(e.target)
    if (e.target === nodeId) relatedIds.add(e.source)
  })
  relatedIds.add(nodeId)
  
  forceChart.setOption({
    series: [{
      data: graphData.value.nodes.map(function(n) {
        return Object.assign({}, n, {
          symbolSize: n.size,
          itemStyle: {
            color: relatedIds.has(n.id) ? n.color : '#E8DDD4',
            opacity: relatedIds.has(n.id) ? 1 : 0.3
          }
        })
      })
    }]
  })
}

// 聚焦节点
function focusNode(nodeId: string) {
  if (!forceChart) return
  
  var node = graphData.value.nodes.find(function(n) { return n.id === nodeId })
  if (node) {
    forceChart.dispatchAction({
      type: 'graphRoam',
      zoom: 1.5,
      originX: forceRef.value ? forceRef.value.clientWidth / 2 : 0,
      originY: forceRef.value ? forceRef.value.clientHeight / 2 : 0
    })
  }
}

// 刷新图谱
async function refreshGraph() {
  await loadGraphData()
  await nextTick()
  forceChart?.dispose()
  treeChart?.dispose()
  radialChart?.dispose()
  sankeyChart?.dispose()
  initForceChart()
  initTreeChart()
  initRadialChart()
  initSankeyChart()
  ElMessage.success('图谱已刷新')
}

// 导出图谱
function exportGraph() {
  ElMessage.success('图谱导出功能开发中')
}

// 监听视图切换
watch(currentView, function() {
  nextTick(function() {
    switch (currentView.value) {
      case 'force':
        forceChart && forceChart.resize()
        break
      case 'tree':
        treeChart && treeChart.resize()
        break
      case 'radial':
        radialChart && radialChart.resize()
        break
      case 'sankey':
        sankeyChart && sankeyChart.resize()
        break
      case 'nebula':
        initNebulaChart()
        break
    }
  })
})

// 监听筛选条件
watch([selectedTrack, selectedLevel], function() {
  // 根据筛选条件过滤图谱数据
  refreshGraph()
})

// 初始化
onMounted(async function() {
  await loadGraphData()
  nextTick(function() {
    initForceChart()
    initTreeChart()
    initRadialChart()
    initSankeyChart()
  })
  
  // 监听窗口大小变化
  window.addEventListener('resize', function() {
    forceChart && forceChart.resize()
    treeChart && treeChart.resize()
    radialChart && radialChart.resize()
    sankeyChart && sankeyChart.resize()
    
    // 重新绘制星云图
    if (currentView.value === 'nebula' && nebulaCanvas.value && nebulaRef.value) {
      nebulaCanvas.value.width = nebulaRef.value.clientWidth
      nebulaCanvas.value.height = nebulaRef.value.clientHeight
      drawNebula()
    }
  })
  
  // 添加星云图鼠标事件
  if (nebulaCanvas.value) {
    let isDragging = false
    let lastX = 0
    let lastY = 0
    
    nebulaCanvas.value.addEventListener('mousedown', (e) => {
      isDragging = true
      lastX = e.clientX
      lastY = e.clientY
    })
    
    nebulaCanvas.value.addEventListener('mousemove', (e) => {
      if (!isDragging) return
      const deltaX = e.clientX - lastX
      const deltaY = e.clientY - lastY
      nebulaOffsetX += deltaX
      nebulaOffsetY += deltaY
      lastX = e.clientX
      lastY = e.clientY
      drawNebula()
    })
    
    nebulaCanvas.value.addEventListener('mouseup', () => {
      isDragging = false
    })
    
    nebulaCanvas.value.addEventListener('mouseleave', () => {
      isDragging = false
    })
    
    nebulaCanvas.value.addEventListener('wheel', (e) => {
      e.preventDefault()
      const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1
      nebulaZoom *= zoomFactor
      nebulaZoom = Math.max(0.1, Math.min(5, nebulaZoom))
      drawNebula()
    })
  }
})
</script>

<style scoped>
/* 星云图样式 */
.nebula-canvas {
  position: relative;
  background: #030310;
}

.nebula-canvas-element {
  width: 100%;
  height: 100%;
  cursor: grab;
}

.nebula-canvas-element:active {
  cursor: grabbing;
}

.nebula-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  gap: 8px;
  z-index: 10;
}
</style>

<style scoped>
.graph-panorama {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.control-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: white;
  border-bottom: 1px solid #e8e8e8;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.control-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.control-left h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
}

.control-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.view-switcher {
  display: flex;
  align-items: center;
}

.filters {
  display: flex;
  gap: 8px;
}

.btn-ghost {
  background: transparent;
  border: 1px solid #d9d9d9;
  color: #666;
}

.btn-ghost:hover {
  border-color: #409eff;
  color: #409eff;
}

.graph-container {
  flex: 1;
  position: relative;
  margin: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  overflow: hidden;
}

.graph-canvas {
  width: 100%;
  height: 100%;
}

.graph-legend {
  position: absolute;
  top: 16px;
  left: 16px;
  background: rgba(255,255,255,0.95);
  padding: 12px 16px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.legend-title {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  margin-bottom: 8px;
}

.legend-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.legend-label {
  font-size: 12px;
  color: #333;
}

.node-detail {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 280px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  overflow: hidden;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8f9fa;
  border-bottom: 1px solid #e8e8e8;
}

.detail-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
}

.detail-body {
  padding: 12px 16px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.detail-row:last-child {
  border-bottom: none;
}

.detail-label {
  font-size: 12px;
  color: #666;
}

.detail-value {
  font-size: 12px;
  color: #333;
  font-weight: 500;
}

.detail-value.up {
  color: #52c41a;
}

.detail-value.down {
  color: #ff4d4f;
}

.detail-actions {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: #f8f9fa;
  border-top: 1px solid #e8e8e8;
}

.graph-stats {
  display: flex;
  justify-content: center;
  gap: 32px;
  padding: 12px 20px;
  background: white;
  border-top: 1px solid #e8e8e8;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-label {
  font-size: 12px;
  color: #666;
}

.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
}

.stat-value.up {
  color: #52c41a;
}

.stat-value.down {
  color: #ff4d4f;
}
</style>