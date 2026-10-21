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
        <img class="resume-cutout" src="/resume-nebula-girl-cutout.png" alt="" aria-hidden="true" />
        <aside class="resume-copy-bubble" aria-label="简历解析说明">
          <span class="upload-badge">简历解析</span>
          <h2>上传简历，开始能力诊断</h2>
          <p>支持 PDF、DOC、DOCX、TXT 格式。系统将提取教育、经历和技能信息，并自动匹配完整岗位目录。</p>
          <div class="privacy-line"><span>✓</span> 文件仅用于本次本地诊断，不会存储或对外共享</div>
        </aside>
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
  border: 1px solid #D9E2E7;
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
  background: linear-gradient(115deg, #fff, #E8F0FA);
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
  background: linear-gradient(135deg, #F8FAFB 0%, #F8FAFB 100%);
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
  color: #247CA2;
  background: #F8FAFB;
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
  color: #55B88D;
  font-weight: 700;
  margin-right: 5px;
}

.upload-badge {
  font-size: 12px;
  color: #247CA2;
  background: #E8F0FA;
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
  color: #55B88D;
  font-weight: 700;
  margin-right: 5px;
}


.resume-upload :deep(.el-upload-dragger) {
  padding: 47px 15px;
  background: #fff;
  border-color: #D9E2E7;
}

.resume-upload :deep(.el-upload-dragger:hover) {
  border-color: #247CA2;
}

.upload-illustration {
  font-size: 52px;
  color: #247CA2;
  margin-bottom: 9px;
}

.parse-success {
  display: flex;
  align-items: center;
  gap: 11px;
  background: #E7F5EF;
  border: 1px solid #E7F5EF;
  border-radius: 16px;
  padding: 12px 16px;
  margin-bottom: 18px;
}

.success-icon {
  background: #55B88D;
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
  color: #247CA2;
  background: #F8FAFB;
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
  color: #55B88D;
  font-weight: 700;
  margin-right: 5px;
}

  .target-select {
    width: 165px;
  }

}

.parse-success { position: relative; }
.parse-quality-badge { display: inline-flex; margin-top: 7px; padding: 3px 9px; border-radius: 10px; background: #eaf6ee; color: #55B88D; font-size: 11px; font-weight: 600; }
.recommendations-panel { margin-top: 18px; }
.recommendation-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.recommendation-card { padding: 16px; border: 1px solid #D9E2E7; border-radius: 12px; background: #FFFFFF; }
.recommendation-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.recommendation-title small, .recommendation-title em { display: block; color: #69808E; font-size: 10px; font-style: normal; }.recommendation-title strong { display: block; color: #172735; font-size: 13px; line-height: 1.5; }.recommendation-title em { margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.standalone-profile { margin-bottom: 18px; }.recommendation-card .el-alert { margin: 0 0 10px; padding: 6px 8px; }.recommendation-card .el-alert__title { font-size: 11px; line-height: 1.5; }
.recommendation-score { display: flex; align-items: baseline; gap: 5px; margin: 15px 0 6px; }
.recommendation-score b { color: #D25B5B; font-size: 25px; }
.recommendation-score span, .recommendation-card p { color: #69808E; font-size: 11px; }
.recommendation-card p { margin: 0 0 12px; }
.recommendation-link { padding: 0; color: #6c96b8 !important; font-size: 11px; }
.recommendation-empty { padding: 30px; color: #69808E; font-size: 12px; text-align: center; }
@media (max-width: 900px) { .recommendation-grid { grid-template-columns: 1fr; } }


.diagnosis-page .page-title { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.diagnosis-page .page-title h1 { margin: 0 0 4px; font-size: 22px; }
.diagnosis-page .page-title p { margin: 0; color: #69808E; font-size: 12px; }
.diagnosis-page .title-actions { display: flex; gap: 10px; }
.parsed-view { display: flex; flex-direction: column; gap: 16px; }
.parse-success { display: flex; align-items: center; gap: 10px; margin: 0; padding: 9px 14px; border-radius: 10px; background: #E7F5EF; }
.parse-success .success-icon { display: grid; width: 22px; height: 22px; place-items: center; border-radius: 50%; background: #55B88D; color: #fff; font-size: 12px; line-height: 1; flex: none; }
.success-main { display: flex; flex-direction: column; line-height: 1.35; min-width: 0; }
.success-main b { font-size: 13px; color: #2D8967; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.success-main span { font-size: 11px; color: #69808E; }
.parse-success .parse-quality-badge { margin-left: auto; font-size: 11px; color: #2D8967; background: rgba(103,163,123,.14); border-radius: 10px; padding: 2px 9px; flex: none; }
.parse-success .el-button { margin-left: 4px; flex: none; }
.split-card { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 0; padding: 0; overflow: hidden; }
.split-side { display: flex; flex-direction: column; gap: 20px; padding: 18px 16px; background: #F8FAFB; border-right: 1px solid var(--line); }
.side-person { display: flex; align-items: center; gap: 12px; }
.side-avatar { flex: none; background: var(--coral-soft); color: var(--coral-deep); font-size: 20px; font-weight: 600; border: 2px solid #fff; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.side-id { min-width: 0; }
.side-id h2 { margin: 0; font-size: 17px; line-height: 1.3; }
.side-id p { margin: 3px 0 0; color: #69808E; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag-ok { display: inline-block; margin-top: 6px; padding: 1px 8px; border-radius: 20px; background: #e3f2e8; color: #2D8967; font-size: 10px; }
.m-module { min-width: 0; }
.m-head { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; padding-left: 9px; border-left: 3px solid var(--coral); font-size: 14px; line-height: 1.3; }
.m-head em { margin-left: auto; padding: 1px 8px; border-radius: 10px; background: #EEF3F6; color: #69808E; font-size: 11px; font-style: normal; }
.info-rows { display: flex; flex-direction: column; margin: 0; }
.info-row { display: flex; gap: 8px; padding: 6px 0; border-bottom: 1px dashed #D9E2E7; font-size: 12px; }
.info-row:last-child { border-bottom: none; }
.info-row dt { width: 66px; color: #69808E; flex: none; }
.info-row dd { margin: 0; color: var(--text); word-break: break-all; }
.skill-flow { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.skill-flow .el-tag { margin: 0; }
.split-main { display: flex; flex-direction: column; gap: 22px; min-width: 0; padding: 18px 20px; }
.exp-list { display: flex; flex-direction: column; gap: 10px; }
.proj-item { padding: 9px 12px; border: 1px solid var(--line); border-radius: 10px; background: #fff; }
.exp-title, .honor-row { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
.exp-title b, .honor-row b { font-size: 13px; color: var(--text); }
.exp-time { flex: none; color: #69808E; font-size: 11px; white-space: nowrap; }
.proj-item ul { margin: 6px 0 0; padding-left: 16px; color: #6f6a65; font-size: 12px; line-height: 1.75; }
.honor-row { padding: 6px 12px; border: 1px solid var(--line); border-radius: 10px; background: #fff; }
.empty-hint { padding: 24px; border: 1px dashed var(--line-strong); border-radius: 12px; color: #69808E; font-size: 12px; text-align: center; }
@media (max-width: 900px) { .split-card { grid-template-columns: 1fr; } .split-side { border-right: none; border-bottom: 1px solid var(--line); } }
.diagnosis-page .page-title { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.diagnosis-page .page-title h1 { margin: 0 0 4px; font-size: 22px; }
.diagnosis-page .page-title p { margin: 0; color: #69808E; font-size: 12px; }
.diagnosis-page .title-actions { display: flex; gap: 10px; }
.parsed-view { display: flex; flex-direction: column; gap: 16px; }
.parse-success { display: flex; align-items: center; gap: 10px; margin: 0; padding: 9px 14px; border-radius: 10px; background: #E7F5EF; }
.parse-success .success-icon { display: grid; width: 22px; height: 22px; place-items: center; border-radius: 50%; background: #55B88D; color: #fff; font-size: 12px; line-height: 1; flex: none; }
.success-main { display: flex; flex-direction: column; line-height: 1.35; min-width: 0; }
.success-main b { font-size: 13px; color: #2D8967; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.success-main span { font-size: 11px; color: #69808E; }
.parse-success .parse-quality-badge { margin-left: auto; font-size: 11px; color: #2D8967; background: rgba(103,163,123,.14); border-radius: 10px; padding: 2px 9px; flex: none; }
.parse-success .el-button { margin-left: 4px; flex: none; }
.split-card { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 0; padding: 0; overflow: hidden; }
.split-side { display: flex; flex-direction: column; gap: 20px; padding: 18px 16px; background: #F8FAFB; border-right: 1px solid var(--line); }
.side-person { display: flex; align-items: center; gap: 12px; }
.side-avatar { flex: none; background: var(--coral-soft); color: var(--coral-deep); font-size: 20px; font-weight: 600; border: 2px solid #fff; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.side-id { min-width: 0; }
.side-id h2 { margin: 0; font-size: 17px; line-height: 1.3; }
.side-id p { margin: 3px 0 0; color: #69808E; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag-ok { display: inline-block; margin-top: 6px; padding: 1px 8px; border-radius: 20px; background: #e3f2e8; color: #2D8967; font-size: 10px; }
.m-module { min-width: 0; }
.m-head { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; padding-left: 9px; border-left: 3px solid var(--coral); font-size: 14px; line-height: 1.3; }
.m-head em { margin-left: auto; padding: 1px 8px; border-radius: 10px; background: #EEF3F6; color: #69808E; font-size: 11px; font-style: normal; }
.info-rows { display: flex; flex-direction: column; margin: 0; }
.info-row { display: flex; gap: 8px; padding: 6px 0; border-bottom: 1px dashed #D9E2E7; font-size: 12px; }
.info-row:last-child { border-bottom: none; }
.info-row dt { width: 66px; color: #69808E; flex: none; }
.info-row dd { margin: 0; color: var(--text); word-break: break-all; }
.skill-flow { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.skill-flow .el-tag { margin: 0; }
.split-main { display: flex; flex-direction: column; gap: 22px; min-width: 0; padding: 18px 20px; }
.exp-list { display: flex; flex-direction: column; gap: 10px; }
.proj-item { padding: 9px 12px; border: 1px solid var(--line); border-radius: 10px; background: #fff; }
.exp-title, .honor-row { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
.exp-title b, .honor-row b { font-size: 13px; color: var(--text); }
.exp-time { flex: none; color: #69808E; font-size: 11px; white-space: nowrap; }
.proj-item ul { margin: 6px 0 0; padding-left: 16px; color: #6f6a65; font-size: 12px; line-height: 1.75; }
.honor-row { padding: 6px 12px; border: 1px solid var(--line); border-radius: 10px; background: #fff; }
.empty-hint { padding: 24px; border: 1px dashed var(--line-strong); border-radius: 12px; color: #69808E; font-size: 12px; text-align: center; }
@media (max-width: 900px) { .split-card { grid-template-columns: 1fr; } .split-side { border-right: none; border-bottom: 1px solid var(--line); } }
/* 简历上传主视觉：使用项目统一的星云女孩插画替代说明文字 */
.upload-panel {
  min-height: clamp(390px, 34vw, 500px);
  grid-template-columns: minmax(0, 1.18fr) minmax(360px, .82fr);
  gap: clamp(28px, 3vw, 48px);
  padding: clamp(26px, 3vw, 42px);
  align-items: stretch;
  overflow: hidden;
}
.upload-copy {
  position: relative;
  min-width: 0;
  min-height: 310px;
  display: grid;
  place-items: center;
  overflow: hidden;
  border: 1px solid rgba(120, 144, 187, .12);
  border-radius: 18px;
  background:
    radial-gradient(circle at 16% 18%, rgba(155, 99, 217, .08), transparent 27%),
    radial-gradient(circle at 84% 32%, rgba(52, 199, 176, .08), transparent 31%),
    linear-gradient(135deg, rgba(255,255,255,.92), rgba(235,243,252,.72));
  box-shadow: inset 0 1px 0 rgba(255,255,255,.9), 0 10px 28px rgba(71, 91, 138, .06);
}
.resume-upload-hero {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 310px;
  object-fit: contain;
  object-position: center;
  transform: scale(1.015);
}
.resume-upload {
  align-self: center;
  min-width: 0;
}
.resume-upload :deep(.el-upload),
.resume-upload :deep(.el-upload-dragger) {
  width: 100%;
}
.resume-upload :deep(.el-upload-dragger) {
  min-height: 250px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  padding: 42px 24px;
  transition: border-color .2s ease, background-color .2s ease, box-shadow .2s ease;
}
.resume-upload :deep(.el-upload-dragger:hover) {
  background: rgba(248, 251, 255, .96);
  border-color: rgba(54, 70, 182, .48);
  box-shadow: 0 12px 28px rgba(54, 70, 182, .08);
}
.resume-upload :deep(.el-upload__tip) {
  margin-top: 13px;
  text-align: center;
}
@media (max-width: 900px) {
  .upload-panel {
    grid-template-columns: 1fr;
    min-height: 0;
    gap: 22px;
    padding: 22px;
  }
  .upload-copy {
    min-height: 0;
    aspect-ratio: 16 / 9;
  }
  .resume-upload-hero {
    min-height: 0;
  }
  .resume-upload :deep(.el-upload-dragger) {
    min-height: 220px;
    padding: 34px 18px;
  }
}

/* 简历人物抠图与常驻说明气泡 */
.upload-copy {
  position: relative;
  min-width: 0;
  min-height: 330px;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: clamp(2px, .8vw, 14px);
  overflow: visible;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.resume-cutout {
  position: relative;
  z-index: 10;
  display: block;
  width: 43%;
  max-width: 315px;
  height: 100%;
  max-height: 395px;
  flex: none;
  object-fit: contain;
  object-position: center bottom;
  filter: contrast(1.06) saturate(1.09) brightness(1.02) drop-shadow(0 18px 23px rgba(77, 92, 158, .18));
}
.resume-copy-bubble {
  position: relative;
  z-index: 5;
  width: min(57%, 500px);
  padding: clamp(20px, 2.2vw, 30px);
  border: 1px solid rgba(111, 132, 181, .18);
  border-radius: 22px;
  background: rgba(255, 255, 255, .9);
  box-shadow: 0 18px 42px rgba(68, 87, 138, .1), inset 0 1px 0 rgba(255, 255, 255, .95);
  backdrop-filter: blur(8px);
}
.resume-copy-bubble::before,
.resume-copy-bubble::after {
  content: "";
  position: absolute;
  top: 50%;
  left: -11px;
  width: 0;
  height: 0;
  border-style: solid;
  transform: translateY(-50%);
}
.resume-copy-bubble::before {
  border-width: 11px 12px 11px 0;
  border-color: transparent rgba(111, 132, 181, .18) transparent transparent;
}
.resume-copy-bubble::after {
  left: -9px;
  border-width: 10px 11px 10px 0;
  border-color: transparent rgba(255, 255, 255, .94) transparent transparent;
}
.resume-copy-bubble .upload-badge {
  margin-bottom: 11px;
}
.resume-copy-bubble h2 {
  margin: 0 0 10px;
  font-size: clamp(19px, 1.55vw, 24px);
}
.resume-copy-bubble > p {
  max-width: none;
  margin: 0;
}
.resume-copy-bubble .privacy-line {
  margin-top: 19px;
}
@media (max-width: 900px) {
  .upload-copy {
    min-height: 370px;
    flex-direction: column;
    gap: 2px;
    padding: 8px 4px 16px;
  }
  .resume-cutout {
    width: 190px;
    height: 185px;
    max-height: none;
  }
  .resume-copy-bubble {
    width: 100%;
    max-width: 520px;
    padding: 17px 18px;
    border-radius: 18px;
  }
  .resume-copy-bubble::before {
    top: -10px;
    left: 50%;
    border-width: 0 10px 11px 10px;
    border-color: transparent transparent rgba(111, 132, 181, .18) transparent;
    transform: translateX(-50%);
  }
  .resume-copy-bubble::after {
    top: -8px;
    left: 50%;
    border-width: 0 9px 10px 9px;
    border-color: transparent transparent rgba(255, 255, 255, .94) transparent;
    transform: translateX(-50%);
  }
  .resume-copy-bubble h2 {
    font-size: 18px;
  }
  .resume-copy-bubble > p {
    font-size: 12.5px;
    line-height: 1.65;
  }
  .resume-copy-bubble .privacy-line {
    margin-top: 13px;
  }
}

</style>