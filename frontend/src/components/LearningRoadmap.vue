<template>
  <section class="roadmap-page">


    <!-- 骨架屏 -->
    <div v-if="loading" class="skeleton-screen">
      <div class="skeleton-banner"></div>
      <div class="skeleton-cards"><div v-for="i in 3" :key="i" class="skeleton-card"></div></div>
      <div class="skeleton-stages"><div v-for="i in 3" :key="i" class="skeleton-stage"></div></div>
    </div>

    <!-- 空状态引导 -->
    <div v-else-if="!currentPath && !selectedJob" class="empty-guide">
      <div class="empty-illustration">
        <svg width="180" height="140" viewBox="0 0 180 140" fill="none">
          <circle cx="90" cy="70" r="55" fill="#FDE8E4" opacity="0.5"/>
          <circle cx="90" cy="70" r="40" fill="#FDF5F0"/>
          <!-- 书本 -->
          <rect x="60" y="50" width="60" height="45" rx="3" fill="#fff" stroke="#E0D5CA" stroke-width="1"/>
          <line x1="90" y1="50" x2="90" y2="95" stroke="#E0D5CA" stroke-width="1"/>
          <line x1="68" y1="62" x2="85" y2="62" stroke="#E07B6D" stroke-width="1" opacity="0.4"/>
          <line x1="68" y1="68" x2="82" y2="68" stroke="#E07B6D" stroke-width="1" opacity="0.3"/>
          <line x1="95" y1="62" x2="112" y2="62" stroke="#A8C5B8" stroke-width="1" opacity="0.4"/>
          <line x1="95" y1="68" x2="108" y2="68" stroke="#A8C5B8" stroke-width="1" opacity="0.3"/>
          <!-- 铅笔 -->
          <rect x="125" y="35" width="5" height="30" rx="1" fill="#FDE8E4" stroke="#E07B6D" stroke-width="0.6" transform="rotate(20 127 50)"/>
          <path d="M126 64 L128 70 L130 64" fill="#E07B6D" opacity="0.4" transform="rotate(20 128 67)"/>
          <!-- 星星 -->
          <path d="M45 30 L47 36 L53 36 L48 40 L50 46 L45 42 L40 46 L42 40 L37 36 L43 36 Z" fill="#FFA726" opacity="0.15"/>
          <circle cx="140" cy="25" r="3" fill="#A8C5B8" opacity="0.15"/>
          <circle cx="50" cy="100" r="2" fill="#B8C4D0" opacity="0.12"/>
        </svg>
      </div>
      <h2>开始你的技能提升之旅</h2>
      <p>选择目标岗位，系统将为你生成个性化的学习路线</p>
      <el-select v-model="selectedJob" placeholder="选择目标岗位" size="large" @change="generatePath">
        <el-option v-for="(path, key) in jobPaths" :key="key" :label="path.jobTitle" :value="key" />
      </el-select>
    </div>

    <template v-else>
      <!-- 标题栏 -->
      <div class="page-title">
        <div>
          <h1>阶梯式技能学习路线</h1>
          <p>围绕目标岗位的能力缺口，按优先级生成可执行的成长计划</p>
        </div>
        <div class="roadmap-actions">
          <el-select v-model="selectedJob" size="default" @change="switchJob">
            <el-option v-for="(path, key) in jobPaths" :key="key" :label="path.jobTitle" :value="key" />
          </el-select>
          <el-button-group>
            <el-button :type="viewMode==='roadmap'?'primary':''" @click="viewMode='roadmap'"><el-icon><List /></el-icon>路线视图</el-button>
            <el-button :type="viewMode==='calendar'?'primary':''" @click="viewMode='calendar'"><el-icon><Calendar /></el-icon>日历视图</el-button>
          </el-button-group>
          <el-button type="primary" @click="exportPDF"><el-icon><Download /></el-icon>导出PDF</el-button>
        </div>
      </div>

      <!-- 全宽卡通插画横幅 -->
      <div class="learning-banner">
        <svg width="100%" height="120" viewBox="0 0 900 120" preserveAspectRatio="xMidYMid meet" fill="none">
          <defs>
            <linearGradient id="learnBannerBg" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#FDE8E4" stop-opacity="0.5"/>
              <stop offset="30%" stop-color="#FDF5F0" stop-opacity="0.6"/>
              <stop offset="70%" stop-color="#E8F5E9" stop-opacity="0.4"/>
              <stop offset="100%" stop-color="#FDF5F0" stop-opacity="0.5"/>
            </linearGradient>
          </defs>
          <rect x="0" y="0" width="900" height="120" rx="14" fill="url(#learnBannerBg)"/>

          <!-- 左侧：书本堆叠 -->
          <rect x="40" y="70" width="55" height="9" rx="2" fill="#D98B6E" opacity="0.25"/>
          <rect x="43" y="59" width="52" height="9" rx="2" fill="#A8C5B8" opacity="0.25"/>
          <rect x="38" y="48" width="57" height="9" rx="2" fill="#B8C4D0" opacity="0.25"/>
          <rect x="45" y="37" width="50" height="9" rx="2" fill="#D98B6E" opacity="0.18"/>
          <!-- 铅笔 -->
          <rect x="100" y="25" width="5" height="45" rx="1.5" fill="#FDE8E4" stroke="#D98B6E" stroke-width="0.8" transform="rotate(12 102 47)"/>
          <path d="M100 69 L102.5 76 L105 69" fill="#D98B6E" opacity="0.4" transform="rotate(12 102.5 72)"/>

          <!-- 左侧人物：阅读 -->
          <circle cx="170" cy="50" r="14" fill="#F5D5C8"/>
          <path d="M156 47 Q158 38 170 36 Q182 38 184 47" fill="#8B7B6B" opacity="0.5"/>
          <circle cx="165" cy="50" r="2" fill="#555" opacity="0.4"/>
          <circle cx="175" cy="50" r="2" fill="#555" opacity="0.4"/>
          <path d="M166 54 Q170 57 174 54" stroke="#C09080" stroke-width="1" fill="none" opacity="0.4"/>
          <path d="M158 64 Q158 58 170 58 Q182 58 182 64 L184 85 Q184 90 170 90 Q156 90 156 85 Z" fill="#D98B6E" opacity="0.18"/>
          <!-- 手臂拿书 -->
          <path d="M162 72 L148 62" stroke="#F5D5C8" stroke-width="2.5" stroke-linecap="round"/>
          <rect x="133" y="52" width="18" height="14" rx="2" fill="#fff" stroke="#E0D5CA" stroke-width="1"/>
          <rect x="136" y="56" width="10" height="2" rx="1" fill="#D98B6E" opacity="0.3"/>
          <rect x="136" y="60" width="8" height="2" rx="1" fill="#B8C4D0" opacity="0.2"/>

          <!-- 中间：阶梯成长路径 -->
          <rect x="240" y="90" width="50" height="14" rx="3" fill="#D98B6E" opacity="0.2"/>
          <text x="265" y="100" text-anchor="middle" font-size="8" fill="#D98B6E">基础</text>
          <rect x="300" y="68" width="50" height="36" rx="3" fill="#A8C5B8" opacity="0.2"/>
          <text x="325" y="89" text-anchor="middle" font-size="8" fill="#6A9A70">进阶</text>
          <rect x="360" y="45" width="50" height="59" rx="3" fill="#B8C4D0" opacity="0.2"/>
          <text x="385" y="78" text-anchor="middle" font-size="8" fill="#555559">实战</text>
          <rect x="420" y="22" width="50" height="82" rx="3" fill="#D98B6E" opacity="0.15"/>
          <text x="445" y="66" text-anchor="middle" font-size="8" fill="#D98B6E">精通</text>

          <!-- 攀登人物 -->
          <circle cx="395" cy="32" r="12" fill="#F5D5C8"/>
          <path d="M383 29 Q385 22 395 20 Q405 22 407 29" fill="#8B7B6B" opacity="0.5"/>
          <path d="M385 42 Q385 37 395 37 Q405 37 405 42 L406 58 Q406 62 395 62 Q384 62 384 58 Z" fill="#D98B6E" opacity="0.18"/>
          <path d="M388 48 L375 38" stroke="#F5D5C8" stroke-width="2.5" stroke-linecap="round"/>
          <line x1="375" y1="24" x2="375" y2="42" stroke="#B8C4D0" stroke-width="1.5"/>
          <path d="M375 24 L390 29 L375 34 Z" fill="#D98B6E" opacity="0.28"/>

          <!-- 右侧：证书奖杯 -->
          <circle cx="540" cy="48" r="26" fill="#FDE8E4" stroke="#D98B6E" stroke-width="1.8"/>
          <text x="540" y="44" text-anchor="middle" font-size="16" fill="#D98B6E">★</text>
          <text x="540" y="58" text-anchor="middle" font-size="8" fill="#D98B6E" font-weight="600">达成</text>
          <rect x="528" y="80" width="24" height="16" rx="3" fill="#FFD699" opacity="0.4"/>
          <path d="M523 80 Q523 92 532 95" stroke="#D4A574" stroke-width="1.2" fill="none" opacity="0.3"/>
          <path d="M557 80 Q557 92 548 95" stroke="#D4A574" stroke-width="1.2" fill="none" opacity="0.3"/>
          <rect x="533" y="95" width="14" height="5" rx="1.5" fill="#D4A574" opacity="0.28"/>
          <rect x="530" y="100" width="20" height="3" rx="1" fill="#D4A574" opacity="0.22"/>

          <!-- 右侧人物：庆祝 -->
          <circle cx="650" cy="42" r="14" fill="#F5D5C8"/>
          <path d="M636 39 Q638 30 650 28 Q662 30 664 39" fill="#8B7B6B" opacity="0.5"/>
          <circle cx="645" cy="42" r="2" fill="#555" opacity="0.4"/>
          <circle cx="655" cy="42" r="2" fill="#555" opacity="0.4"/>
          <path d="M644 46 Q650 50 656 46" stroke="#C09080" stroke-width="1" fill="none" opacity="0.4"/>
          <path d="M638 56 Q638 50 650 50 Q662 50 662 56 L664 80 Q664 85 650 85 Q636 85 636 80 Z" fill="#A8C5B8" opacity="0.18"/>
          <!-- 举手庆祝 -->
          <path d="M642 62 L630 45" stroke="#F5D5C8" stroke-width="2.5" stroke-linecap="round"/>
          <path d="M658 62 L670 45" stroke="#F5D5C8" stroke-width="2.5" stroke-linecap="round"/>

          <!-- 右侧装饰：笔记本电脑 -->
          <rect x="750" y="55" width="60" height="35" rx="4" fill="#fff" stroke="#E0D5CA" stroke-width="1"/>
          <rect x="754" y="59" width="52" height="24" rx="2" fill="#F7F0EA"/>
          <rect x="740" y="90" width="88" height="4" rx="2" fill="#D5C8BC" opacity="0.4"/>
          <rect x="760" y="72" width="8" height="10" rx="1" fill="#D98B6E" opacity="0.3"/>
          <rect x="772" y="66" width="12" height="16" rx="1" fill="#A8C5B8" opacity="0.35"/>
          <rect x="788" y="68" width="8" height="14" rx="1" fill="#D98B6E" opacity="0.25"/>

          <!-- 星星装饰 -->
          <path d="M500 15 L502 21 L508 21 L503 25 L505 31 L500 27 L495 31 L497 25 L492 21 L498 21 Z" fill="#FFD699" opacity="0.2"/>
          <path d="M700 20 L701 23 L705 23 L702 25 L703 28 L700 26 L697 28 L698 25 L695 23 L699 23 Z" fill="#D98B6E" opacity="0.15"/>
          <path d="M300 12 L301 15 L305 15 L302 17 L303 20 L300 18 L297 20 L298 17 L295 15 L299 15 Z" fill="#A8C5B8" opacity="0.18"/>
          <circle cx="830" cy="100" r="3" fill="#B8C4D0" opacity="0.12"/>
          <circle cx="50" cy="105" r="2.5" fill="#D98B6E" opacity="0.1"/>
        </svg>
      </div>

      <!-- 大型卡通插画：学习成长场景 -->
      

      <!-- Hero 区域 -->
      <section class="roadmap-hero">
        <div class="hero-content">
          <div class="hero-radar"><div class="radar-chart" ref="heroRadarRef"></div></div>
          <div class="hero-info">
            <span>你的当前诊断</span>
            <h2>从 <b>{{ currentPath.currentScore }}分</b> 到目标 <b>{{ currentPath.targetScore }}分</b></h2>
            <p>建议优先补齐 {{ currentPath.prioritySkills.length }} 项薄弱技能，预计用时 {{ estimatedWeeks }} 周</p>
            <div class="daily-hours-selector">
              <span>每日学习时长：</span>
              <el-slider v-model="dailyHours" :min="1" :max="6" :step="0.5" :format-tooltip="tooltipHours" @change="updateEstimatedWeeks" />
              <span class="hours-value">{{ dailyHours }}h</span>
            </div>
          </div>
          <div class="hero-progress" @click="showProgressDetail=true">
            <el-progress type="circle" :percentage="progress" :width="112" :stroke-width="10" color="#fff">
              <template #default="{ percentage }"><b>{{ percentage }}%</b><small>学习进度</small></template>
            </el-progress>
          </div>
          <!-- Hero 装饰 -->
          <div class="hero-deco">
            <svg width="60" height="60" viewBox="0 0 60 60" fill="none">
              <circle cx="30" cy="30" r="25" fill="#fff" opacity="0.08"/>
              <path d="M20 30 L28 22 L28 28 L40 28 L40 32 L28 32 L28 38 Z" fill="#fff" opacity="0.15"/>
              <circle cx="45" cy="15" r="3" fill="#fff" opacity="0.1"/>
              <circle cx="15" cy="45" r="2" fill="#fff" opacity="0.08"/>
            </svg>
          </div>
        </div>
      </section>
      <!-- 技能标签筛选 -->
      <div class="tech-tags-filter">
        <el-tag v-for="tag in allSkills" :key="tag" :type="selectedTags.includes(tag)?'':'info'" effect="plain" @click="toggleTag(tag)">{{ tag }}</el-tag>
      </div>

      <!-- 优先补齐能力缺口 -->
      <section class="panel priority-panel">
        <div class="panel-head">
          <div><h3>优先补齐的能力缺口</h3><p>按岗位影响度、当前掌握度与技能依赖关系综合排序</p></div>
          <div class="priority-actions">
            <el-tag type="warning" effect="light">{{ currentPath.prioritySkills.length }} 项待提升</el-tag>
            <el-button size="small" @click="batchAddToPlan">批量加入学习规划</el-button>
          </div>
        </div>
        <div class="priority-list">
          <article v-for="(skill,index) in filteredPrioritySkills" :key="skill.name" class="priority-item" :class="{high:skill.level==='high',medium:skill.level==='medium'}" @click="scrollToSkillTask(skill.name)">
            <div class="priority-checkbox"><el-checkbox v-model="skill.selected" @click.stop /></div>
            <span class="priority-index" :class="skill.level">{{ index+1 }}</span>
            <div class="priority-name"><b>{{ skill.name }}</b><p>{{ skill.reason }}</p></div>
            <el-tag :type="skill.level==='high'?'danger':'warning'" size="small">{{ skill.level==='high'?'P0 高优先级':'P1 建议提升' }}</el-tag>
            <div class="skill-trend"><div class="trend-chart" :ref="el=>setTrendRef(el,skill.name)"></div></div>
            <div class="skill-impact"><span>岗位影响度</span><el-progress :percentage="skill.impact" :show-text="false" :stroke-width="7" :color="skill.level==='high'?'#E07B6D':'#FFA726'" /></div>
            <el-button text size="small" @click.stop="goToGraph(skill.graphNodeId)"><el-icon><Connection /></el-icon>图谱定位</el-button>
          </article>
        </div>
      </section>

      <!-- 路线视图 -->
      <template v-if="viewMode==='roadmap'">
        <section class="roadmap-heading">
          <div><h2>分阶段学习计划</h2><p>建议按顺序完成，每个阶段均有明确学习目标和实践产出</p></div>
          <div class="roadmap-stats"><span>已完成 <b>{{ completedCount }}</b> / {{ allTasks.length }}</span><el-progress :percentage="progress" :show-text="false" :stroke-width="7" color="#E07B6D" /></div>
        </section>
        <section class="timeline">
          <article v-for="(stage,stageIndex) in filteredStages" :key="stage.title" class="stage">
            <div class="stage-marker" :class="{done:allTasksDone(stage.tasks)}"><span>{{ stageIndex+1 }}</span><small>{{ stage.weeks }}</small></div>
            <div class="panel stage-card" :class="{collapsed:stage.collapsed}">
              <div class="stage-card-head" @click="stage.collapsed=!stage.collapsed">
                <div>
                  <span class="stage-label" :style="{color:stage.color,background:stage.color+'14'}">{{ stage.phase }}</span>
                  <h2>{{ stage.title }}</h2>
                  <p>{{ stage.goal }}</p>
                </div>
                <div class="stage-right">
                  <div class="stage-progress-mini"><el-progress :percentage="getStageProgress(stage)" :show-text="false" :stroke-width="4" :color="stage.color" /><span>{{ getStageProgress(stage) }}%</span></div>
                  <div class="stage-hours"><b>{{ stage.hours }}h</b><span>预计投入</span></div>
                  <el-icon class="collapse-icon"><ArrowDown v-if="stage.collapsed" /><ArrowUp v-else /></el-icon>
                </div>
              </div>
              <template v-if="!stage.collapsed">
                <div class="stage-skills"><span v-for="skill in stage.skills" :key="skill">{{ skill }}</span></div>
                <div class="task-list">
                  <div v-for="task in stage.tasks" :key="task.name" class="task-wrapper" :class="task.status" :data-task="task.name">
                    <label class="task">
                      <div class="task-left">
                        <el-checkbox v-model="task.done" @change="saveProgress" />
                        <div class="task-content">
                          <div class="task-header">
                            <b :class="{finished:task.done}">{{ task.name }}</b>
                            <el-tag :type="getTaskStatusType(task.status)" size="small">{{ getTaskStatusLabel(task.status) }}</el-tag>
                            <el-tag v-if="task.priority" :type="task.priority==='P0'?'danger':'warning'" size="small" effect="plain">{{ task.priority }}</el-tag>
                          </div>
                          <p>{{ task.desc }}</p>
                          <div v-if="task.dueDate" class="task-due"><el-icon><Clock /></el-icon><span>截止：{{ task.dueDate }}</span></div>
                        </div>
                      </div>
                      <div class="task-right">
                        <el-tag v-if="task.output" size="small" effect="plain">{{ task.output }}</el-tag>
                        <div class="task-actions">
                          <el-button text size="small" @click.stop="openResource(task.name,'tutorial')"><el-icon><Reading /></el-icon>教程</el-button>
                          <el-button text size="small" @click.stop="openResource(task.name,'quiz')"><el-icon><Edit /></el-icon>题库</el-button>
                        </div>
                      </div>
                    </label>
                  </div>
                </div>
              </template>
              <!-- 阶段装饰 -->
              <div class="stage-deco">
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <circle cx="35" cy="5" r="4" :fill="stage.color" opacity="0.06"/>
                  <circle cx="30" cy="14" r="2" :fill="stage.color" opacity="0.04"/>
                </svg>
              </div>
            </div>
          </article>
        </section>
      </template>

      <!-- 日历视图 -->
      <template v-if="viewMode==='calendar'">
        <section class="calendar-view">
          <div class="calendar-header">
            <el-button @click="prevWeek" circle><el-icon><ArrowLeft /></el-icon></el-button>
            <h3>{{ currentWeekLabel }}</h3>
            <el-button @click="nextWeek" circle><el-icon><ArrowRight /></el-icon></el-button>
          </div>
          <div class="calendar-grid">
            <div v-for="day in weekDays" :key="day.date" class="calendar-day" :class="{today:isToday(day.date)}">
              <div class="day-header"><span class="day-name">{{ day.name }}</span><span class="day-date">{{ day.dateStr }}</span></div>
              <div class="day-tasks">
                <div v-for="task in day.tasks" :key="task.name" class="day-task" :class="{completed:task.done}" @click="scrollToSkillTask(task.name)"><span class="task-time">{{ task.time }}</span><span class="task-name">{{ task.name }}</span></div>
                <div v-if="!day.tasks.length" class="day-empty">暂无安排</div>
              </div>
            </div>
          </div>
        </section>
      </template>
      <!-- 成果区域 -->
      <section class="panel outcome-panel">
        <div class="outcome-header">
          <div class="outcome-icon"><el-icon><Trophy /></el-icon></div>
          <div><h3>完成路线后，你将获得</h3><p>可展示的技能提升成果与岗位匹配度提升</p></div>
        </div>
        <div class="outcome-chart"><div class="score-comparison" ref="outcomeChartRef"></div></div>
        <div class="outcome-actions">
          <el-button type="primary" @click="savePlan"><el-icon><FolderOpened /></el-icon>保存学习方案</el-button>
          <el-button @click="exportPDF"><el-icon><Document /></el-icon>导出PDF</el-button>
          <el-button @click="generateResumeDesc"><el-icon><EditPen /></el-icon>生成简历描述</el-button>
          <el-button @click="downloadPackage"><el-icon><Folder /></el-icon>打包下载</el-button>
        </div>
      </section>

      <!-- 进度详情弹窗 -->
      <el-dialog v-model="showProgressDetail" title="学习进度详情" width="600px">
        <div class="progress-detail">
          <div class="progress-summary">
            <div class="summary-item"><span>已完成</span><b class="success">{{ completedCount }}</b></div>
            <div class="summary-item"><span>进行中</span><b class="active">{{ inProgressCount }}</b></div>
            <div class="summary-item"><span>待开始</span><b class="pending">{{ pendingCount }}</b></div>
            <div class="summary-item"><span>总任务</span><b>{{ allTasks.length }}</b></div>
          </div>
          <div class="stage-progress-list">
            <div v-for="stage in currentPath.learningStages" :key="stage.title" class="stage-progress-item">
              <span>{{ stage.title }}</span>
              <el-progress :percentage="getStageProgress(stage)" :stroke-width="8" :color="stage.color" />
            </div>
          </div>
        </div>
      </el-dialog>

      <!-- 学习资源弹窗 -->
      <el-dialog v-model="showResourceDialog" :title="resourceTitle" width="600px">
        <div class="resource-content" v-if="currentResource">
          <h4>推荐教程</h4>
          <ul><li v-for="t in currentResource.tutorials" :key="t">{{ t }}</li></ul>
          <h4>题库</h4>
          <ul><li v-for="q in currentResource.quizzes" :key="q">{{ q }}</li></ul>
          <h4>实战项目</h4>
          <ul><li v-for="p in currentResource.projects" :key="p">{{ p }}</li></ul>
        </div>
        <div v-else class="resource-empty">暂无相关学习资源</div>
      </el-dialog>

      <!-- 简历描述弹窗 -->
      <el-dialog v-model="showResumeDialog" title="生成的简历描述" width="600px">
        <div class="resume-desc-content">
          <pre>{{ resumeDescription }}</pre>
          <el-button type="primary" @click="copyResumeDesc" style="margin-top:16px"><el-icon><CopyDocument /></el-icon>复制到剪贴板</el-button>
        </div>
      </el-dialog>

      <!-- 浮动数据抽屉 -->
      <div class="floating-drawer" :class="{expanded:drawerExpanded}" @click="drawerExpanded=!drawerExpanded">
        <div class="drawer-header"><el-icon><DataLine /></el-icon><span v-if="drawerExpanded">学习统计</span></div>
        <div v-if="drawerExpanded" class="drawer-content">
          <div class="stat-item"><span>总学习时长</span><b>{{ totalHours }}h</b></div>
          <div class="stat-item"><span>已完成任务</span><b class="success">{{ completedCount }}/{{ allTasks.length }}</b></div>
          <div class="stat-item"><span>当前进度</span><b>{{ progress }}%</b></div>
          <div class="stat-item"><span>预计完成</span><b>{{ estimatedWeeks }}周</b></div>
          <div class="drawer-chart"><div ref="drawerChartRef"></div></div>
        </div>
      </div>

    </template>
  </section>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { Download, List, Calendar, ArrowDown, ArrowUp, ArrowLeft, ArrowRight, Connection, Clock, Reading, Edit, Trophy, FolderOpened, Document, EditPen, Folder, DataLine, CopyDocument } from '@element-plus/icons-vue'


const router = useRouter()
const route = useRoute()

const loading = ref(true)
const selectedJob = ref('')
const viewMode = ref<'roadmap'|'calendar'>('roadmap')
const dailyHours = ref(2)
const showProgressDetail = ref(false)
const showResourceDialog = ref(false)
const showResumeDialog = ref(false)
const drawerExpanded = ref(false)
const selectedTags = ref<string[]>([])
const currentWeekStart = ref(new Date())

const heroRadarRef = ref<HTMLElement>()
const outcomeChartRef = ref<HTMLElement>()
const drawerChartRef = ref<HTMLElement>()
const trendRefs = ref<Record<string,HTMLElement>>({})

const resourceTitle = ref('')
const currentResource = ref<any>(null)
const resumeDescription = ref('')

const jobPaths = ref({} as Record<string, any>)
const learningResources = {} as Record<string, any>
const currentPath = computed(()=>jobPaths.value[selectedJob.value])

const estimatedWeeks = computed(()=>{
  if(!currentPath.value) return 0
  const total = currentPath.value.learningStages.reduce((s: number, st: any)=>s+st.hours,0)
  return Math.ceil(total/(dailyHours.value*7))
})

const allTasks = computed(()=>{
  if(!currentPath.value) return []
  return currentPath.value.learningStages.flatMap((st: any)=>st.tasks)
})

const filteredPrioritySkills = computed(()=>{
  if(!currentPath.value) return []
  let skills = currentPath.value.prioritySkills
  if(selectedTags.value.length>0) skills = skills.filter((s: any)=>selectedTags.value.includes(s.name))
  return skills
})

const filteredStages = computed(()=>{
  if(!currentPath.value) return []
  let stages = currentPath.value.learningStages
  if(selectedTags.value.length>0){
    stages = stages.map((s: any)=>({...s,tasks:s.tasks.filter((t: any)=>selectedTags.value.some((tag: any)=>t.name.includes(tag)||t.desc.includes(tag)))})).filter((s: any)=>s.tasks.length>0)
  }
  return stages
})

const allSkills = computed(()=>{
  if(!currentPath.value) return []
  const skills = new Set<string>()
  currentPath.value.prioritySkills.forEach((s: any)=>skills.add(s.name))
  currentPath.value.learningStages.forEach((st: any)=>st.skills.forEach((s: any)=>skills.add(s)))
  return Array.from(skills)
})

const completedCount = computed(()=>allTasks.value.filter((t: any)=>t.done).length)
const inProgressCount = computed(()=>allTasks.value.filter((t: any)=>t.status==='in-progress').length)
const pendingCount = computed(()=>allTasks.value.filter((t: any)=>t.status==='pending').length)
const progress = computed(()=>allTasks.value.length?Math.round(completedCount.value/allTasks.value.length*100):0)
const totalHours = computed(()=>currentPath.value?.learningStages.reduce((s: number, st: any)=>s+st.hours,0)||0)

const weekDays = computed(()=>{
  const days:any[] = []
  const names = ['周一','周二','周三','周四','周五','周六','周日']
  const start = new Date(currentWeekStart.value)
  for(let i=0;i<7;i++){
    const d = new Date(start); d.setDate(start.getDate()+i)
    days.push({name:names[i],date:d,dateStr:`${d.getMonth()+1}/${d.getDate()}`,tasks:getTasksForDate(d)})
  }
  return days
})

const currentWeekLabel = computed(()=>{
  const s = new Date(currentWeekStart.value)
  const e = new Date(s); e.setDate(s.getDate()+6)
  return `${s.getMonth()+1}月${s.getDate()}日 - ${e.getMonth()+1}月${e.getDate()}日`
})

function generatePath(job:string){selectedJob.value=job;loading.value=true;setTimeout(()=>{loading.value=false;nextTick(initCharts)},800)}
function switchJob(job:string){selectedJob.value=job;nextTick(initCharts)}
function updateEstimatedWeeks(){}
function toggleTag(tag:string){const i=selectedTags.value.indexOf(tag);if(i>=0)selectedTags.value.splice(i,1);else selectedTags.value.push(tag)}
function getStageProgress(stage:any){return stage.tasks.length?Math.round(stage.tasks.filter((t:any)=>t.done).length/stage.tasks.length*100):0}
function getTaskStatusType(s:string){return{completed:'success','in-progress':'',pending:'info',overdue:'danger'}[s]||'info'}
function getTaskStatusLabel(s:string){return{completed:'已完成','in-progress':'进行中',pending:'待开始',overdue:'已逾期'}[s]||'待开始'}
function scrollToSkillTask(name:string){const el=document.querySelector(`[data-task="${name}"]`);if(el){el.scrollIntoView({behavior:'smooth',block:'center'});el.classList.add('highlight');setTimeout(()=>el.classList.remove('highlight'),2000)}}
function goToGraph(id:string){router.push({path:'/graph',query:{highlight:id}})}
function batchAddToPlan(){const sel=currentPath.value.prioritySkills.filter((s:any)=>s.selected);if(!sel.length){ElMessage.warning('请先选择要加入学习规划的技能');return}ElMessage.success(`已将${sel.length}项技能加入学习规划`)}
function openResource(name:string,_type:string){resourceTitle.value=`${name} - 学习资源`;currentResource.value=learningResources[name]||null;showResourceDialog.value=true}
function saveProgress(){ElMessage.success('学习进度已保存')}
function savePlan(){if(!currentPath.value){ElMessage.warning('暂无学习路径数据');return}ElMessage.success('学习方案已保存')}
function exportPDF(){ElMessage.success('PDF导出功能开发中')}
function generateResumeDesc(){if(!currentPath.value)return;const skills=currentPath.value.outcome.skills.join('、');resumeDescription.value=`技能提升项目（${currentPath.value.jobTitle}方向）\n\n• 系统学习了${skills}等核心技能\n• 完成了${allTasks.value.length}个学习任务，累计投入${totalHours.value}小时\n• 通过项目实战，将岗位匹配度从${currentPath.value.currentScore}分提升至${currentPath.value.targetScore}分\n• 具备独立完成相关岗位核心工作的能力`;showResumeDialog.value=true}
function copyResumeDesc(){navigator.clipboard.writeText(resumeDescription.value);ElMessage.success('已复制到剪贴板')}
function downloadPackage(){ElMessage.success('成果打包下载功能开发中')}
function prevWeek(){const d=new Date(currentWeekStart.value);d.setDate(d.getDate()-7);currentWeekStart.value=d}
function nextWeek(){const d=new Date(currentWeekStart.value);d.setDate(d.getDate()+7);currentWeekStart.value=d}
function isToday(d:Date){return d.toDateString()===new Date().toDateString()}
function getTasksForDate(d:Date){if(!currentPath.value)return[];const ds=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;const tasks:any[]=[];currentPath.value.learningStages.forEach((st: any)=>{st.tasks.forEach((t: any)=>{if(t.dueDate===ds)tasks.push({...t,time:'09:00'})})});return tasks}
function setTrendRef(el:any,name:string){if(el)trendRefs.value[name]=el}
function tooltipHours(v: any){return v + 'h'}
function allTasksDone(tasks: any[]){return tasks.every((t: any)=>t.done)}

function initCharts(){initHeroRadar();initTrendCharts();initOutcomeChart();initDrawerChart()}
function initHeroRadar(){if(!heroRadarRef.value||!currentPath.value)return;const c=echarts.init(heroRadarRef.value);const skills=currentPath.value.prioritySkills.slice(0,5);c.setOption({radar:{indicator:skills.map((s:any)=>({name:s.name,max:100})),shape:'polygon',splitArea:{areaStyle:{color:['rgba(224,123,109,0.08)','rgba(224,123,109,0.03)']}}},series:[{type:'radar',data:[{value:skills.map((s:any)=>s.impact),name:'能力缺口',areaStyle:{color:'rgba(224,123,109,0.25)'},lineStyle:{color:'#E07B6D'},itemStyle:{color:'#E07B6D'}}]}]})}
function initTrendCharts(){if(!currentPath.value)return;currentPath.value.prioritySkills.forEach((skill:any)=>{const el=trendRefs.value[skill.name];if(!el)return;const c=echarts.init(el);c.setOption({grid:{top:5,right:5,bottom:5,left:5},xAxis:{type:'category',show:false,data:['1月','2月','3月','4月','5月']},yAxis:{type:'value',show:false},series:[{type:'line',data:skill.trend,smooth:true,showSymbol:false,lineStyle:{color:skill.level==='high'?'#E07B6D':'#FFA726',width:2},areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:skill.level==='high'?'rgba(224,123,109,0.3)':'rgba(255,167,38,0.3)'},{offset:1,color:'rgba(255,255,255,0)'}])}}]})})}
function initOutcomeChart(){if(!outcomeChartRef.value||!currentPath.value)return;const c=echarts.init(outcomeChartRef.value);c.setOption({grid:{top:30,right:30,bottom:30,left:80},xAxis:{type:'value',max:100},yAxis:{type:'category',data:['当前分数','目标分数'],axisLabel:{fontSize:14,color:'#3D3D3D'}},series:[{type:'bar',data:[{value:currentPath.value.currentScore,itemStyle:{color:'#E07B6D',borderRadius:[0,6,6,0]}},{value:currentPath.value.targetScore,itemStyle:{color:'#66BB6A',borderRadius:[0,6,6,0]}}],barWidth:30,label:{show:true,position:'right',formatter:'{c} 分',color:'#8C8C8C'}}]})}
function initDrawerChart(){if(!drawerChartRef.value||!currentPath.value)return;const c=echarts.init(drawerChartRef.value);c.setOption({radar:{indicator:currentPath.value.prioritySkills.slice(0,5).map((s:any)=>({name:s.name,max:100})),shape:'circle',splitNumber:4,axisName:{color:'#8C8C8C',fontSize:10}},series:[{type:'radar',data:[{value:currentPath.value.prioritySkills.slice(0,5).map((s:any)=>s.impact),name:'能力缺口',areaStyle:{color:'rgba(224,123,109,0.15)'},lineStyle:{color:'#E07B6D'},itemStyle:{color:'#E07B6D'}}]}]})}

onMounted(()=>{
  const jobFromQuery = route.query.job as string
  if(jobFromQuery && jobPaths.value[jobFromQuery]) selectedJob.value = jobFromQuery
  setTimeout(()=>{loading.value=false;nextTick(()=>{if(selectedJob.value)initCharts()})},1000)
})
</script>
<style scoped>
.roadmap-page{max-width:1440px;margin:auto;position:relative;overflow:hidden}

/* 装饰 */




/* 骨架屏 */
.skeleton-screen{padding:20px 0}
.skeleton-banner{height:180px;background:linear-gradient(135deg,#FDE8E4,#FDF5F0);border-radius:16px;margin-bottom:20px;animation:pulse 1.5s infinite}
.skeleton-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:20px}
.skeleton-card{height:120px;background:#F5F0EA;border-radius:12px;animation:pulse 1.5s infinite}
.skeleton-stages{display:grid;gap:16px}
.skeleton-stage{height:200px;background:#F5F0EA;border-radius:12px;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.6}}

/* 空状态 */
.empty-guide{text-align:center;padding:80px 20px}
.empty-illustration{margin-bottom:24px}
.empty-guide h2{font-size:22px;font-weight:600;color:#3D3D3D;margin:0 0 8px}
.empty-guide p{font-size:14px;color:#8C8C8C;margin:0 0 24px}

/* 标题栏 */
.page-title{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;flex-wrap:wrap;gap:16px}
.learning-banner{margin-bottom:18px;border-radius:14px;overflow:hidden}
.page-title h1{font-size:22px;font-weight:600;color:#3D3D3D;margin:0 0 4px}
.page-title>p,.page-title p{font-size:13px;color:#8C8C8C;margin:0}
.roadmap-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}

/* Hero 区域 */

.roadmap-hero{background:linear-gradient(135deg,#E07B6D 0%,#E8948A 50%,#F0A899 100%);border-radius:16px;padding:28px;margin-bottom:20px;color:#fff;position:relative;overflow:hidden}
.hero-content{display:flex;align-items:center;gap:24px;position:relative;z-index:1}
.hero-radar{width:180px;height:180px;flex-shrink:0}
.radar-chart{width:100%;height:100%}
.hero-info{flex:1}
.hero-info span{font-size:13px;opacity:0.85}
.hero-info h2{font-size:22px;font-weight:600;margin:6px 0 8px}
.hero-info h2 b{color:#fff;text-decoration:underline;text-underline-offset:3px}
.hero-info p{font-size:13px;opacity:0.9;margin:0 0 16px}
.daily-hours-selector{display:flex;align-items:center;gap:10px;background:rgba(255,255,255,0.15);border-radius:10px;padding:10px 14px;font-size:13px;backdrop-filter:blur(4px)}
.daily-hours-selector span:first-child{white-space:nowrap}
.daily-hours-selector .el-slider{flex:1;max-width:160px}
.hours-value{font-weight:600;min-width:30px}
.hero-progress{cursor:pointer;flex-shrink:0;transition:transform 0.2s}
.hero-progress:hover{transform:scale(1.05)}
.hero-deco{position:absolute;right:20px;top:20px;opacity:0.6}

/* 技能标签 */
.tech-tags-filter{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}
.tech-tags-filter .el-tag{cursor:pointer;transition:all 0.2s}
.tech-tags-filter .el-tag:hover{background:#FDE8E4;color:#E07B6D;border-color:#FDE8E4}

/* 面板 */
.panel{background:#fff;border:none;border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,0.04);padding:20px}
.panel-head{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.panel-head h3{font-size:15px;font-weight:600;color:#3D3D3D;margin:0 0 3px}
.panel-head p{font-size:11px;color:#B0B0B0;margin:0}

/* 优先技能 */
.priority-panel{margin-bottom:24px}
.priority-actions{display:flex;gap:10px;align-items:center}
.priority-list{display:grid;gap:10px}
.priority-item{display:grid;grid-template-columns:auto auto 1fr auto 80px 120px auto;align-items:center;gap:12px;padding:14px;border-radius:12px;background:#FDFBF7;cursor:pointer;transition:all 0.2s}
.priority-item:hover{background:#FDF7F5;transform:translateX(2px)}
.priority-item.high{border-left:3px solid #E07B6D}
.priority-item.medium{border-left:3px solid #FFA726}
.priority-checkbox{display:flex;align-items:center}
.priority-index{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600}
.priority-index.high{background:#FDE8E4;color:#E07B6D}
.priority-index.medium{background:#FFF3E0;color:#EF6C00}
.priority-name b{font-size:13px;color:#3D3D3D;display:block;margin-bottom:2px}
.priority-name p{font-size:11px;color:#8C8C8C;margin:0;line-height:1.4}
.skill-trend{width:80px;height:32px}
.trend-chart{width:100%;height:100%}
.skill-impact{display:flex;flex-direction:column;gap:4px}
.skill-impact span{font-size:10px;color:#B0B0B0}

/* 时间线 */
.roadmap-heading{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.roadmap-heading h2{font-size:18px;font-weight:600;color:#3D3D3D;margin:0 0 4px}
.roadmap-heading p{font-size:12px;color:#8C8C8C;margin:0}
.roadmap-stats{display:flex;align-items:center;gap:12px;font-size:12px;color:#8C8C8C}
.roadmap-stats b{color:#E07B6D}
.timeline{padding-left:52px;position:relative}
.stage{position:relative;padding-bottom:18px}
.stage:before{content:'';position:absolute;left:-27px;top:44px;bottom:-3px;border-left:2px dashed #F0EBE3}
.stage:last-child:before{display:none}
.stage-marker{position:absolute;left:-52px;top:19px;width:46px;height:46px;border-radius:50%;background:#FDE8E4;border:4px solid #FDF5F0;color:#E07B6D;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:1}
.stage-marker.done{background:#E8F5E9;color:#66BB6A}
.stage-marker span{font-size:15px;font-weight:700}
.stage-marker small{font-size:9px}
.stage-card{padding:20px;position:relative}
.stage-card.collapsed .task-list,.stage-card.collapsed .stage-skills{display:none}
.stage-card-head{display:flex;justify-content:space-between;align-items:flex-start;cursor:pointer}
.stage-label{display:inline-block;border-radius:6px;padding:4px 8px;font-size:11px;font-weight:600}
.stage-card h2{font-size:16px;font-weight:600;color:#3D3D3D;margin:8px 0 4px}
.stage-card p{font-size:12px;color:#8C8C8C;margin:0;line-height:1.5}
.stage-right{display:flex;align-items:center;gap:14px}
.stage-progress-mini{display:flex;align-items:center;gap:8px;min-width:100px}
.stage-progress-mini span{font-size:12px;color:#E07B6D;font-weight:600}
.stage-hours{text-align:right}
.stage-hours b{font-size:20px;color:#E07B6D}
.stage-hours span{font-size:10px;color:#B0B0B0;display:block;margin-top:2px}
.collapse-icon{font-size:18px;color:#B0B0B0}
.stage-deco{position:absolute;top:0;right:0;pointer-events:none}
.stage-skills{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}
.stage-skills span{background:#FDF7F5;color:#E07B6D;border-radius:6px;padding:4px 10px;font-size:11px;font-weight:500}

/* 任务列表 */
.task-list{border-top:1px solid #F5F0EA}
.task-wrapper{transition:all 0.3s}
.task-wrapper.highlight{background:#FFF3CD;border-radius:6px}
.task-wrapper.completed{opacity:0.6}
.task-wrapper.overdue{background:#FEF2F2}
.task{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:11px 0;border-bottom:1px solid #FAF7F2}
.task:last-child{border:0}
.task-left{display:flex;align-items:flex-start;gap:12px;flex:1}
.task-content{flex:1}
.task-header{display:flex;align-items:center;gap:6px;margin-bottom:4px;flex-wrap:wrap}
.task-header b{font-size:13px;color:#3D3D3D}
.task-header b.finished{text-decoration:line-through;color:#B0B0B0}
.task p{font-size:11px;margin:3px 0 0;color:#8C8C8C}
.task-due{display:flex;align-items:center;gap:4px;font-size:10px;color:#B0B0B0;margin-top:5px}
.task-right{display:flex;align-items:center;gap:10px;flex-shrink:0}
.task-actions{display:flex;gap:4px}

/* 日历视图 */
.calendar-view{margin-bottom:24px}
.calendar-header{display:flex;align-items:center;justify-content:center;gap:16px;margin-bottom:20px}
.calendar-header h3{margin:0;min-width:200px;text-align:center;font-size:15px;color:#3D3D3D}
.calendar-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:10px}
.calendar-day{background:#fff;border:1px solid #F0EBE3;border-radius:12px;min-height:140px;padding:12px}
.calendar-day.today{border-color:#E07B6D;background:#FDF7F5}
.day-header{display:flex;justify-content:space-between;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid #FAF7F2}
.day-name{font-size:12px;color:#8C8C8C}
.day-date{font-size:13px;font-weight:600;color:#3D3D3D}
.day-tasks{display:flex;flex-direction:column;gap:5px}
.day-task{padding:5px 8px;background:#FDF7F5;border-radius:6px;cursor:pointer;font-size:11px;transition:background 0.2s}
.day-task:hover{background:#FDE8E4}
.day-task.completed{background:#E8F5E9;text-decoration:line-through}
.task-time{color:#B0B0B0;margin-right:4px}
.task-name{color:#3D3D3D}
.day-empty{font-size:11px;color:#D5C8BC;text-align:center;padding:20px 0}

/* 成果区域 */
.outcome-panel{background:linear-gradient(135deg,#FDF7F5,#FDF5F0);border:1px solid #FDE8E4}
.outcome-header{display:flex;align-items:center;gap:14px;margin-bottom:20px}
.outcome-icon{width:44px;height:44px;border-radius:50%;background:#FDE8E4;display:flex;align-items:center;justify-content:center;color:#E07B6D;font-size:20px}
.outcome-header h3{font-size:15px;font-weight:600;color:#3D3D3D;margin:0 0 4px}
.outcome-header p{font-size:12px;color:#8C8C8C;margin:0}
.outcome-chart{height:150px;margin-bottom:20px}
.score-comparison{width:100%;height:100%}
.outcome-actions{display:flex;gap:10px;flex-wrap:wrap}

/* 弹窗 */
.progress-detail{padding:8px}
.progress-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
.summary-item{text-align:center;padding:14px;background:#FDFBF7;border-radius:10px}
.summary-item span{display:block;font-size:11px;color:#8C8C8C;margin-bottom:6px}
.summary-item b{font-size:22px;color:#3D3D3D}
.summary-item b.success{color:#66BB6A}
.summary-item b.active{color:#E07B6D}
.summary-item b.pending{color:#B0B0B0}
.stage-progress-item{display:flex;align-items:center;gap:14px;margin-bottom:10px}
.stage-progress-item span{min-width:140px;font-size:13px;color:#3D3D3D}
.resource-content{padding:8px}
.resource-content h4{margin:14px 0 6px;font-size:14px;color:#3D3D3D}
.resource-content ul{margin:0;padding-left:18px}
.resource-content li{margin-bottom:6px;font-size:13px;color:#555}
.resource-empty{text-align:center;padding:40px;color:#B0B0B0}
.resume-desc-content pre{background:#FDFBF7;padding:16px;border-radius:10px;font-size:13px;line-height:1.7;color:#3D3D3D;white-space:pre-wrap}

/* 浮动抽屉 */
.floating-drawer{position:fixed;right:20px;top:50%;transform:translateY(-50%);background:#fff;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.08);z-index:100;overflow:hidden;transition:all 0.3s;cursor:pointer}
.floating-drawer:not(.expanded){width:48px;height:48px}
.floating-drawer.expanded{width:240px}
.drawer-header{display:flex;align-items:center;gap:8px;padding:12px 16px;background:linear-gradient(135deg,#E07B6D,#E8948A);color:#fff;font-size:13px;font-weight:600}
.drawer-content{padding:14px}
.drawer-chart{margin-top:12px;height:140px}
.stat-item{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid #F5F0EA}
.stat-item:last-child{border-bottom:none}
.stat-item span{font-size:11px;color:#8C8C8C}
.stat-item b{font-size:13px;color:#3D3D3D}
.stat-item b.success{color:#66BB6A}

/* 响应式 */
@media(max-width:1200px){.priority-item{grid-template-columns:auto auto 1fr auto auto}.skill-trend,.skill-impact{display:none}}
@media(max-width:950px){.hero-content{flex-direction:column;text-align:center}.hero-radar{width:140px;height:140px}.daily-hours-selector{justify-content:center}.calendar-grid{grid-template-columns:1fr}.floating-drawer{display:none}}
@media(max-width:680px){.page-title{flex-direction:column;align-items:flex-start;gap:12px}.roadmap-actions{width:100%;flex-wrap:wrap}.priority-item{grid-template-columns:1fr;gap:8px}.timeline{padding-left:42px}.stage-marker{left:-42px;width:38px;height:38px}.stage:before{left:-22px}.page-deco{display:none}}
</style>