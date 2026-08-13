<template>
  <div class="dashboard">
    <!-- 页面装饰：底部波浪线 + 小仙人掌 -->
    <div class="page-deco deco-wave-bl">
      <svg width="260" height="80" viewBox="0 0 260 80" fill="none">
        <path d="M0 50 Q30 30 60 50 T120 50 T180 50 T240 50 T260 50" stroke="#E07B6D" stroke-width="1" fill="none" opacity="0.08"/>
        <path d="M0 58 Q30 38 60 58 T120 58 T180 58 T240 58 T260 58" stroke="#A8C5B8" stroke-width="1" fill="none" opacity="0.06"/>
        <rect x="40" y="30" width="4" height="20" rx="2" fill="#A8C5B8" opacity="0.2"/>
        <path d="M40 36 L34 30 L34 34 L40 36" fill="#A8C5B8" opacity="0.15"/>
        <path d="M44 38 L50 32 L50 36 L44 38" fill="#A8C5B8" opacity="0.15"/>
        <rect x="36" y="50" width="12" height="4" rx="2" fill="#D5C8BC" opacity="0.2"/>
        <path d="M180 20 L182 26 L188 26 L183 30 L185 36 L180 32 L175 36 L177 30 L172 26 L178 26 Z" fill="#E07B6D" opacity="0.06"/>
      </svg>
    </div>
    <!-- 右侧小圆点 + 小气球 + 云朵 -->
    <div class="page-deco deco-dots-mr">
      <svg width="80" height="200" viewBox="0 0 80 200" fill="none">
        <circle cx="50" cy="20" r="3" fill="#A8C5B8" opacity="0.1"/>
        <circle cx="60" cy="55" r="2" fill="#E07B6D" opacity="0.08"/>
        <circle cx="45" cy="90" r="4" fill="#B8C4D0" opacity="0.06"/>
        <ellipse cx="30" cy="40" rx="8" ry="10" fill="#E07B6D" opacity="0.06"/>
        <line x1="30" y1="50" x2="30" y2="65" stroke="#E07B6D" stroke-width="0.5" opacity="0.08"/>
        <path d="M28 65 L30 68 L32 65" stroke="#E07B6D" stroke-width="0.5" fill="none" opacity="0.08"/>
        <ellipse cx="20" cy="140" rx="12" ry="6" fill="#B8C4D0" opacity="0.05"/>
      </svg>
    </div>

    <header class="welcome-bar">
      <div class="welcome-left">
        <h1>岗位人才数据总览</h1>
        <p class="welcome-sub">统一采集全渠道JD岗位与简历数据，可视化分析岗位技能需求、人才匹配缺口</p>
      </div>
      <div class="welcome-right">
        <!-- 小人举图表 + 旗子 + 火箭 -->
        <div class="welcome-deco">
          <svg width="100" height="70" viewBox="0 0 100 70" fill="none">
            <circle cx="50" cy="16" r="8" fill="#F5D5C8"/>
            <path d="M44 14 Q46 8 50 7 Q54 8 56 14" fill="#8B7B6B" opacity="0.5"/>
            <path d="M42 24 Q42 20 50 20 Q58 20 58 24 L60 40 Q60 44 50 44 Q40 44 40 40 Z" fill="#E07B6D" opacity="0.2"/>
            <path d="M42 30 L28 18" stroke="#F5D5C8" stroke-width="2.5" stroke-linecap="round"/>
            <rect x="14" y="6" width="18" height="14" rx="2" fill="#fff" stroke="#E0D5CA" stroke-width="0.8"/>
            <rect x="17" y="14" width="3" height="4" rx="0.5" fill="#E07B6D" opacity="0.4"/>
            <rect x="21" y="11" width="3" height="7" rx="0.5" fill="#A8C5B8" opacity="0.5"/>
            <path d="M58 30 L70 20" stroke="#F5D5C8" stroke-width="2.5" stroke-linecap="round"/>
            <line x1="70" y1="8" x2="70" y2="22" stroke="#D5C8BC" stroke-width="1"/>
            <path d="M70 8 L82 12 L70 16 Z" fill="#E07B6D" opacity="0.25"/>
            <g transform="translate(82, 2) rotate(35)">
              <ellipse cx="6" cy="10" rx="4" ry="7" fill="#FDE8E4" stroke="#E07B6D" stroke-width="0.6" opacity="0.5"/>
              <path d="M3 16 L6 20 L9 16" fill="#FFA726" opacity="0.3"/>
            </g>
          </svg>
        </div>
        <div class="time-pills">
          <button v-for="opt in timeOptions" :key="opt.value" class="pill-btn" :class="{ active: timeRange === opt.value }" @click="timeRange = opt.value">{{ opt.label }}</button>
        </div>
      </div>
    </header>

    <section class="stats-row" v-loading="dashboardLoading" element-loading-text="加载中...">
      <div v-for="(card, i) in statCards" :key="card.title" class="stat-card warm-card">
        <div class="stat-icon-circle" :style="{ background: card.iconBg }">
          <svg v-if="i===0" width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="3" y="8" width="16" height="12" rx="2" stroke="#E07B6D" stroke-width="1.4" fill="none"/><path d="M7 8 V6 Q7 3 11 3 Q15 3 15 6 V8" stroke="#E07B6D" stroke-width="1.4" fill="none"/><circle cx="11" cy="14" r="2" stroke="#E07B6D" stroke-width="1" fill="#FDE8E4"/></svg>
          <svg v-else-if="i===1" width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="4" y="2" width="14" height="18" rx="2" stroke="#66BB6A" stroke-width="1.4" fill="none"/><line x1="7" y1="7" x2="15" y2="7" stroke="#66BB6A" stroke-width="1" opacity="0.6"/><line x1="7" y1="10" x2="13" y2="10" stroke="#66BB6A" stroke-width="1" opacity="0.4"/><circle cx="11" cy="5" r="1.5" fill="#E8F5E9" stroke="#66BB6A" stroke-width="0.8"/></svg>
          <svg v-else-if="i===2" width="22" height="22" viewBox="0 0 22 22" fill="none"><circle cx="8" cy="11" r="5" stroke="#FFA726" stroke-width="1.4" fill="none"/><circle cx="14" cy="11" r="5" stroke="#FFA726" stroke-width="1.4" fill="none"/><circle cx="11" cy="11" r="1.5" fill="#FFF3E0"/></svg>
          <svg v-else width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M11 3 L3 19 L19 19 Z" stroke="#EF5350" stroke-width="1.4" fill="none" stroke-linejoin="round"/><line x1="11" y1="9" x2="11" y2="13" stroke="#EF5350" stroke-width="1.4" stroke-linecap="round"/><circle cx="11" cy="16" r="1" fill="#EF5350"/></svg>
        </div>
        <div class="stat-info"><span class="stat-label">{{ card.title }}</span><span class="stat-value">{{ animatedNums[i] }}</span></div>
        <span class="stat-badge" :style="{ background: card.badgeBg, color: card.badgeColor }">{{ card.trend }}</span>
        <svg class="card-corner-deco" width="40" height="40" viewBox="0 0 40 40" fill="none"><circle cx="35" cy="5" r="3" :fill="card.iconColor" opacity="0.06"/><circle cx="30" cy="12" r="1.5" :fill="card.iconColor" opacity="0.04"/></svg>
      </div>
    </section>

    <!-- 珊瑚粉色块统计 - 横向排列 -->
    <section class="stat-blocks-row">
        <div class="coral-block" v-for="block in coralBlocks" :key="block.label"><span class="coral-num">{{ block.value }}</span><span class="coral-label">{{ block.label }}</span></div>
    </section>

    <section class="charts-row">
      <div class="warm-card chart-card">
        <div class="card-head"><div><h3>岗位能力趋势</h3><p>近6个月各岗位需求指数变化</p></div>
          <div class="metric-pills"><button v-for="m in metricOptions" :key="m.value" class="pill-btn sm" :class="{ active: lineMetric === m.value }" @click="lineMetric = m.value">{{ m.label }}</button></div>
        </div>
        <div ref="lineChartRef" class="chart-box"></div>
        <div class="chart-deco chart-deco-br"><svg width="32" height="32" viewBox="0 0 32 32" fill="none"><path d="M6 14 Q6 10 10 10 L20 10 Q24 10 24 14 L24 22 Q24 26 20 26 L10 26 Q6 26 6 22 Z" fill="#F5F0EA" stroke="#D5C8BC" stroke-width="0.8"/><path d="M24 16 Q28 16 28 20 Q28 24 24 24" stroke="#D5C8BC" stroke-width="0.8" fill="none"/><path d="M10 8 Q11 4 12 8" stroke="#D5C8BC" stroke-width="0.6" fill="none" opacity="0.4"/><path d="M14 7 Q15 3 16 7" stroke="#D5C8BC" stroke-width="0.6" fill="none" opacity="0.3"/></svg></div>
      </div>
      <div class="warm-card chart-card">
        <div class="card-head"><div><h3>岗位技能分布</h3><p>Top 8 核心技能覆盖率</p></div></div>
        <div ref="barChartRef" class="chart-box"></div>
        <div class="chart-deco chart-deco-tl"><svg width="28" height="28" viewBox="0 0 28 28" fill="none"><rect x="8" y="4" width="6" height="18" rx="1" fill="#FDE8E4" stroke="#E07B6D" stroke-width="0.6" transform="rotate(-30 11 13)"/><path d="M7 22 L10 26 L13 22" fill="#E07B6D" opacity="0.3" transform="rotate(-30 10 24)"/></svg></div>
      </div>
    </section>

    <div class="section-deco"><svg width="200" height="12" viewBox="0 0 200 12" fill="none"><circle cx="80" cy="6" r="2" fill="#E07B6D" opacity="0.1"/><circle cx="100" cy="6" r="3" fill="#A8C5B8" opacity="0.08"/><circle cx="120" cy="6" r="2" fill="#B8C4D0" opacity="0.1"/><line x1="30" y1="6" x2="70" y2="6" stroke="#E0D5CA" stroke-width="0.5" opacity="0.3"/><line x1="130" y1="6" x2="170" y2="6" stroke="#E0D5CA" stroke-width="0.5" opacity="0.3"/></svg></div>

    <section class="bottom-row">
      <div class="warm-card table-card">
        <div class="card-head"><div><h3>岗位列表</h3><p>共 {{ filteredJobs.length }} 个在招岗位</p></div><el-input v-model="jobSearch" placeholder="搜索岗位名称..." :prefix-icon="Search" clearable style="width:200px" size="small" /></div>
        <el-table :data="pagedJobs" style="width:100%" :header-cell-style="tblHeaderStyle" :cell-style="{ padding:'12px 0' }">
          <el-table-column prop="name" label="岗位名称" min-width="150"><template #default="{ row }"><span class="job-name">{{ row.name }}</span></template></el-table-column>
          <el-table-column prop="dept" label="部门" width="110" />
          <el-table-column prop="count" label="需求人数" width="90" align="center"><template #default="{ row }"><span class="count-badge" :class="row.count>=10?'hot':row.count>=5?'warm':'cool'">{{ row.count }}人</span></template></el-table-column>
          <el-table-column prop="salary" label="薪资范围" width="120" />
          <el-table-column prop="status" label="状态" width="90" align="center"><template #default="{ row }"><span class="status-dot" :class="row.status==='急聘'?'urgent':row.status==='招聘中'?'open':'pending'"></span>{{ row.status }}</template></el-table-column>
          <el-table-column prop="updateTime" label="更新时间" width="110" />
        </el-table>
        <div class="tbl-pagination"><el-pagination v-model:current-page="currentPage" :page-size="pageSize" :total="filteredJobs.length" layout="total, prev, pager, next" small /></div>
      </div>

      <div class="side-panels">
        <div class="warm-card side-card">
          <div class="card-head"><h3>待办日程</h3><span class="card-count">{{ scheduleItems.length }}</span></div>
          <div class="sched-list">
            <div v-for="item in scheduleItems" :key="item.id" class="sched-item" :class="item.level">
              <div class="sched-dot" :class="item.level"></div>
              <div class="sched-body"><span class="sched-title">{{ item.title }}</span><span class="sched-time">{{ item.time }}</span></div>
              <span class="sched-tag" :class="item.level">{{ item.tag }}</span>
            </div>
          </div>
          <div class="card-deco-tl"><svg width="24" height="24" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="4" fill="#FFA726" opacity="0.08"/><line x1="12" y1="4" x2="12" y2="6" stroke="#FFA726" stroke-width="1" opacity="0.1" stroke-linecap="round"/><line x1="12" y1="18" x2="12" y2="20" stroke="#FFA726" stroke-width="1" opacity="0.1" stroke-linecap="round"/><line x1="4" y1="12" x2="6" y2="12" stroke="#FFA726" stroke-width="1" opacity="0.1" stroke-linecap="round"/><line x1="18" y1="12" x2="20" y2="12" stroke="#FFA726" stroke-width="1" opacity="0.1" stroke-linecap="round"/></svg></div>
        </div>
        <div class="warm-card side-card">
          <div class="card-head"><h3>待分析任务</h3><span class="card-count">{{ pendingCount }}</span></div>
          <div class="task-list">
            <div v-for="task in taskItems" :key="task.id" class="task-item"><el-checkbox v-model="task.done" /><div class="task-body"><span :class="{ done: task.done }">{{ task.title }}</span><span class="task-deadline">{{ task.deadline }}</span></div></div>
          </div>
        </div>
        <div class="create-card" @click="$router.push('/jobs')">
          <div class="create-inner">
            <div class="create-icon-wrap"><el-icon :size="24"><Plus /></el-icon><svg class="create-sparkle" width="40" height="40" viewBox="0 0 40 40" fill="none"><path d="M20 8 L22 16 L30 18 L22 20 L20 28 L18 20 L10 18 L18 16 Z" fill="#E07B6D" opacity="0.12"/><circle cx="32" cy="10" r="2" fill="#A8C5B8" opacity="0.15"/><circle cx="8" cy="28" r="1.5" fill="#FFA726" opacity="0.12"/></svg></div>
            <span>创建新岗位分析</span>
          </div>
        </div>
      </div>
    </section>

    <div class="page-deco deco-footer"><svg width="300" height="50" viewBox="0 0 300 50" fill="none"><path d="M0 45 Q40 20 80 40 Q120 55 160 35 Q200 15 240 38 Q280 55 300 40" stroke="#E0D5CA" stroke-width="0.8" fill="none" opacity="0.15"/><rect x="95" y="28" width="2" height="12" rx="1" fill="#A8C5B8" opacity="0.12"/><circle cx="96" cy="25" r="5" fill="#A8C5B8" opacity="0.06"/><rect x="200" y="30" width="10" height="8" rx="1" fill="#FDE8E4" opacity="0.12"/><path d="M198 30 L205 24 L212 30" fill="#E07B6D" opacity="0.08"/></svg></div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, reactive } from 'vue'
import { Search, User, Document, DataAnalysis, Trophy, Plus } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getDashboardOverview, getDashboardTrend, getSkillDistribution, getJobList } from '../api'

const dashboardLoading = ref(true)
const timeRange = ref('month')
const lineMetric = ref('demand')
const jobSearch = ref('')
const currentPage = ref(1)
const pageSize = 8
const timeOptions = [{ label:'日', value:'day' },{ label:'周', value:'week' },{ label:'月', value:'month' }]
const metricOptions = [{ label:'需求指数', value:'demand' },{ label:'薪资水平', value:'salary' }]
const statCards = reactive([
  { title:'岗位总数', value:2468, trend:'↑ 12.5%', iconBg:'#FDE8E4', iconColor:'#E07B6D', icon:DataAnalysis, badgeBg:'#FDE8E4', badgeColor:'#D96C63' },
  { title:'解析简历数', value:8932, trend:'↑ 23.1%', iconBg:'#E8F5E9', iconColor:'#66BB6A', icon:Document, badgeBg:'#E8F5E9', badgeColor:'#43A047' },
  { title:'匹配成功数', value:1847, trend:'↑ 8.7%', iconBg:'#FFF3E0', iconColor:'#FFA726', icon:Trophy, badgeBg:'#FFF3E0', badgeColor:'#EF6C00' },
  { title:'技能缺口数', value:376, trend:'↓ 5.2%', iconBg:'#FCE4EC', iconColor:'#EF5350', icon:User, badgeBg:'#FCE4EC', badgeColor:'#E53935' }
])
const coralBlocks = [{ value:'28', label:'新增岗位' },{ value:'24', label:'待面试' },{ value:'04', label:'紧急招聘' }]

const animatedNums = ref([0,0,0,0])
let animTimer: ReturnType<typeof setInterval> | null = null
function animateNumbers() {
  const targets = statCards.map(c => c.value); let step = 0
  animTimer = setInterval(() => { step++; const p = step/40; const ease = 1 - Math.pow(1-p,3); animatedNums.value = targets.map(t => Math.round(t*ease)); if (step>=40) { animatedNums.value = targets; if(animTimer) clearInterval(animTimer) } }, 30)
}

const lineChartRef = ref<HTMLElement>(); const barChartRef = ref<HTMLElement>()
let lineChart: echarts.ECharts | null = null; let barChart: echarts.ECharts | null = null
const months = ['2月','3月','4月','5月','6月','7月']
const demandData: Record<string, number[]> = { 'AI算法':[82,88,91,95,98,105], '前端开发':[75,78,82,86,90,94], '后端开发':[70,73,76,80,83,87], '大数据':[65,69,74,78,82,88], '云计算':[58,62,67,71,76,80], '测试':[50,53,56,60,64,68], '产品':[55,58,61,65,69,73], '物联网':[45,48,52,56,60,65] }
const salaryData: Record<string, number[]> = { 'AI算法':[28,30,31,32,34,35], '前端开发':[20,21,22,23,24,25], '后端开发':[22,23,24,25,26,27], '大数据':[24,25,26,27,28,29], '云计算':[23,24,25,26,27,28], '测试':[15,16,17,18,19,20], '产品':[18,19,20,21,22,23], '物联网':[17,18,19,20,21,22] }
const lineColors = ['#E07B6D','#66BB6A','#FFA726','#EF5350','#42A5F5','#AB47BC','#78909C','#26A69A']

function getLineOption() {
  const dm = lineMetric.value === 'demand' ? demandData : salaryData
  return { tooltip:{ trigger:'axis', backgroundColor:'#fff', borderColor:'#F0EBE3', textStyle:{ color:'#3D3D3D', fontSize:12 }, borderRadius:12, extraCssText:'box-shadow:0 4px 16px rgba(0,0,0,0.06);' }, legend:{ bottom:0, textStyle:{ color:'#999', fontSize:11 }, itemWidth:14, itemHeight:6, itemGap:14 }, grid:{ top:16, right:16, bottom:44, left:44 }, xAxis:{ type:'category', data:months, axisLine:{ lineStyle:{ color:'#F0EBE3' } }, axisTick:{ show:false }, axisLabel:{ color:'#999', fontSize:11 } }, yAxis:{ type:'value', axisLabel:{ color:'#999', fontSize:11 }, splitLine:{ lineStyle:{ color:'#F5F0EA', type:'dashed' } } }, series: Object.keys(dm).map((name,i) => ({ name, type:'line', data:dm[name], smooth:0.4, symbol:'circle', symbolSize:5, lineStyle:{ width:2, color:lineColors[i] }, itemStyle:{ color:lineColors[i] }, areaStyle:{ color: new echarts.graphic.LinearGradient(0,0,0,1,[{ offset:0, color:lineColors[i]+'20' },{ offset:1, color:lineColors[i]+'02' }]) } })) }
}
const barSkills = ['JavaScript','Python','Java','TypeScript','SQL','Vue','React','Go']
const barValues = [92,88,76,71,68,65,60,55]
function getBarOption() {
  return { tooltip:{ trigger:'axis', backgroundColor:'#fff', borderColor:'#F0EBE3', textStyle:{ color:'#3D3D3D', fontSize:12 }, borderRadius:12, extraCssText:'box-shadow:0 4px 16px rgba(0,0,0,0.06);', formatter:(params:any) => { const p=params[0]; return '<div style="font-weight:600">'+p.name+'</div><div style="margin-top:4px;color:#8C8C8C">覆盖率 <b style="color:#E07B6D">'+p.value+'%</b></div>' } }, grid:{ top:12, right:16, bottom:32, left:76 }, xAxis:{ type:'value', max:100, axisLabel:{ color:'#999', fontSize:11, formatter:'{value}%' }, splitLine:{ lineStyle:{ color:'#F5F0EA', type:'dashed' } } }, yAxis:{ type:'category', data:barSkills, axisLine:{ show:false }, axisTick:{ show:false }, axisLabel:{ color:'#3D3D3D', fontSize:12 } }, series:[{ type:'bar', data:barValues.map((v,i)=>({ value:v, itemStyle:{ borderRadius:[0,6,6,0], color: new echarts.graphic.LinearGradient(0,0,1,0,[{ offset:0, color:lineColors[i]+'40' },{ offset:1, color:lineColors[i] }]) } })), barWidth:14, label:{ show:true, position:'right', formatter:'{c}%', color:'#999', fontSize:11 } }] }
}

interface JobRow { id:number; name:string; dept:string; count:number; salary:string; status:string; updateTime:string }
const allJobs = ref<JobRow[]>([
  { id:1, name:'AI算法工程师', dept:'人工智能部', count:15, salary:'30-50K', status:'急聘', updateTime:'2026-08-06' },
  { id:2, name:'高级前端工程师', dept:'产品技术部', count:8, salary:'25-40K', status:'招聘中', updateTime:'2026-08-05' },
  { id:3, name:'大数据开发工程师', dept:'数据平台部', count:12, salary:'28-45K', status:'急聘', updateTime:'2026-08-05' },
  { id:4, name:'Go后端工程师', dept:'基础架构部', count:6, salary:'25-42K', status:'招聘中', updateTime:'2026-08-04' },
  { id:5, name:'云计算运维工程师', dept:'基础设施部', count:4, salary:'20-35K', status:'招聘中', updateTime:'2026-08-04' },
  { id:6, name:'测试开发工程师', dept:'质量保障部', count:5, salary:'18-30K', status:'招聘中', updateTime:'2026-08-03' },
  { id:7, name:'产品经理（B端）', dept:'产品部', count:3, salary:'22-38K', status:'待开放', updateTime:'2026-08-03' },
  { id:8, name:'NLP算法工程师', dept:'人工智能部', count:10, salary:'35-55K', status:'急聘', updateTime:'2026-08-02' },
  { id:9, name:'嵌入式软件工程师', dept:'物联网部', count:7, salary:'18-32K', status:'招聘中', updateTime:'2026-08-02' },
  { id:10, name:'DevOps工程师', dept:'基础设施部', count:4, salary:'22-36K', status:'招聘中', updateTime:'2026-08-01' },
  { id:11, name:'数据分析师', dept:'商业智能部', count:6, salary:'18-28K', status:'招聘中', updateTime:'2026-08-01' },
  { id:12, name:'Vue3前端工程师', dept:'产品技术部', count:9, salary:'20-35K', status:'急聘', updateTime:'2026-07-31' },
  { id:13, name:'Java高级工程师', dept:'基础架构部', count:5, salary:'28-45K', status:'招聘中', updateTime:'2026-07-30' },
  { id:14, name:'SRE工程师', dept:'基础设施部', count:3, salary:'25-40K', status:'待开放', updateTime:'2026-07-30' },
  { id:15, name:'自动化测试工程师', dept:'质量保障部', count:4, salary:'15-25K', status:'招聘中', updateTime:'2026-07-29' }
])
const filteredJobs = computed(() => jobSearch.value ? allJobs.value.filter(j => j.name.includes(jobSearch.value)) : allJobs.value)
const pagedJobs = computed(() => { const s=(currentPage.value-1)*pageSize; return filteredJobs.value.slice(s,s+pageSize) })
const tblHeaderStyle = { background:'#FAF7F2', color:'#8C8C8C', fontWeight:'500', fontSize:'12px', borderBottom:'1px solid #F0EBE3' }

interface ScheduleItem { id:number; title:string; time:string; tag:string; level:'urgent'|'normal'|'low' }
const scheduleItems = ref<ScheduleItem[]>([
  { id:1, title:'AI算法岗位JD评审', time:'今天 14:00', tag:'紧急', level:'urgent' },
  { id:2, title:'前端团队能力评估', time:'今天 16:30', tag:'进行中', level:'normal' },
  { id:3, title:'大数据岗位需求对接', time:'明天 10:00', tag:'待处理', level:'normal' },
  { id:4, title:'季度技能缺口报告', time:'周五 15:00', tag:'计划中', level:'low' }
])
interface TaskItem { id:number; title:string; deadline:string; done:boolean }
const taskItems = ref<TaskItem[]>([
  { id:1, title:'NLP工程师能力模型更新', deadline:'今日截止', done:false },
  { id:2, title:'前端React技能树校准', deadline:'明日截止', done:false },
  { id:3, title:'云计算岗位薪资调研', deadline:'3天后', done:false },
  { id:4, title:'物联网嵌入式技能补充', deadline:'本周内', done:false },
  { id:5, title:'大数据Spark能力评估', deadline:'已完成', done:true }
])
const pendingCount = computed(() => taskItems.value.filter(t => !t.done).length)

function initCharts() { if(lineChartRef.value){lineChart=echarts.init(lineChartRef.value);lineChart.setOption(getLineOption())} if(barChartRef.value){barChart=echarts.init(barChartRef.value);barChart.setOption(getBarOption())} }
function handleResize() { lineChart?.resize(); barChart?.resize() }
watch(lineMetric, () => { lineChart?.setOption(getLineOption(), true) })
async function loadDashboardData() {
  dashboardLoading.value = true
  try {
    const [overview] = await Promise.all([
      getDashboardOverview(),
    ])
    if (overview) {
      statCards[0].value = overview.totalJobs
      statCards[1].value = overview.totalResumes
      statCards[2].value = overview.matchSuccess
      statCards[3].value = overview.skillGaps
    }
  } catch (e) {
    console.error('加载看板数据失败:', e)
  } finally {
    dashboardLoading.value = false
  }
}
onMounted(async () => { animateNumbers(); initCharts(); window.addEventListener('resize', handleResize); await loadDashboardData() })
onUnmounted(() => { window.removeEventListener('resize', handleResize); lineChart?.dispose(); barChart?.dispose(); if(animTimer) clearInterval(animTimer) })
</script>
<style scoped>
.dashboard{--coral:#E07B6D;--coral-light:#FDE8E4;--green:#66BB6A;--green-light:#E8F5E9;--orange:#FFA726;--orange-light:#FFF3E0;--red:#EF5350;--red-light:#FCE4EC;--text:#3D3D3D;--text-sec:#8C8C8C;--text-muted:#B0B0B0;--bg:#FDFBF7;--card-bg:#FFFFFF;--border:#F0EBE3;--radius:16px;position:relative}
.page-deco{position:fixed;z-index:0;pointer-events:none}
.deco-wave-bl{bottom:0;left:240px}
.deco-dots-mr{top:40%;right:0;transform:translateY(-50%)}

.welcome-bar{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:28px;flex-wrap:wrap;gap:16px;position:relative}
.welcome-left h1{font-size:22px;font-weight:600;color:var(--text);margin:0 0 4px}
.welcome-sub{font-size:13px;color:var(--text-sec);margin:0 0 2px}
.welcome-date{font-size:11px;color:var(--text-muted);margin:0}
.welcome-right{display:flex;align-items:center;gap:12px}
.welcome-deco{opacity:0.85;flex-shrink:0}
.time-pills,.metric-pills{display:inline-flex;background:#fff;border:1px solid var(--border);border-radius:20px;padding:3px;gap:2px}
.pill-btn{border:none;background:transparent;color:var(--text-sec);font-size:12px;font-weight:500;padding:6px 16px;border-radius:16px;cursor:pointer;transition:all 0.2s;font-family:inherit}
.pill-btn.sm{padding:4px 12px;font-size:11px}
.pill-btn.active{background:var(--coral-light);color:var(--coral)}
.pill-btn:hover:not(.active){background:#FDF7F5}
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px;align-items:start}
.stat-card{padding:20px;display:flex;flex-wrap:wrap;align-items:center;gap:14px;position:relative}
.stat-icon-circle{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.stat-info{flex:1;min-width:0}
.stat-label{display:block;font-size:12px;color:var(--text-sec);margin-bottom:4px}
.stat-value{display:block;font-size:26px;font-weight:600;color:var(--text);line-height:1.1;font-variant-numeric:tabular-nums}
.stat-badge{position:absolute;top:16px;right:16px;font-size:11px;font-weight:500;padding:3px 10px;border-radius:20px}
.card-corner-deco{position:absolute;top:0;right:0;pointer-events:none}
.stat-blocks-row{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:24px}
.coral-block{background:var(--coral);color:#fff;border-radius:12px;padding:14px 20px;text-align:center;min-width:90px}
.coral-num{display:block;font-size:24px;font-weight:700;line-height:1.1;margin-bottom:2px}
.coral-label{font-size:11px;opacity:0.85}
.charts-row{display:grid;grid-template-columns:1.4fr 1fr;gap:16px;margin-bottom:16px}
.chart-card{padding:24px;position:relative;overflow:visible}
.chart-box{width:100%;height:280px}
.card-head{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px}
.card-head h3{font-size:15px;font-weight:600;color:var(--text);margin:0 0 3px}
.card-head p{font-size:11px;color:var(--text-muted);margin:0}
.card-count{background:var(--coral-light);color:var(--coral);font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px}
.chart-deco{position:absolute;pointer-events:none;opacity:0.7}
.chart-deco-br{bottom:8px;right:8px}
.chart-deco-tl{top:8px;left:8px}
.section-deco{display:flex;justify-content:center;margin-bottom:16px}
.bottom-row{display:grid;grid-template-columns:1.6fr 1fr;gap:16px}
.table-card{padding:24px}
:deep(.el-table){--el-table-border-color:#F5F0EA;--el-table-tr-bg-hover:#FDF7F5;--el-table-header-bg-color:transparent;background:transparent;font-size:12px}
:deep(.el-table th.el-table__cell){background:#FAF7F2 !important;border-bottom:1px solid #F0EBE3}
.job-name{font-weight:500;color:var(--text);font-size:13px}
.count-badge{font-size:11px;font-weight:500;padding:2px 8px;border-radius:8px}
.count-badge.hot{background:var(--coral-light);color:var(--coral)}
.count-badge.warm{background:var(--orange-light);color:#EF6C00}
.count-badge.cool{background:#F5F5F5;color:#999}
.status-dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:6px;vertical-align:middle}
.status-dot.urgent{background:var(--coral)}
.status-dot.open{background:var(--green)}
.status-dot.pending{background:var(--text-muted)}
.tbl-pagination{display:flex;justify-content:flex-end;margin-top:14px}
.side-panels{display:flex;flex-direction:column;gap:16px}
.side-card{padding:20px;position:relative}
.card-deco-tl{position:absolute;top:8px;right:8px;pointer-events:none}
.sched-list{display:flex;flex-direction:column;gap:10px}
.sched-item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:10px;background:#FDFBF7;transition:background 0.2s}
.sched-item:hover{background:#F5F0EA}
.sched-item.urgent{border-left:3px solid var(--coral)}
.sched-item.normal{border-left:3px solid var(--orange)}
.sched-item.low{border-left:3px solid var(--green)}
.sched-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.sched-dot.urgent{background:var(--coral)}
.sched-dot.normal{background:var(--orange)}
.sched-dot.low{background:var(--green)}
.sched-body{flex:1;min-width:0}
.sched-title{display:block;font-size:12px;font-weight:500;color:var(--text);margin-bottom:1px}
.sched-time{font-size:10px;color:var(--text-muted)}
.sched-tag{font-size:10px;font-weight:500;padding:2px 8px;border-radius:8px;flex-shrink:0}
.sched-tag.urgent{background:var(--coral-light);color:var(--coral)}
.sched-tag.normal{background:var(--orange-light);color:#EF6C00}
.sched-tag.low{background:var(--green-light);color:#43A047}
.task-list{display:flex;flex-direction:column;gap:8px}
.task-item{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:10px;transition:background 0.2s}
.task-item:hover{background:#FDF7F5}
.task-body{flex:1;min-width:0}
.task-body span:first-child{display:block;font-size:12px;color:var(--text);transition:color 0.2s}
.task-body span.done{text-decoration:line-through;color:var(--text-muted)}
.task-deadline{font-size:10px;color:var(--text-muted)}
.create-card{border:2px dashed #D9D9D9;border-radius:var(--radius);padding:28px;cursor:pointer;transition:border-color 0.2s,background 0.2s;text-align:center}
.create-card:hover{border-color:var(--coral);background:#FDF7F5}
.create-inner{display:flex;flex-direction:column;align-items:center;gap:8px;color:var(--text-muted);font-size:13px}
.create-inner .el-icon{color:var(--coral)}
.create-icon-wrap{position:relative;display:flex;align-items:center;justify-content:center}
.create-sparkle{position:absolute;top:-8px;left:-8px;pointer-events:none}
@media(max-width:1200px){.stats-row,.stat-blocks-row{grid-template-columns:repeat(2,1fr)}.charts-row,.bottom-row{grid-template-columns:1fr}}
@media(max-width:768px){.stats-row,.stat-blocks-row{grid-template-columns:1fr}.welcome-bar{flex-direction:column;align-items:flex-start}.welcome-deco{display:none}.page-deco{display:none}}
</style>

