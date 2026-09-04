<template>
  <section class="learning-roadmap panel" v-loading="loading">
    <div class="roadmap-header">
      <div><h2>技能学习路径</h2><p>学习目标来自简历自动匹配结果，点击推荐岗位后自动生成对应路径。</p></div>
      <el-button class="btn-coral" :disabled="!hasResume || !selectedJobId" :loading="generating" @click="generatePath"><el-icon><MagicStick /></el-icon>重新生成</el-button>
    </div>

    <div v-if="!hasResume" class="roadmap-empty compact"><div class="empty-symbol"><el-icon><Document /></el-icon></div><h3>请先完成简历解析</h3><p>解析简历后系统会自动给出至少 3 个岗位推荐；从推荐卡片进入即可绑定学习目标。</p><el-button class="btn-soft" @click="router.push('/resume')">前往简历解析</el-button></div>

    <template v-else>
      <div class="roadmap-config">
        <div class="config-status"><span class="status-dot"></span><div><small>当前简历</small><strong>{{ resumeStore.fileName || '最近一次解析结果' }}</strong><p>解析完成度 {{ resumeStore.parseQuality ? resumeStore.parseQuality + '%' : '—' }}</p></div></div>
        <div class="selected-target"><small>自动匹配目标岗位</small><strong>{{ path?.job_title || '等待选择推荐岗位' }}</strong><em>{{ path?.job_name_en || '' }}<span v-if="path?.category"> · {{ path.category }}</span></em></div>
      </div>

      <div v-if="!selectedJobId" class="roadmap-empty compact"><div class="empty-symbol"><el-icon><MagicStick /></el-icon></div><h3>请选择一个自动推荐岗位</h3><p>学习路径必须绑定到简历页中你点击的推荐岗位，避免生成与匹配结果不一致的路径。</p><el-button class="btn-soft" @click="router.push('/resume')">返回查看岗位推荐</el-button></div>

      <template v-else>
        <div v-if="path">
          <div class="summary-grid">
            <div><span>岗位</span><strong>{{ path.job_title }}</strong></div>
            <div><span>已掌握</span><strong class="green-text">{{ path.overview ? path.overview.mastered_required + path.overview.mastered_bonus : path.mastered_skills.length }} 项</strong></div>
            <div><span>待学习</span><strong class="orange-text">{{ path.missing_skills.length }} 项</strong></div>
            <div><span>数据来源</span><strong>岗位技能目录 + JD 证据</strong></div>
          </div>

          <div v-if="path.overview?.at_standard" class="at-standard">
            <el-icon><CircleCheck /></el-icon>
            <div><strong>当前已达标</strong><p>该岗位的必备与加分技能均已命中当前简历，可直接投递；建议在真实项目中持续巩固，并关注岗位加分项以提升竞争力。</p></div>
          </div>

          <div v-if="path.mastered_skills.length" class="skill-overview">
            <div class="skill-panel"><div class="panel-title"><el-icon><CircleCheck /></el-icon><b>已掌握技能</b><el-tag type="success" size="small">{{ path.mastered_skills.length }}</el-tag></div><div class="skill-tags"><el-tag v-for="skill in path.mastered_skills" :key="skill" type="success" effect="plain">{{ skill }}</el-tag><span v-if="!path.mastered_skills.length" class="muted">暂无直接命中技能</span></div></div>
            <div class="skill-panel"><div class="panel-title"><el-icon><Warning /></el-icon><b>岗位技能缺口</b><el-tag type="warning" size="small">{{ path.missing_skills.length }}</el-tag></div><div class="skill-tags"><el-tag v-for="skill in path.missing_skills" :key="skill.name" type="warning" effect="plain">{{ skill.display_name || skill.name }}</el-tag><span v-if="!path.missing_skills.length" class="muted">当前没有待学习技能</span></div></div>
          </div>

          <div v-if="path.missing_skills?.length" class="suggestions">
            <div class="section-heading"><div><h3>针对性改进建议</h3></div></div>
            <article v-for="item in path.missing_skills" :key="item.name" class="suggestion-card">
              <div class="suggestion-head">
                <strong>{{ item.display_name || item.name }}</strong>
                <el-tag v-if="item.category" size="small" effect="plain">{{ item.category }}</el-tag>
                <el-tag size="small" :type="item.priority === 'high' ? 'danger' : 'warning'" effect="plain">{{ item.priority === 'high' ? '必备缺口' : '加分缺口' }}</el-tag>
              </div>
              <p class="suggestion-text">{{ item.suggestion }}</p>
              <div v-if="item.bridge_skills?.length" class="bridge-line">简历衔接：已掌握 {{ item.bridge_skills.join('、') }}，可顺延补齐</div>
              <div v-if="item.evidence" class="evidence-line">JD 依据：{{ item.evidence }}</div>
            </article>
          </div>

          <div v-if="path.stages?.length" class="stages">
            <div class="section-heading"><div><h3>学习阶段</h3></div></div>
            <div class="stage-list">
              <article v-for="stage in path.stages" :key="stage.stage" class="stage-card">
                <div class="stage-body">
                  <strong>{{ stage.title }}</strong>
                  <p>{{ stage.description }}</p>
                  <ol class="stage-steps">
                    <li v-for="skill in stage.skills" :key="skill.name">
                      <div class="step-head"><b>{{ skill.display_name || skill.name }}</b><el-tag size="small" effect="plain">{{ skill.category }}</el-tag></div>
                      <p v-if="skill.suggestion" class="step-tip">{{ skill.suggestion }}</p>
                    </li>
                  </ol>
                </div>
              </article>
            </div>
          </div>
        </div>
        <div v-else class="roadmap-empty"><div class="empty-symbol"><el-icon><MagicStick /></el-icon></div><h3>正在生成学习路径</h3><p>学习目标已锁定为自动匹配岗位，请稍候。</p></div>
      </template>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { CircleCheck, Document, MagicStick, Warning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { generateLearningPath, type LearningPath } from '../api/learning'
import { useResumeStore } from '../store/resume'

const router = useRouter()
const route = useRoute()
const resumeStore = useResumeStore()
const loading = ref(false)
const generating = ref(false)
const selectedJobId = ref(String(route.query.job_id || route.query.job || resumeStore.matchResult?.target_job_id || ''))
const path = ref<LearningPath | null>(null)
const hasResume = computed(() => Boolean(resumeStore.profile?.skills?.length))

async function generatePath() {
  if (!hasResume.value || !selectedJobId.value) return
  generating.value = true
  try {
    path.value = await generateLearningPath({ job_id: selectedJobId.value, resume_skills: resumeStore.profile.skills || [] })
    ElMessage.success('学习路径已生成')
  } catch { ElMessage.error('学习路径生成失败') } finally { generating.value = false }
}

onMounted(async () => {
  loading.value = true
  try { if (hasResume.value && selectedJobId.value) await generatePath() } finally { loading.value = false }
})
</script>

<style scoped>
.learning-roadmap { min-height: 620px; }.roadmap-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-bottom: 18px; border-bottom: 1px solid var(--line); }.roadmap-header h2 { margin: 0 0 5px; font-size: 18px; }.roadmap-header p { margin: 0; color: #a29d99; font-size: 12px; }.roadmap-config { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 18px 0 14px; padding: 15px; border-radius: 13px; background: var(--card-soft); }.config-status { display: flex; align-items: center; gap: 10px; }.status-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--green); box-shadow: 0 0 0 5px var(--green-soft); }.config-status small, .config-status strong, .config-status p { display: block; }.config-status small { color: #a5a09b; font-size: 10px; }.config-status strong { margin: 4px 0; font-size: 13px; }.config-status p { margin: 0; color: #78a486; font-size: 10px; }.selected-target { min-width: 260px; text-align: right; }.selected-target small, .selected-target strong, .selected-target em { display: block; }.selected-target small { color: #a5a09b; font-size: 10px; }.selected-target strong { margin: 4px 0; font-size: 14px; }.selected-target em { color: #8f8985; font-size: 11px; font-style: normal; }.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }.summary-grid > div { padding: 14px; border-radius: 12px; background: #fffaf6; }.summary-grid span, .summary-grid strong { display: block; }.summary-grid span { color: #a5a09b; font-size: 11px; }.summary-grid strong { margin-top: 5px; color: var(--text); font-size: 16px; }.green-text { color: #67a37b !important; }.orange-text { color: #c58a4c !important; }
.at-standard { display: flex; align-items: center; gap: 12px; margin-top: 12px; padding: 14px 16px; border-radius: 12px; background: #eef7f0; color: #3f7a58; }.at-standard .el-icon { font-size: 22px; }.at-standard strong { font-size: 14px; }.at-standard p { margin: 4px 0 0; font-size: 12px; line-height: 1.7; color: #4e7a60; }
.skill-overview { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }.skill-panel { min-height: 112px; padding: 15px; border-radius: 12px; background: var(--card-soft); }.panel-title { display: flex; align-items: center; gap: 7px; margin-bottom: 13px; font-size: 13px; }.panel-title .el-icon { color: var(--green); }.skill-panel:nth-child(2) .panel-title .el-icon { color: var(--orange); }.panel-title .el-tag { margin-left: auto; }.skill-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }.muted { color: #aaa39e; font-size: 11px; }
.suggestions { margin-top: 18px; }.suggestion-card { padding: 13px 15px; margin-bottom: 10px; border: 1px solid var(--line); border-radius: 12px; background: #fff; }.suggestion-head { display: flex; align-items: center; gap: 8px; }.suggestion-head strong { font-size: 14px; }.suggestion-head .el-tag { margin-right: 0; }.suggestion-text { margin: 8px 0 6px; color: #5f5a55; font-size: 12.5px; line-height: 1.8; }.bridge-line, .evidence-line { color: #98918d; font-size: 11px; line-height: 1.7; }.evidence-line { color: #a1886a; }
.stages { margin-top: 18px; }.stage-list { display: grid; gap: 10px; }.stage-card { display: flex; gap: 12px; padding: 15px; border: 1px solid var(--line); border-radius: 12px; background: #fff; }.stage-body strong { font-size: 13px; }.stage-body p { margin: 6px 0 9px; color: #98918d; font-size: 11px; }.roadmap-empty { display: flex; min-height: 350px; flex-direction: column; align-items: center; justify-content: center; padding: 30px; border: 1px dashed var(--line-strong); border-radius: 14px; background: linear-gradient(180deg, #fffdfa, #fcfaf7); text-align: center; }.roadmap-empty.compact { min-height: 300px; margin-top: 18px; }.empty-symbol { display: grid; width: 58px; height: 58px; place-items: center; border-radius: 50%; background: var(--coral-soft); color: var(--coral); font-size: 27px; }.roadmap-empty h3 { margin: 14px 0 7px; font-size: 18px; }.roadmap-empty p { max-width: 560px; margin: 0 0 18px; color: #a29d99; font-size: 12px; line-height: 1.8; }
.stage-steps { counter-reset: step; margin: 6px 0 0; padding: 0; list-style: none; }.stage-steps li { position: relative; padding: 8px 10px 8px 30px; margin-bottom: 6px; border-radius: 10px; background: #faf7f2; }.stage-steps li::before { counter-increment: step; content: counter(step); position: absolute; left: 8px; top: 9px; width: 16px; height: 16px; border-radius: 50%; background: var(--coral-soft); color: var(--coral-deep); font-size: 10px; font-weight: 700; text-align: center; line-height: 16px; }.step-head { display: flex; align-items: center; gap: 8px; }.step-head b { font-size: 12.5px; }.step-tip { margin: 4px 0 0; color: #98918d; font-size: 11px; line-height: 1.7; }
@media (max-width: 800px) { .roadmap-header, .roadmap-config { align-items: flex-start; flex-direction: column; }.selected-target { width: 100%; text-align: right; }.summary-grid { grid-template-columns: repeat(2, 1fr); }.skill-overview { grid-template-columns: 1fr; } }
@media (max-width: 500px) { .summary-grid { grid-template-columns: 1fr; } }
</style>