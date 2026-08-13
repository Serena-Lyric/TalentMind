<template>
  <section class="diagnosis-page">
    <div class="page-title">
      <div>
        <h1>简历上传诊断</h1>
        <p>智能提取个人能力，并与目标岗位能力图谱进行匹配分析</p>
      </div>
      <div class="title-actions">
        <el-button @click="importMockResume">
          <el-icon><Document /></el-icon>导入模拟简历
        </el-button>
        <el-button @click="goToPreview">
          <el-icon><View /></el-icon>预览简历
        </el-button>
        <el-select v-model="targetJob" class="target-select">
          <template #prefix>
            <el-icon><Aim /></el-icon>
          </template>
          <el-option v-for="job in targetJobs" :key="job.value" :label="job.label" :value="job.value" />
        </el-select>
      </div>
    </div>
    <section v-if="!parsed" class="upload-panel panel">
<div class="upload-copy">
        <span class="upload-badge">AI 简历解析</span>
        <h2>上传简历，开始能力诊断</h2>
        <p>支持 PDF、DOC、DOCX 格式。系统将提取教育、经历和技能信息，并生成岗位匹配报告。</p>
        <div class="privacy-line">
          <span>✓</span> 文件仅用于本次本地诊断，不会存储或对外共享
        </div>
      </div>
      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".pdf,.doc,.docx"
        :on-change="handleFile"
        class="resume-upload"
      >
        <el-icon class="upload-illustration"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将 PDF / Word 简历拖到这里<br/>
          <em>或点击选择文件</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">支持最大 10MB 的 PDF、DOC、DOCX 文件</div>
        </template>
      </el-upload>
    </section>
    
    <section v-else>
      <div class="parse-success">
        <span class="success-icon">✓</span>
        <div>
          <b>{{ fileName }} 已解析完成</b>
          <p>已提取 {{ profile.skills.length }} 项个人技能，诊断报告已根据目标岗位更新。</p>
        </div>
        <el-button text type="primary" @click="parsed=false">重新上传</el-button>
      </div>
      
      <div class="diagnosis-grid">
        <article class="panel profile-panel">
          <div class="profile-head">
            <el-avatar :size="60">{{ profile.name[0] }}</el-avatar>
            <div>
              <h2>{{ profile.name }}</h2>
              <p>{{ profile.role }} · {{ profile.experience }}</p>
            </div>
            <el-tag type="success" effect="light">解析成功</el-tag>
          </div>
          <el-divider/>
          <div class="info-list">
            <div><span>最高学历</span><b>{{ profile.education }}</b></div>
            <div><span>最近公司</span><b>{{ profile.company }}</b></div>
            <div><span>工作年限</span><b>{{ profile.experience }}</b></div>
          </div>
          <h3>提取的个人技能 <small>({{ profile.skills.length }})</small></h3>
          <div class="extracted-skills">
            <el-tag v-for="skill in profile.skills" :key="skill" effect="plain">{{ skill }}</el-tag>
          </div>
          <h3>关键词摘要</h3>
          <p class="profile-summary">{{ profile.summary }}</p>
        </article>
        
        <article class="panel radar-panel">
          <AbilityRadar :data="radarData" />
        </article>
        
        <article class="panel score-panel">
          <h3>综合匹配度</h3>
          <el-progress 
            type="dashboard" 
            :percentage="currentJob.score" 
            :width="190" 
            :stroke-width="13" 
            color="#E07B6D"
          >
            <template #default="{ percentage }">
              <strong>{{ percentage }}</strong>
              <span>分</span>
              <p>{{ scoreText }}</p>
            </template>
          </el-progress>
          <p class="score-caption">与「{{ currentJob.label }}」能力需求的匹配评估</p>
          <div class="score-breakdown">
            <div v-for="item in currentJob.dimensions.slice(0, 3)" :key="item.name">
              <span>{{ item.name }}</span>
              <el-progress :percentage="item.value" :show-text="false" :stroke-width="6" color="#E07B6D"/>
              <b>{{ item.value }}</b>
            </div>
          </div>
        </article>
      </div>
      
      <section class="panel skill-result">
        <div class="panel-head">
          <div>
            <h3>技能匹配诊断</h3>
            <p>识别已有优势与优先提升的能力缺口</p>
          </div>
          <el-button type="primary" plain @click="goToLearning">
            <el-icon><MagicStick /></el-icon>生成学习路径
          </el-button>
        </div>
        <div class="skill-columns">
          <div class="skill-column matched">
            <div class="column-title">
              <i>✓</i>
              <div>
                <b>已有技能</b>
                <span>{{ currentJob.matched.length }} 项能力已匹配</span>
              </div>
            </div>
            <div class="diagnostic-tags">
              <el-tag v-for="skill in currentJob.matched" :key="skill" type="success" effect="light">{{ skill }}</el-tag>
            </div>
            <p class="column-note">这些技能与目标岗位高度相关，是你的重点竞争优势。</p>
          </div>
          <div class="skill-column missing">
            <div class="column-title">
              <i>!</i>
              <div>
                <b>缺失 / 薄弱技能</b>
                <span>{{ currentJob.missing.length }} 项建议优先补齐</span>
              </div>
            </div>
            <div class="gap-list">
              <div v-for="skill in currentJob.missing" :key="skill.name">
                <span class="gap-level" :class="skill.level"></span>
                <div>
                  <b>{{ skill.name }}</b>
                  <p>{{ skill.tip }}</p>
                </div>
                <el-tag :type="skill.level === 'high' ? 'danger' : 'warning'" size="small">
                  {{ skill.level === 'high' ? '优先提升' : '建议学习' }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>
      </section>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Aim, UploadFilled, Document, View, MagicStick } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { resume } from '../data/mock'
import { mockResume, mockResumeSkills, mockMatchResult } from '../mock/resume-data'
import AbilityRadar from './AbilityRadar.vue'

interface Dimension {
  name: string
  value: number
}

interface MissingSkill {
  name: string
  level: 'high' | 'medium'
  tip: string
}

interface JobOption {
  value: string
  label: string
  score: number
  dimensions: Dimension[]
  matched: string[]
  missing: MissingSkill[]
}

const router = useRouter()
const parsed = ref(false)

const fileName = ref('')
const targetJob = ref('frontend')

const profile = ref({
  ...resume,
  education: '本科 · 软件工程',
  company: '智云科技',
  summary: 'Vue3 项目开发、数据可视化、组件化设计与跨团队协作。'
})

const targetJobs = computed<JobOption[]>(() => {
  if (fileName.value.includes('模拟')) {
    return [
      {
        value: 'frontend',
        label: '高级前端工程师',
        score: mockMatchResult.score,
        dimensions: mockResume.skills.dimensions.map((dim, i) => ({
          name: dim,
          value: mockResume.skills.radarData.personalAbility[i]
        })),
        matched: mockMatchResult.matched,
        missing: mockMatchResult.missing
      }
    ]
  }
  
  return [
    {
      value: 'frontend',
      label: '高级前端工程师',
      score: 87,
      dimensions: [
        { name: '全栈开发', value: 65 },
        { name: '组件与工具', value: 92 },
        { name: '跨端开发', value: 58 },
        { name: '基础技能', value: 88 },
        { name: '前端开发框架', value: 95 },
        { name: '技术扩展', value: 72 },
        { name: '综合素养', value: 85 },
        { name: 'AI应用开发能力', value: 45 }
      ],
      matched: ['Vue3', 'TypeScript', 'ECharts', 'Vite', 'Git', '组件化开发'],
      missing: [
        { name: '性能优化实战', level: 'high', tip: '建议补充首屏加载、缓存策略与性能监控经验' },
        { name: '微前端架构', level: 'medium', tip: '大型项目常见的应用拆分与集成方案' },
        { name: 'Node.js 服务端', level: 'medium', tip: '提升全栈协作与 BFF 开发能力' }
      ]
    },
    {
      value: 'data',
      label: '数据分析师',
      score: 72,
      dimensions: [
        { name: '全栈开发', value: 35 },
        { name: '组件与工具', value: 68 },
        { name: '跨端开发', value: 30 },
        { name: '基础技能', value: 75 },
        { name: '前端开发框架', value: 45 },
        { name: '技术扩展', value: 55 },
        { name: '综合素养', value: 80 },
        { name: 'AI应用开发能力', value: 40 }
      ],
      matched: ['ECharts', '数据可视化', '沟通协作'],
      missing: [
        { name: 'SQL 查询与调优', level: 'high', tip: '数据岗位的通用基础能力' },
        { name: 'Python 数据分析', level: 'high', tip: '建议掌握 Pandas 与常用分析方法' },
        { name: '指标体系设计', level: 'medium', tip: '提升业务分析的系统性' }
      ]
    },
    {
      value: 'ai',
      label: 'AI 算法工程师',
      score: 65,
      dimensions: [
        { name: '算法基础', value: 55 },
        { name: '深度学习', value: 48 },
        { name: '工程实践', value: 62 },
        { name: '数学基础', value: 70 },
        { name: '数据处理', value: 68 },
        { name: '模型部署', value: 45 },
        { name: '综合素养', value: 75 },
        { name: '前沿追踪', value: 58 }
      ],
      matched: ['Python', '数据处理', '逻辑思维'],
      missing: [
        { name: '深度学习框架', level: 'high', tip: 'PyTorch/TensorFlow 核心能力' },
        { name: '大模型应用开发', level: 'high', tip: 'RAG、Agent、Prompt Engineering' },
        { name: '数学基础强化', level: 'medium', tip: '线性代数、概率论、优化方法' }
      ]
    },
    {
      value: 'backend',
      label: 'Java 后端工程师',
      score: 58,
      dimensions: [
        { name: 'Java 核心', value: 50 },
        { name: '框架能力', value: 45 },
        { name: '数据库', value: 55 },
        { name: '分布式', value: 40 },
        { name: '系统设计', value: 48 },
        { name: '运维部署', value: 42 },
        { name: '综合素养', value: 70 },
        { name: '安全意识', value: 38 }
      ],
      matched: ['SQL', '基础编程', '逻辑思维'],
      missing: [
        { name: 'Spring Boot 深入', level: 'high', tip: '自动配置、Starter 开发、性能调优' },
        { name: '分布式系统设计', level: 'high', tip: '微服务架构、消息队列、分布式事务' },
        { name: '高并发编程', level: 'medium', tip: 'JUC 并发包、线程池优化、锁机制' }
      ]
    },
    {
      value: 'product',
      label: '产品经理',
      score: 68,
      dimensions: [
        { name: '需求分析', value: 72 },
        { name: '用户研究', value: 65 },
        { name: '数据分析', value: 58 },
        { name: '项目管理', value: 70 },
        { name: '商业思维', value: 55 },
        { name: '技术理解', value: 60 },
        { name: '综合素养', value: 78 },
        { name: '行业洞察', value: 62 }
      ],
      matched: ['沟通协作', '需求分析', '逻辑思维'],
      missing: [
        { name: '数据驱动决策', level: 'high', tip: 'SQL 基础、指标体系、A/B 测试' },
        { name: '用户研究方法', level: 'medium', tip: '用户访谈、可用性测试、问卷设计' },
        { name: '技术理解能力', level: 'medium', tip: '前后端基础、API 概念、系统架构' }
      ]
    }
  ]
})

const currentJob = computed(() => targetJobs.value.find(item => item.value === targetJob.value)!)

const radarData = computed(() => ({
  dimensions: mockResume.skills.dimensions,
  jobStandard: mockResume.skills.radarData.jobStandard,
  personalAbility: mockResume.skills.radarData.personalAbility
}))

const scoreText = computed(() => {
  const score = currentJob.value.score
  return score >= 85 ? '匹配表现优异' : score >= 70 ? '具备较好潜力' : '建议重点提升'
})

function handleFile(file: any) {
  fileName.value = file.name
  parsed.value = true
  ElMessage.success('简历解析成功，正在生成诊断报告')
}

function importMockResume() {
  fileName.value = '林苑琪_模拟简历_前端开发.pdf'
  
  profile.value = {
    name: mockResume.basic.name,
    role: mockResume.basic.jobIntention,
    experience: '2026届应届生',
    education: mockResume.education.degree + ' · ' + mockResume.education.major,
    company: '广州应用科技学院',
    skills: mockResumeSkills,
    summary: mockResume.selfEvaluation
  }
  
  parsed.value = true
  ElMessage.success('模拟简历导入成功！')
}

function goToPreview() {
  router.push('/resume-demo')
}

function goToLearning() {
  ElMessage.success('正在生成个性化学习路径...')
  router.push({ path: '/learning', query: { job: targetJob.value } })
}
</script>

<style scoped>
.diagnosis-page {
  max-width: 1440px;
  margin: auto;
}

.page-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 22px;
  flex-wrap: wrap;
  gap: 12px;
}

.page-title h1 {
  font-size: 24px;
  margin: 0 0 7px;
}

.page-title p {
  font-size: 13px;
  color: #8C8C8C;
  margin: 0;
}

.title-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.target-select {
  width: 210px;
}

.panel {
  background: #fff;
  border: none;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
  background: #fff;
  border: 1px solid #F0EBE3;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}

.resume-hero-illustration {
  margin-bottom: 18px;
  border-radius: 16px;
  overflow: hidden;
}


/* 大型插画 */
.resume-hero-illustration {
  margin-bottom: 18px;
  border-radius: 16px;
  overflow: hidden;
}
.upload-panel {
min-height: 380px;
  padding: 32px 40px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 36px;
  align-items: center;
  background: linear-gradient(115deg, #fff, #f7faff);
}
.upload-copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.upload-ill-wrap {
  margin-bottom: 16px;
  border-radius: 12px;
  overflow: hidden;
  background: linear-gradient(135deg, #FDF5F0 0%, #F5F0EA 100%);
}

.upload-ill-wrap svg {
  display: block;
}

/* AI小人闪烁动效 */
.ai-blink circle:nth-child(2),
.ai-blink circle:nth-child(3) {
  animation: blink 0.8s ease-in-out infinite alternate;
}

@keyframes blink {
  0% { opacity: 0.4; }
  100% { opacity: 0.8; }
}

/* 匹配进度条动效 */
.match-bar {
  transition: width 0.6s ease;
}

.upload-badge {
  font-size: 12px;
  color: #D98B6E;
  background: #FDF5F0;
  padding: 5px 10px;
  border-radius: 6px;
  display: inline-block;
  margin-bottom: 12px;
  font-weight: 500;
}

.upload-copy h2 {
  font-size: 20px;
  margin: 0 0 8px;
  color: #333338;
}

.upload-copy > p {
  font-size: 13px;
  line-height: 1.7;
  color: #77777E;
  max-width: 320px;
}

.privacy-line {
  font-size: 12px;
  color: #8492a5;
  margin-top: 16px;
}

.privacy-line span {
  color: #66BB6A;
  font-weight: 700;
  margin-right: 5px;
}

.upload-badge {
  font-size: 12px;
  color: #E07B6D;
  background: #eaf2ff;
  padding: 5px 9px;
  border-radius: 4px;
}

.upload-copy h2 {
  font-size: 24px;
  margin: 16px 0 11px;
}

.upload-copy > p {
  font-size: 14px;
  line-height: 1.8;
  color: #728099;
  max-width: 390px;
}

.privacy-line {
  font-size: 12px;
  color: #8C8C8C;
  margin-top: 25px;
}

.privacy-line span {
  color: #66BB6A;
  font-weight: 700;
  margin-right: 5px;
}


.resume-upload :deep(.el-upload-dragger) {
  padding: 47px 15px;
  background: #fff;
  border-color: #E0D5CA;
}

.resume-upload :deep(.el-upload-dragger:hover) {
  border-color: #E07B6D;
}

.upload-illustration {
  font-size: 52px;
  color: #E07B6D;
  margin-bottom: 9px;
}

.parse-success {
  display: flex;
  align-items: center;
  gap: 11px;
  background: #effaf3;
  border: 1px solid #c6ead5;
  border-radius: 16px;
  padding: 12px 16px;
  margin-bottom: 18px;
}

.success-icon {
  background: #66BB6A;
  color: #fff;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 13px;
}

.parse-success b {
  font-size: 14px;
}

.parse-success p {
  font-size: 12px;
  color: #5a6a5a;
  margin: 4px 0 0;
}

.parse-success .el-button {
  margin-left: auto;
}

.diagnosis-grid {
  display: grid;
  grid-template-columns: 1.05fr 1.15fr 0.8fr;
  gap: 18px;
}

.profile-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.profile-head h2 {
  font-size: 19px;
  margin: 0 0 5px;
}

.profile-head p {
  font-size: 12px;
  color: #8C8C8C;
  margin: 0;
}

.profile-head .el-tag {
  margin-left: auto;
}

.info-list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  padding: 0 0 18px;
  border-bottom: 1px solid #F5F0EA;
}

.info-list div {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.info-list span {
  font-size: 12px;
  color: #8C8C8C;
}

.info-list b {
  font-size: 13px;
}

.profile-panel h3 {
  font-size: 14px;
  margin: 19px 0 11px;
}

.profile-panel h3 small {
  font-weight: 400;
  color: #8C8C8C;
}

.extracted-skills {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}

.profile-summary {
  font-size: 13px;
  line-height: 1.7;
  color: #555555;
  margin: 0;
}

.radar-panel {
  padding: 0;
  overflow: hidden;
}

.score-panel {
  text-align: center;
}

.score-panel h3 {
  margin: 0 0 13px;
  text-align: left;
  font-size: 16px;
}

.score-panel :deep(.el-progress__text) {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: baseline;
  gap: 2px;
}

.score-panel :deep(.el-progress__text strong) {
  font-size: 33px;
  color: #E07B6D;
}

.score-panel :deep(.el-progress__text span) {
  font-size: 13px;
  color: #E07B6D;
}

.score-panel :deep(.el-progress__text p) {
  width: 100%;
  font-size: 11px;
  color: #66BB6A;
  margin: 2px 0;
}

.score-caption {
  font-size: 12px;
  line-height: 1.6;
  color: #8C8C8C;
  margin: 4px auto 15px;
}

.score-breakdown {
  display: grid;
  gap: 8px;
  text-align: left;
}

.score-breakdown div {
  display: grid;
  grid-template-columns: 72px 1fr 22px;
  align-items: center;
  gap: 6px;
}

.score-breakdown span,
.score-breakdown b {
  font-size: 11px;
  color: #8C8C8C;
}

.score-breakdown b {
  text-align: right;
  color: #3D3D3D;
}

.skill-result {
  margin-top: 18px;
}

.skill-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
}

.skill-column {
  padding: 5px 24px 2px;
}

.skill-column + .skill-column {
  border-left: 1px solid #F5F0EA;
}

.column-title {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 15px;
}

.column-title i {
  width: 27px;
  height: 27px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #e8f8ef;
  color: #66BB6A;
  font-style: normal;
  font-weight: 700;
}

.missing .column-title i {
  background: #fff2df;
  color: #EF6C00;
}

.column-title b {
  display: block;
  font-size: 14px;
}

.column-title span {
  font-size: 12px;
  color: #8d99aa;
}

.diagnostic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.column-note {
  font-size: 12px;
  line-height: 1.7;
  color: #708172;
  background: #f2fbf5;
  padding: 9px 11px;
  border-radius: 10px;
  margin: 16px 0 0;
}

.gap-list {
  display: grid;
  gap: 11px;
}

.gap-list > div {
  display: flex;
  align-items: center;
  gap: 9px;
}

.gap-level {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #FFA726;
}

.gap-level.high {
  background: #E07B6D;
}

.gap-list b {
  font-size: 13px;
}

.gap-list p {
  font-size: 11px;
  color: #8C8C8C;
  margin: 3px 0 0;
}

.gap-list .el-tag {
  margin-left: auto;
  flex: none;
}

@media (max-width: 1100px) {
  .diagnosis-grid {
    grid-template-columns: 1fr 1fr;
  }
  
  .score-panel {
    grid-column: span 2;
  }
}

@media (max-width: 720px) {
  .page-title {
    flex-direction: column;
  }
  
  .title-actions {
    flex-wrap: wrap;
  }
  
  .upload-panel,
  .diagnosis-grid,
  .skill-columns {
    grid-template-columns: 1fr;
  }
  
  .resume-hero-illustration {
  margin-bottom: 18px;
  border-radius: 16px;
  overflow: hidden;
}


/* 大型插画 */
.resume-hero-illustration {
  margin-bottom: 18px;
  border-radius: 16px;
  overflow: hidden;
}
.upload-panel {
padding: 28px 20px;
    gap: 25px;
  }

.upload-badge {
  font-size: 12px;
  color: #D98B6E;
  background: #FDF5F0;
  padding: 5px 10px;
  border-radius: 6px;
  display: inline-block;
  margin-bottom: 12px;
  font-weight: 500;
}

.upload-copy h2 {
  font-size: 20px;
  margin: 0 0 8px;
  color: #333338;
}

.upload-copy > p {
  font-size: 13px;
  line-height: 1.7;
  color: #77777E;
  max-width: 320px;
}

.privacy-line {
  font-size: 12px;
  color: #8492a5;
  margin-top: 16px;
}

.privacy-line span {
  color: #66BB6A;
  font-weight: 700;
  margin-right: 5px;
}
  
  .target-select {
    width: 165px;
  }
  
  .score-panel {
    grid-column: auto;
  }
  
  .skill-column + .skill-column {
    border-left: 0;
    border-top: 1px solid #F5F0EA;
    margin-top: 16px;
    padding-top: 18px;
  }
}
</style>

