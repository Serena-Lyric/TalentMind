<template>
  <section class="learning-roadmap panel" v-loading="loading">
    <div class="roadmap-header">
      <div><h2>技能学习路径</h2><p>学习目标来自简历自动匹配结果，点击推荐岗位后自动生成对应路径。</p></div>
      <el-button class="btn-coral" :disabled="!hasResume || !selectedJobId" :loading="generating" @click="generatePath"><el-icon><MagicStick /></el-icon>重新生成</el-button>
    </div>

    <div v-if="!hasResume" class="roadmap-empty compact"><div class="empty-symbol"><el-icon><Document /></el-icon></div><h3>请先完成简历解析</h3><p>解析简历后系统会自动给出至少 3 个岗位推荐；从推荐卡片进入即可绑定学习目标。</p><el-button class="btn-soft" @click="router.push('/resume')">前往简历解析</el-button></div>
    <template v-else>
      <div class="roadmap-config"><div class="config-status"><span class="status-dot"></span><div><small>当前简历</small><strong>{{ resumeStore.fileName || '最近一次解析结果' }}</strong><p>解析完成度 {{ resumeStore.parseQuality || 92 }}%</p></div></div><div class="selected-target"><small>自动匹配目标岗位</small><strong>{{ path?.job_title || '等待选择推荐岗位' }}</strong><em>{{ path?.job_name_en || '' }}<span v-if="path?.category"> · {{ path.category }}</span></em></div></div>

      <div v-if="!selectedJobId" class="roadmap-empty compact"><div class="empty-symbol"><el-icon><MagicStick /></el-icon></div><h3>请选择一个自动推荐岗位</h3><p>学习路径必须绑定到简历页中你点击的推荐岗位，避免生成与匹配结果不一致的路径。</p><el-button class="btn-soft" @click="router.push('/resume')">返回查看岗位推荐</el-button></div>
      <template v-else>
        <div v-if="path" class="summary-grid"><div><span>岗位</span><strong>{{ path.job_title }}</strong></div><div><span>已掌握</span><strong class="green-text">{{ path.mastered_skills.length }} 项</strong></div><div><span>待学习</span><strong class="orange-text">{{ path.missing_skills.length }} 项</strong></div><div><span>数据来源</span><strong>岗位技能目录</strong></div></div>
        <div v-if="path" class="skill-overview"><div class="skill-panel"><div class="panel-title"><el-icon><CircleCheck /></el-icon><b>已掌握技能</b><el-tag type="success" size="small">{{ path.mastered_skills.length }}</el-tag></div><div class="skill-tags"><el-tag v-for="skill in path.mastered_skills" :key="skill" type="success" effect="plain">{{ skill }}</el-tag><span v-if="!path.mastered_skills.length" class="muted">暂无直接命中技能</span></div></div><div class="skill-panel"><div class="panel-title"><el-icon><Warning /></el-icon><b>岗位技能缺口</b><el-tag type="warning" size="small">{{ path.missing_skills.length }}</el-tag></div><div class="skill-tags"><el-tag v-for="skill in path.missing_skills" :key="skill.name" type="warning" effect="plain">{{ skill.name }}</el-tag><span v-if="!path.missing_skills.length" class="muted">当前没有待学习技能</span></div></div></div>
        <div v-if="path" class="stages"><div class="section-heading"><div><h3>学习阶段</h3><p>阶段只根据真实技能缺口分组，不虚构课程时长或资源链接。</p></div></div><div class="stage-list"><article v-for="stage in path.stages" :key="stage.stage" class="stage-card"><div class="stage-index">{{ stage.stage }}</div><div class="stage-body"><strong>{{ stage.title }} · {{ stage.category }}</strong><p>{{ stage.skills.map(item => item.name).join('、') }}</p><div class="skill-tags"><el-tag v-for="skill in stage.skills" :key="skill.name" size="small" :type="skill.priority === 'high' ? 'danger' : 'warning'">{{ skill.name }}</el-tag></div></div></article></div></div>
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
.learning-roadmap { min-height: 620px; }.roadmap-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-bottom: 18px; border-bottom: 1px solid var(--line); }.roadmap-header h2 { margin: 0 0 5px; font-size: 18px; }.roadmap-header p { margin: 0; color: #a29d99; font-size: 12px; }.roadmap-config { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 18px 0 14px; padding: 15px; border-radius: 13px; background: var(--card-soft); }.config-status { display: flex; align-items: center; gap: 10px; }.status-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--green); box-shadow: 0 0 0 5px var(--green-soft); }.config-status small, .config-status strong, .config-status p { display: block; }.config-status small { color: #a5a09b; font-size: 10px; }.config-status strong { margin: 4px 0; font-size: 13px; }.config-status p { margin: 0; color: #78a486; font-size: 10px; }.selected-target { min-width: 260px; text-align: right; }.selected-target small, .selected-target strong, .selected-target em { display: block; }.selected-target small { color: #a5a09b; font-size: 10px; }.selected-target strong { margin: 4px 0; font-size: 14px; }.selected-target em { color: #8f8985; font-size: 11px; font-style: normal; }.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }.summary-grid > div { padding: 14px; border-radius: 12px; background: #fffaf6; }.summary-grid span, .summary-grid strong { display: block; }.summary-grid span { color: #a5a09b; font-size: 11px; }.summary-grid strong { margin-top: 5px; color: var(--text); font-size: 16px; }.green-text { color: #67a37b !important; }.orange-text { color: #c58a4c !important; }.skill-overview { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }.skill-panel { min-height: 112px; padding: 15px; border-radius: 12px; background: var(--card-soft); }.panel-title { display: flex; align-items: center; gap: 7px; margin-bottom: 13px; font-size: 13px; }.panel-title .el-icon { color: var(--green); }.skill-panel:nth-child(2) .panel-title .el-icon { color: var(--orange); }.panel-title .el-tag { margin-left: auto; }.skill-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }.muted { color: #aaa39e; font-size: 11px; }.stages { margin-top: 16px; }.stage-list { display: grid; gap: 10px; }.stage-card { display: flex; gap: 12px; padding: 15px; border: 1px solid var(--line); border-radius: 12px; background: #fff; }.stage-index { display: grid; width: 28px; height: 28px; flex: 0 0 auto; place-items: center; border-radius: 50%; background: var(--coral-soft); color: var(--coral-deep); font-size: 13px; font-weight: 700; }.stage-body strong { font-size: 13px; }.stage-body p { margin: 6px 0 9px; color: #98918d; font-size: 11px; }.roadmap-empty { display: flex; min-height: 350px; flex-direction: column; align-items: center; justify-content: center; padding: 30px; border: 1px dashed var(--line-strong); border-radius: 14px; background: linear-gradient(180deg, #fffdfa, #fcfaf7); text-align: center; }.roadmap-empty.compact { min-height: 300px; margin-top: 18px; }.empty-symbol { display: grid; width: 58px; height: 58px; place-items: center; border-radius: 50%; background: var(--coral-soft); color: var(--coral); font-size: 27px; }.roadmap-empty h3 { margin: 14px 0 7px; font-size: 18px; }.roadmap-empty p { max-width: 560px; margin: 0 0 18px; color: #a29d99; font-size: 12px; line-height: 1.8; }
@media (max-width: 800px) { .roadmap-header, .roadmap-config { align-items: flex-start; flex-direction: column; }.selected-target { width: 100%; text-align: left; }.summary-grid { grid-template-columns: repeat(2, 1fr); }.skill-overview { grid-template-columns: 1fr; } }
@media (max-width: 500px) { .summary-grid { grid-template-columns: 1fr; } }
</style>