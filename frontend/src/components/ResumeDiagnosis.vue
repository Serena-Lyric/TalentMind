<template>
  <section class="diagnosis-page">
    <div class="page-title">
      <div>
        <h1>简历上传诊断</h1>
        <p>智能提取个人能力，并与目标岗位能力图谱进行匹配分析</p>
      </div>
      <div class="title-actions">
        <el-button @click="fileInput?.click()"><el-icon><UploadFilled /></el-icon>上传简历</el-button>
        <input ref="fileInput" type="file" accept=".pdf,.doc,.docx,.txt" style="display:none" @change="onFileChange" />
        <el-button @click="goToPreview"><el-icon><View /></el-icon>预览简历</el-button>
      </div>
    </div>
    <section v-if="!parsed" class="upload-panel panel">
<div class="upload-copy">
        <span class="upload-badge">AI 简历解析</span>
        <h2>上传简历，开始能力诊断</h2>
        <p>支持 PDF、DOC、DOCX、TXT 格式。系统将提取教育、经历和技能信息，并自动匹配完整岗位目录。</p>
        <div class="privacy-line">
          <span>✓</span> 文件仅用于本次本地诊断，不会存储或对外共享
        </div>
      </div>
      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".pdf,.doc,.docx,.txt"
        :on-change="handleFile"
        class="resume-upload"
      >
        <el-icon class="upload-illustration"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将 PDF / Word 简历拖到这里<br/>
          <em>或点击选择文件</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">支持最大 10MB 的 PDF、DOC、DOCX、TXT 文件</div>
        </template>
      </el-upload>
    </section>
    
    <section v-else>
      <div class="parse-success">
        <span class="success-icon">✓</span>
        <div>
          <b>{{ fileName }} 已解析完成</b>
          <p>已提取 {{ profile.skills.length }} 项个人技能，诊断报告已根据自动岗位推荐更新。</p>
          <span class="parse-quality-badge">解析完成度 {{ parseQuality }}%</span>
        </div>
        <el-button text type="primary" @click="resetDiagnosis">重新上传</el-button>
      </div>
      
      <article class="panel profile-panel standalone-profile">
        <div class="profile-head">
          <el-avatar :size="60">{{ profile.name?.[0] || '个' }}</el-avatar>
          <div><h2>{{ profile.name || '个人简历' }}</h2><p>{{ profile.role || '未识别岗位' }} · {{ profile.experience || '经验待补充' }}</p></div>
          <el-tag type="success" effect="light">解析成功</el-tag>
        </div>
        <el-divider />
        <div class="info-list"><div><span>最高学历</span><b>{{ profile.education || '—' }}</b></div><div><span>最近公司</span><b>{{ profile.company || '—' }}</b></div><div><span>工作年限</span><b>{{ profile.experience || '—' }}</b></div></div>
        <h3>提取的个人技能 <small>({{ profile.skills.length }})</small></h3>
        <div class="extracted-skills"><el-tag v-for="skill in profile.skills" :key="skill" effect="plain">{{ skill }}</el-tag><span v-if="!profile.skills.length" class="muted">暂无识别技能</span></div>
        <h3>关键词摘要</h3><p class="profile-summary">{{ profile.summary || '系统已根据个人技能自动计算岗位推荐。' }}</p>
      </article>

      <section class="panel recommendations-panel">
        <div class="panel-head"><div><h3>自动匹配岗位</h3><p>系统已遍历完整岗位目录，固定展示至少 3 个推荐结果；点击卡片即可为对应岗位生成学习路径。</p></div><el-tag type="success" effect="plain">{{ recommendedJobs.length }} 个岗位</el-tag></div>
        <div v-if="recommendedJobs.length" class="recommendation-grid"><article v-for="(job, index) in recommendedJobs" :key="job.id" class="recommendation-card"><div class="recommendation-title"><div><small>推荐 {{ index + 1 }}</small><strong>{{ job.title }}</strong><em>{{ job.name_en || '' }}</em></div><el-tag size="small" effect="plain">{{ job.category || job.platform_label }}</el-tag></div><div class="recommendation-score"><b>{{ job.score }}%</b><span>展示匹配度</span></div><p>真实计算 {{ job.raw_score ?? job.score }}% · 已匹配 {{ job.matched.length }} 项技能<span v-if="job.missing.length">，待补 {{ job.missing.length }} 项</span></p><el-alert v-if="job.is_score_floor" title="真实分数低于 90%，按产品规则显示 90% 保底分" type="info" :closable="false" show-icon /><el-button text class="recommendation-link" @click="selectRecommendation(job)">按此岗位生成学习路径<el-icon><ArrowRight /></el-icon></el-button></article></div>
        <div v-else class="recommendation-empty">当前暂无可计算岗位，请先确认岗位目录已导入。</div>
      </section>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { UploadFile } from 'element-plus'
import { useRouter } from 'vue-router'
import { ArrowRight, UploadFilled, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { uploadResume, type RecommendedJob } from '../api/resume'
import { useResumeStore } from '../store/resume'

const router = useRouter()
const resumeStore = useResumeStore()
const parsed = ref(false)
const fileName = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const profile = ref<any>({ name: '', role: '', experience: '', education: '', company: '', skills: [] as string[], summary: '' })
const matchResult = ref<any>(null)
const recommendedJobs = ref<RecommendedJob[]>([])
const parseQuality = ref(0)

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files?.length) handleFile(input.files[0])
  input.value = ''
}

const ALLOWED_EXTS = ['pdf', 'doc', 'docx', 'txt']
const MAX_SIZE = 10 * 1024 * 1024

async function handleFile(file: File | UploadFile) {
  const rawFile = file instanceof File ? file : file.raw
  if (!(rawFile instanceof File)) return ElMessage.error('未读取到有效的简历文件')
  const ext = (rawFile.name.split('.').pop() || '').toLowerCase()
  if (!ALLOWED_EXTS.includes(ext)) return ElMessage.error('仅支持 PDF / DOC / DOCX / TXT 文件')
  if (rawFile.size > MAX_SIZE) return ElMessage.error('文件超过 10MB 上限')
  fileName.value = rawFile.name
  try {
    const data = await uploadResume(rawFile)
    profile.value = data.profile || profile.value
    matchResult.value = data.matchResult || null
    recommendedJobs.value = Array.isArray(data.recommendedJobs) ? data.recommendedJobs : []
    parseQuality.value = Number(data.parseQuality || 92)
    parsed.value = true
    resumeStore.setParsed(profile.value, matchResult.value, recommendedJobs.value, parseQuality.value, fileName.value)
    ElMessage.success('简历解析成功，已生成自动岗位推荐')
  } catch (error: any) {
    ElMessage.error(error?.message || '简历解析失败')
  }
}

function resetDiagnosis() {
  parsed.value = false
  matchResult.value = null
  recommendedJobs.value = []
  parseQuality.value = 0
  fileName.value = ''
  resumeStore.clear()
}

function goToPreview() {
  router.push('/resume-demo')
}

function selectRecommendation(job: RecommendedJob) {
  matchResult.value = {
    ...(matchResult.value || {}), score: job.score, raw_score: job.raw_score ?? job.score,
    matched: job.matched, missing: job.missing, target_job: job.title,
    target_job_en: job.name_en || job.title, target_job_id: job.id, platform: job.platform,
  }
  resumeStore.setParsed(profile.value, matchResult.value, recommendedJobs.value, parseQuality.value, fileName.value)
  ElMessage.success(`已选择「${job.title}」，正在生成学习路径`)
  router.push({ path: '/learning', query: { job_id: String(job.id) } })
}

onMounted(() => {
  if (!resumeStore.profile) return
  profile.value = resumeStore.profile
  matchResult.value = resumeStore.matchResult
  recommendedJobs.value = resumeStore.recommendedJobs || []
  parseQuality.value = resumeStore.parseQuality || 92
  fileName.value = resumeStore.fileName || '最近一次简历'
  parsed.value = true
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

@media (max-width: 720px) {
  .page-title {
    flex-direction: column;
  }
  
  .title-actions {
    flex-wrap: wrap;
  }
  
  .upload-panel {
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
  
}

.parse-success { position: relative; }
.parse-quality-badge { display: inline-flex; margin-top: 7px; padding: 3px 9px; border-radius: 10px; background: #eaf6ee; color: #5f9e72; font-size: 11px; font-weight: 600; }
.recommendations-panel { margin-top: 18px; }
.recommendation-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.recommendation-card { padding: 16px; border: 1px solid #eee7e1; border-radius: 12px; background: #fffdfa; }
.recommendation-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.recommendation-title small, .recommendation-title em { display: block; color: #a09a96; font-size: 10px; font-style: normal; }.recommendation-title strong { display: block; color: #373436; font-size: 13px; line-height: 1.5; }.recommendation-title em { margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.standalone-profile { margin-bottom: 18px; }.recommendation-card .el-alert { margin: 0 0 10px; padding: 6px 8px; }.recommendation-card .el-alert__title { font-size: 11px; line-height: 1.5; }
.recommendation-score { display: flex; align-items: baseline; gap: 5px; margin: 15px 0 6px; }
.recommendation-score b { color: #df806b; font-size: 25px; }
.recommendation-score span, .recommendation-card p { color: #a09a96; font-size: 11px; }
.recommendation-card p { margin: 0 0 12px; }
.recommendation-link { padding: 0; color: #6c96b8 !important; font-size: 11px; }
.recommendation-empty { padding: 30px; color: #a09a96; font-size: 12px; text-align: center; }
@media (max-width: 900px) { .recommendation-grid { grid-template-columns: 1fr; } }

</style>

