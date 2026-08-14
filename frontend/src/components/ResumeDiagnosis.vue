<template>
  <section class="diagnosis-page">
    <div class="page-title">
      <div>
        <h1>简历上传诊断</h1>
        <p>智能提取个人能力，并与目标岗位能力图谱进行匹配分析</p>
      </div>
      <div class="title-actions">
        <el-button @click="fileInput?.click()">
          <el-icon><UploadFilled /></el-icon>上传简历
        </el-button>
        <input ref="fileInput" type="file" accept=".pdf,.doc,.docx,.txt" style="display:none" @change="onFileChange" />
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
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Aim, UploadFilled, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { uploadResume, getTargetJobs } from '../api/resume'
import AbilityRadar from './AbilityRadar.vue'

interface MissingSkill {
  name: string
  level: 'high' | 'medium'
  tip: string
}

interface JobOption {
  value: string
  label: string
  score: number
  dimensions: { name: string; value: number }[]
  matched: string[]
  missing: MissingSkill[]
}

const router = useRouter()
const parsed = ref(false)
const fileName = ref('')
const targetJob = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const profile = ref<any>({
  name: '', role: '', experience: '', education: '', company: '',
  skills: [] as string[], summary: '',
})
const matchResult = ref<any>(null)
const targetJobs = ref<JobOption[]>([])

const currentJob = computed<JobOption>(() => {
  const base = targetJobs.value.find((item: any) => String(item.value) === String(targetJob.value))
  if (!base) return { value: '', label: '未选择目标岗位', score: 0, matched: [], missing: [], dimensions: [] }
  const mr = matchResult.value
  if (mr && mr.target_job && (base.label === mr.target_job || String(base.value) === String(mr.target_job))) {
    return { ...base, score: mr.score ?? base.score, matched: mr.matched || [], missing: mr.missing || [], dimensions: base.dimensions || [] }
  }
  return { ...base, matched: base.matched || [], missing: base.missing || [], dimensions: base.dimensions || [] }
})

const radarData = computed(() => ({
  dimensions: [] as string[],
  jobStandard: [] as number[],
  personalAbility: [] as number[],
}))

const scoreText = computed(() => {
  const score = currentJob.value?.score ?? 0
  return score >= 85 ? '匹配表现优异' : score >= 70 ? '具备较好潜力' : '建议重点提升'
})

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) handleFile(input.files[0])
  input.value = ''
}

async function handleFile(file: any) {
  fileName.value = file.name
  try {
    const data = await uploadResume(file)
    if (data?.profile) profile.value = data.profile
    if (data?.matchResult) {
      matchResult.value = data.matchResult
      if (data.matchResult.target_job) {
        const found = targetJobs.value.find((j: any) => j.label === data.matchResult.target_job)
        if (found) targetJob.value = String(found.value)
      }
    }
    parsed.value = true
    ElMessage.success('简历解析成功，正在生成诊断报告')
  } catch (e: any) {
    ElMessage.error(e?.message || '简历解析失败')
  }
}

function goToPreview() {
  router.push('/resume-demo')
}

function goToLearning() {
  ElMessage.success('正在生成个性化学习路径...')
  router.push({ path: '/learning', query: { job: targetJob.value } })
}

onMounted(async () => {
  try {
    const list = await getTargetJobs()
    if (Array.isArray(list) && list.length) {
      targetJobs.value = list.map((j: any) => ({
        value: String(j.value), label: j.label, score: j.score || 0,
        dimensions: [], matched: [], missing: [],
      }))
      targetJob.value = String(list[0].value)
    }
  } catch (e) { /* 忽略 */ }
})
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

