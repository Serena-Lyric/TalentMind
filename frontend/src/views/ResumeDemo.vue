<template>
  <div class="resume-demo-page">
    <div v-if="!resume" class="empty-state">
      <el-icon :size="48" color="#D98B6E"><Document /></el-icon>
      <h2>暂无可预览的简历</h2>
      <p>请先在“简历解析匹配”页面上传并完成一次简历解析。</p>
      <el-button type="primary" @click="goBack">返回简历解析</el-button>
    </div>

    <template v-else>
    <div class="page-header">
      <h1>简历预览与导出</h1>
      <p>展示最近一次简历解析结果，支持导出 PDF</p>
      <div class="header-actions">
        <el-button @click="goBack">
          <el-icon><ArrowLeft /></el-icon>返回
        </el-button>
        <el-button type="primary" @click="exportPDF">
          <el-icon><Download /></el-icon>导出PDF
        </el-button>
      </div>
    </div>

    <div class="resume-container" ref="resumeRef">
      <div class="resume-paper">
        <!-- 头部信息 -->
        <div class="resume-header">
          <div class="header-left">
            <h1 class="resume-name">{{ resume.basic.name }}</h1>
            <div class="job-intention">{{ resume.basic.jobIntention }}</div>
            <div class="contact-info">
              <span><el-icon><Phone /></el-icon>{{ resume.basic.phone }}</span>
              <span><el-icon><Message /></el-icon>{{ resume.basic.email }}</span>
              <span><el-icon><Location /></el-icon>{{ resume.basic.location }}</span>
              <span>{{ resume.basic.gender }}</span>
            </div>
          </div>
          <div class="header-right">
            <div class="avatar-placeholder">
              <el-icon :size="48"><User /></el-icon>
            </div>
          </div>
        </div>

        <!-- 教育经历 -->
        <div class="resume-section">
          <h2 class="section-title">
            <span class="title-icon">📚</span>
            教育经历
          </h2>
          <div class="education-item">
            <div class="edu-header">
              <div class="edu-left">
                <h3>{{ resume.education.school }}</h3>
                <span class="major">{{ resume.education.major }} · {{ resume.education.degree }}</span>
              </div>
              <div class="edu-right">{{ resume.education.duration }}</div>
            </div>
            <div class="courses">
              <span class="label">主修课程：</span>
              <span>{{ resume.education.courses.join('、') }}</span>
            </div>
          </div>
        </div>

        <!-- 专业技能 -->
        <div class="resume-section">
          <h2 class="section-title">
            <span class="title-icon">💻</span>
            专业技能
          </h2>
          <div class="skills-grid">
            <div v-for="(detail, dim) in resume.skills.details" :key="dim" class="skill-item">
              <div class="skill-header">
                <span class="skill-name">{{ dim }}</span>
                <el-progress :percentage="detail.level" :stroke-width="6" :show-text="false" color="#2f7cf6" />
                <span class="skill-level">{{ detail.level }}分</span>
              </div>
              <div class="skill-tags">
                <el-tag v-for="item in detail.items" :key="item" size="small" effect="plain">{{ item }}</el-tag>
              </div>
            </div>
          </div>
        </div>

        <!-- 项目经历 -->
        <div v-if="resume.projects.length" class="resume-section">
          <h2 class="section-title">
            <span class="title-icon">🚀</span>
            项目经历
          </h2>
          <div v-for="(project, index) in resume.projects" :key="index" class="project-item">
            <div class="project-header">
              <div class="project-left">
                <h3>{{ project.name }}</h3>
                <div v-if="project.techStack" class="tech-stack">技术栈：{{ project.techStack }}</div>
              </div>
              <div class="project-right">{{ project.duration }}</div>
            </div>
            <ul class="project-list">
              <li v-for="(resp, i) in project.responsibilities" :key="i">{{ resp }}</li>
            </ul>
          </div>
        </div>

        <!-- 竞赛与荣誉 -->
        <div v-if="resume.honors.length" class="resume-section">
          <h2 class="section-title">
            <span class="title-icon">🏆</span>
            竞赛与荣誉
          </h2>
          <div class="honors-list">
            <div v-for="(honor, index) in resume.honors" :key="index" class="honor-item">
              <span class="honor-time">{{ honor.time }}</span>
              <span class="honor-title">{{ honor.title }}</span>
            </div>
          </div>
        </div>

        <!-- 自我评价 -->
        <div v-if="resume.selfEvaluation" class="resume-section">
          <h2 class="section-title">
            <span class="title-icon">💡</span>
            自我评价
          </h2>
          <p class="self-evaluation">{{ resume.selfEvaluation }}</p>
        </div>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Download, Phone, Message, Location, User, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useResumeStore } from '../store/resume'


const router = useRouter()
const resumeStore = useResumeStore()
const resumeRef = ref<HTMLElement | null>(null)

// 把后端解析 profile 适配为预览模板结构；无真实数据时显示空态
const resume = computed<any>(() => {
  const p = resumeStore.profile
  if (!p) return null
  return {
    basic: {
      name: p.name || '未命名简历',
      jobIntention: p.role || '—',
      phone: p.phone || '', email: p.email || '', location: p.location || '', gender: p.gender || '',
    },
    education: {
      school: p.education_school || p.education || '—',
      major: p.education_major || '', degree: p.education_degree || '', duration: p.education_period || '',
      courses: [],
    },
    skills: {
      details: p.skills && p.skills.length
        ? { '已识别技能': { level: 80, items: p.skills } }
        : {},
    },
    projects: (p.projects || []).map((pr: any) => ({ name: pr.name || '项目实践', duration: pr.duration || '', techStack: pr.tech_stack || '', responsibilities: pr.responsibilities || [] })),
    honors: (p.honors || []).map((h: any) => ({ time: h.time || '', title: h.title || '' })),
    selfEvaluation: p.self_evaluation || '',
  }
})

function goBack() {
  router.push('/resume')
}

async function exportPDF() {
  if (!resume.value) { ElMessage.warning('暂无可导出的简历'); return }
  ElMessage.info('正在生成PDF，请稍候...')
  
  try {
    // 动态导入 html2canvas 和 jspdf
    const html2canvas = (await import('html2canvas')).default
    const { jsPDF } = await import('jspdf')
    
    if (!resumeRef.value) return
    
    const element = resumeRef.value.querySelector('.resume-paper') as HTMLElement
    if (!element) return
    
    const canvas = await html2canvas(element, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#ffffff'
    })
    
    const imgData = canvas.toDataURL('image/png')
    const pdf = new jsPDF('p', 'mm', 'a4')
    const pdfWidth = pdf.internal.pageSize.getWidth()
    const pdfHeight = pdf.internal.pageSize.getHeight()
    const imgWidth = canvas.width
    const imgHeight = canvas.height
    const ratio = Math.min(pdfWidth / imgWidth, pdfHeight / imgHeight)
    const imgX = (pdfWidth - imgWidth * ratio) / 2
    const imgY = 0
    
    pdf.addImage(imgData, 'PNG', imgX, imgY, imgWidth * ratio, imgHeight * ratio)
    pdf.save('TalentMind-简历.pdf')
    
    ElMessage.success('PDF导出成功！')
  } catch (error) {
    console.error('PDF导出失败:', error)
    ElMessage.error('PDF导出失败，请安装 html2canvas 和 jspdf 依赖')
  }
}
</script>

<style scoped>
.empty-state {
  min-height: 420px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: #fff;
  border: 1px solid #F0EBE3;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
  text-align: center;
}

.empty-state h2 {
  margin: 8px 0 0;
  color: #3D3D3D;
  font-size: 20px;
}

.empty-state p {
  margin: 0 0 8px;
  color: #8C8C8C;
  font-size: 13px;
}

.resume-demo-page {
  max-width: 1200px;
  margin: auto;
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}

.page-header h1 {
  font-size: 24px;
  margin: 0;
}

.page-header p {
  font-size: 14px;
  color: #8d99ad;
  margin: 4px 0 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.resume-container {
  display: flex;
  justify-content: center;
}

.resume-paper {
  width: 100%;
  max-width: 800px;
  background: #fff;
  padding: 40px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  border-radius: 8px;
}

/* 头部信息 */
.resume-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding-bottom: 20px;
  border-bottom: 2px solid #2f7cf6;
  margin-bottom: 24px;
}

.header-left {
  flex: 1;
}

.resume-name {
  font-size: 28px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 8px;
}

.job-intention {
  font-size: 14px;
  color: #2f7cf6;
  margin-bottom: 12px;
  font-weight: 500;
}

.contact-info {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: #6b7280;
}

.contact-info span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.contact-info .el-icon {
  font-size: 14px;
  color: #2f7cf6;
}

.header-right {
  margin-left: 24px;
}

.avatar-placeholder {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: #e8f4ff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #2f7cf6;
}

/* 章节标题 */
.resume-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-icon {
  font-size: 18px;
}

/* 教育经历 */
.education-item {
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
}

.edu-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.edu-left h3 {
  margin: 0 0 4px;
  font-size: 15px;
  color: #1f2937;
}

.major {
  font-size: 13px;
  color: #6b7280;
}

.edu-right {
  font-size: 13px;
  color: #6b7280;
}

.courses {
  font-size: 13px;
  color: #4b5563;
}

.courses .label {
  color: #6b7280;
}

/* 专业技能 */
.skills-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.skill-item {
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
}

.skill-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.skill-name {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  min-width: 80px;
}

.skill-header .el-progress {
  flex: 1;
}

.skill-level {
  font-size: 12px;
  color: #2f7cf6;
  font-weight: 600;
}

.skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.skill-tags .el-tag {
  font-size: 11px;
}

/* 项目经历 */
.project-item {
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
  margin-bottom: 12px;
}

.project-item:last-child {
  margin-bottom: 0;
}

.project-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.project-left h3 {
  margin: 0 0 4px;
  font-size: 15px;
  color: #1f2937;
}

.tech-stack {
  font-size: 12px;
  color: #2f7cf6;
}

.project-right {
  font-size: 13px;
  color: #6b7280;
}

.project-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: #4b5563;
  line-height: 1.8;
}

.project-list li {
  margin-bottom: 4px;
}

/* 竞赛与荣誉 */
.honors-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.honor-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 12px;
  background: #f9fafb;
  border-radius: 6px;
}

.honor-time {
  font-size: 13px;
  color: #6b7280;
  min-width: 100px;
}

.honor-title {
  font-size: 14px;
  color: #374151;
  font-weight: 500;
}

/* 自我评价 */
.self-evaluation {
  font-size: 14px;
  color: #4b5563;
  line-height: 1.8;
  margin: 0;
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
}

/* 响应式 */
@media (max-width: 768px) {
  .resume-paper {
    padding: 24px;
  }
  
  .resume-header {
    flex-direction: column-reverse;
    align-items: center;
    text-align: center;
  }
  
  .header-right {
    margin-left: 0;
    margin-bottom: 16px;
  }
  
  .contact-info {
    justify-content: center;
  }
  
  .skills-grid {
    grid-template-columns: 1fr;
  }
  
  .edu-header,
  .project-header {
    flex-direction: column;
    gap: 4px;
  }
}
</style>
