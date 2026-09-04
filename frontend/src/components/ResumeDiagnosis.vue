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
        <span class="upload-badge">简历解析</span>
        <h2>上传简历，开始能力诊断</h2>
        <p>支持 PDF、DOC、DOCX、TXT 格式。系统将提取教育、经历和技能信息，并自动匹配完整岗位目录。</p>
        <div class="privacy-line"><span>✓</span> 文件仅用于本次本地诊断，不会存储或对外共享</div>
      </div>
      <el-upload drag :auto-upload="false" :show-file-list="false" accept=".pdf,.doc,.docx,.txt" :on-change="handleFile" class="resume-upload">
        <el-icon class="upload-illustration"><UploadFilled /></el-icon>
        <div class="el-upload__text">将 PDF / Word 简历拖到这里<br/><em>或点击选择文件</em></div>
        <template #tip><div class="el-upload__tip">支持最大 10MB 的 PDF、DOC、DOCX、TXT 文件</div></template>
      </el-upload>
    </section>

    <section v-else class="parsed-view">
      <div class="parse-success">
        <span class="success-icon">✓</span>
        <div class="success-main"><b>{{ fileName }}</b><span>解析完成 · 已提取 {{ profile.skills.length }} 项技能</span></div>
        <span class="parse-quality-badge">{{ parseQuality }}%</span>
        <el-button text type="primary" @click="resetDiagnosis">重新上传</el-button>
      </div>

      <article class="panel split-card">
        <aside class="split-side">
          <div class="side-person">
            <el-avatar :size="54" class="side-avatar">{{ profile.name?.[0] || '个' }}</el-avatar>
            <div class="side-id"><h2>{{ profile.name || '个人简历' }}</h2><p>{{ profile.role || '未识别岗位' }}</p><span class="tag-ok">解析成功</span></div>
          </div>
          <section class="m-module">
            <h4 class="m-head">基本信息</h4>
            <dl class="info-rows">
              <div class="info-row"><dt>最高学历</dt><dd>{{ profile.education || '—' }}</dd></div>
              <div class="info-row"><dt>最近公司</dt><dd>{{ profile.company || '—' }}</dd></div>
              <div class="info-row"><dt>工作年限</dt><dd>{{ profile.experience || '—' }}</dd></div>
              <div class="info-row" v-if="profile.phone"><dt>联系电话</dt><dd>{{ profile.phone }}</dd></div>
              <div class="info-row" v-if="profile.location"><dt>所在城市</dt><dd>{{ profile.location }}</dd></div>
            </dl>
          </section>
          <section class="m-module">
            <h4 class="m-head">技能标签 <em>{{ profile.skills.length }}</em></h4>
            <div class="skill-flow">
              <el-tag v-for="skill in profile.skills" :key="skill" size="small" effect="plain">{{ skill }}</el-tag>
              <span v-if="!profile.skills.length" class="muted">暂无识别技能</span>
            </div>
          </section>
        </aside>

        <div class="split-main">
          <template v-if="(profile.projects && profile.projects.length) || (profile.honors && profile.honors.length)">
            <section class="m-module" v-if="profile.projects && profile.projects.length">
              <h4 class="m-head">项目经历 <em>{{ profile.projects.length }}</em></h4>
              <div class="exp-list">
                <div v-for="(pr, i) in profile.projects" :key="'p' + i" class="proj-item">
                  <div class="exp-title"><b>{{ pr.name }}</b><span v-if="pr.duration" class="exp-time">{{ pr.duration }}</span></div>
                  <ul v-if="pr.responsibilities && pr.responsibilities.length"><li v-for="(r, j) in pr.responsibilities" :key="j">{{ r }}</li></ul>
                </div>
              </div>
            </section>
            <section class="m-module" v-if="profile.honors && profile.honors.length">
              <h4 class="m-head">竞赛与荣誉 <em>{{ profile.honors.length }}</em></h4>
              <div class="exp-list">
                <div v-for="(h, i) in profile.honors" :key="'h' + i" class="honor-row"><b>{{ h.title }}</b><span v-if="h.time" class="exp-time">{{ h.time }}</span></div>
              </div>
            </section>
          </template>
          <div v-else class="empty-hint">当前简历未识别到项目经历与竞赛荣誉，可在下方岗位推荐中查看匹配度。</div>
        </div>
      </article>

      <section class="panel recommendations-panel">
        <div class="panel-head"><div><h3>自动匹配岗位</h3><p>系统已遍历完整岗位目录，固定展示至少 3 个推荐结果；点击卡片即可为对应岗位生成学习路径。</p></div><el-tag type="success" effect="plain">{{ recommendedJobs.length }} 个岗位</el-tag></div>
        <div v-if="recommendedJobs.length" class="recommendation-grid"><article v-for="(job, index) in recommendedJobs" :key="job.id" class="recommendation-card"><div class="recommendation-title"><div><small>推荐 {{ index + 1 }}</small><strong>{{ job.title }}</strong><em>{{ job.name_en || '' }}</em></div><el-tag size="small" effect="plain">{{ job.category || job.platform_label }}</el-tag></div><div class="recommendation-score"><b>{{ scoreText(job.score) }}%</b><span>展示匹配度</span></div><p>已匹配 {{ job.matched.length }} 项技能<span v-if="job.missing.length">，待补 {{ job.missing.length }} 项</span></p><el-button text class="recommendation-link" @click="selectRecommendation(job)">按此岗位生成学习路径<el-icon><ArrowRight /></el-icon></el-button></article></div>
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

function scoreText(value: number | string | undefined) { const n = Number(value || 0); return Number.isFinite(n) ? n.toFixed(2) : '—' }

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


.diagnosis-page .page-title { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.diagnosis-page .page-title h1 { margin: 0 0 4px; font-size: 22px; }
.diagnosis-page .page-title p { margin: 0; color: #8f8985; font-size: 12px; }
.diagnosis-page .title-actions { display: flex; gap: 10px; }
.parsed-view { display: flex; flex-direction: column; gap: 16px; }
.parse-success { display: flex; align-items: center; gap: 10px; margin: 0; padding: 9px 14px; border-radius: 10px; background: #eef7f0; }
.parse-success .success-icon { display: grid; width: 22px; height: 22px; place-items: center; border-radius: 50%; background: #67a37b; color: #fff; font-size: 12px; line-height: 1; flex: none; }
.success-main { display: flex; flex-direction: column; line-height: 1.35; min-width: 0; }
.success-main b { font-size: 13px; color: #3f7a58; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.success-main span { font-size: 11px; color: #6c8f78; }
.parse-success .parse-quality-badge { margin-left: auto; font-size: 11px; color: #3f7a58; background: rgba(103,163,123,.14); border-radius: 10px; padding: 2px 9px; flex: none; }
.parse-success .el-button { margin-left: 4px; flex: none; }
.split-card { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 0; padding: 0; overflow: hidden; }
.split-side { display: flex; flex-direction: column; gap: 20px; padding: 18px 16px; background: #fbf9f6; border-right: 1px solid var(--line); }
.side-person { display: flex; align-items: center; gap: 12px; }
.side-avatar { flex: none; background: var(--coral-soft); color: var(--coral-deep); font-size: 20px; font-weight: 600; border: 2px solid #fff; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.side-id { min-width: 0; }
.side-id h2 { margin: 0; font-size: 17px; line-height: 1.3; }
.side-id p { margin: 3px 0 0; color: #8f8985; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag-ok { display: inline-block; margin-top: 6px; padding: 1px 8px; border-radius: 20px; background: #e3f2e8; color: #3f7a58; font-size: 10px; }
.m-module { min-width: 0; }
.m-head { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; padding-left: 9px; border-left: 3px solid var(--coral); font-size: 14px; line-height: 1.3; }
.m-head em { margin-left: auto; padding: 1px 8px; border-radius: 10px; background: #f2ede7; color: #a5a09b; font-size: 11px; font-style: normal; }
.info-rows { display: flex; flex-direction: column; margin: 0; }
.info-row { display: flex; gap: 8px; padding: 6px 0; border-bottom: 1px dashed #ece6df; font-size: 12px; }
.info-row:last-child { border-bottom: none; }
.info-row dt { width: 66px; color: #a5a09b; flex: none; }
.info-row dd { margin: 0; color: var(--text); word-break: break-all; }
.skill-flow { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.skill-flow .el-tag { margin: 0; }
.split-main { display: flex; flex-direction: column; gap: 22px; min-width: 0; padding: 18px 20px; }
.exp-list { display: flex; flex-direction: column; gap: 10px; }
.proj-item { padding: 9px 12px; border: 1px solid var(--line); border-radius: 10px; background: #fff; }
.exp-title, .honor-row { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
.exp-title b, .honor-row b { font-size: 13px; color: var(--text); }
.exp-time { flex: none; color: #a5a09b; font-size: 11px; white-space: nowrap; }
.proj-item ul { margin: 6px 0 0; padding-left: 16px; color: #6f6a65; font-size: 12px; line-height: 1.75; }
.honor-row { padding: 6px 12px; border: 1px solid var(--line); border-radius: 10px; background: #fff; }
.empty-hint { padding: 24px; border: 1px dashed var(--line-strong); border-radius: 12px; color: #a29d99; font-size: 12px; text-align: center; }
@media (max-width: 900px) { .split-card { grid-template-columns: 1fr; } .split-side { border-right: none; border-bottom: 1px solid var(--line); } }
.diagnosis-page .page-title { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.diagnosis-page .page-title h1 { margin: 0 0 4px; font-size: 22px; }
.diagnosis-page .page-title p { margin: 0; color: #8f8985; font-size: 12px; }
.diagnosis-page .title-actions { display: flex; gap: 10px; }
.parsed-view { display: flex; flex-direction: column; gap: 16px; }
.parse-success { display: flex; align-items: center; gap: 10px; margin: 0; padding: 9px 14px; border-radius: 10px; background: #eef7f0; }
.parse-success .success-icon { display: grid; width: 22px; height: 22px; place-items: center; border-radius: 50%; background: #67a37b; color: #fff; font-size: 12px; line-height: 1; flex: none; }
.success-main { display: flex; flex-direction: column; line-height: 1.35; min-width: 0; }
.success-main b { font-size: 13px; color: #3f7a58; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.success-main span { font-size: 11px; color: #6c8f78; }
.parse-success .parse-quality-badge { margin-left: auto; font-size: 11px; color: #3f7a58; background: rgba(103,163,123,.14); border-radius: 10px; padding: 2px 9px; flex: none; }
.parse-success .el-button { margin-left: 4px; flex: none; }
.split-card { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 0; padding: 0; overflow: hidden; }
.split-side { display: flex; flex-direction: column; gap: 20px; padding: 18px 16px; background: #fbf9f6; border-right: 1px solid var(--line); }
.side-person { display: flex; align-items: center; gap: 12px; }
.side-avatar { flex: none; background: var(--coral-soft); color: var(--coral-deep); font-size: 20px; font-weight: 600; border: 2px solid #fff; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.side-id { min-width: 0; }
.side-id h2 { margin: 0; font-size: 17px; line-height: 1.3; }
.side-id p { margin: 3px 0 0; color: #8f8985; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag-ok { display: inline-block; margin-top: 6px; padding: 1px 8px; border-radius: 20px; background: #e3f2e8; color: #3f7a58; font-size: 10px; }
.m-module { min-width: 0; }
.m-head { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; padding-left: 9px; border-left: 3px solid var(--coral); font-size: 14px; line-height: 1.3; }
.m-head em { margin-left: auto; padding: 1px 8px; border-radius: 10px; background: #f2ede7; color: #a5a09b; font-size: 11px; font-style: normal; }
.info-rows { display: flex; flex-direction: column; margin: 0; }
.info-row { display: flex; gap: 8px; padding: 6px 0; border-bottom: 1px dashed #ece6df; font-size: 12px; }
.info-row:last-child { border-bottom: none; }
.info-row dt { width: 66px; color: #a5a09b; flex: none; }
.info-row dd { margin: 0; color: var(--text); word-break: break-all; }
.skill-flow { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.skill-flow .el-tag { margin: 0; }
.split-main { display: flex; flex-direction: column; gap: 22px; min-width: 0; padding: 18px 20px; }
.exp-list { display: flex; flex-direction: column; gap: 10px; }
.proj-item { padding: 9px 12px; border: 1px solid var(--line); border-radius: 10px; background: #fff; }
.exp-title, .honor-row { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
.exp-title b, .honor-row b { font-size: 13px; color: var(--text); }
.exp-time { flex: none; color: #a5a09b; font-size: 11px; white-space: nowrap; }
.proj-item ul { margin: 6px 0 0; padding-left: 16px; color: #6f6a65; font-size: 12px; line-height: 1.75; }
.honor-row { padding: 6px 12px; border: 1px solid var(--line); border-radius: 10px; background: #fff; }
.empty-hint { padding: 24px; border: 1px dashed var(--line-strong); border-radius: 12px; color: #a29d99; font-size: 12px; text-align: center; }
@media (max-width: 900px) { .split-card { grid-template-columns: 1fr; } .split-side { border-right: none; border-bottom: 1px solid var(--line); } }
</style>

