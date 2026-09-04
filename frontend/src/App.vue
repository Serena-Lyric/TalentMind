<template>
  <div v-if="isLoginRoute" class="login-route"><router-view /></div>
  <div v-else class="app-shell">
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-card">
        <div class="brand-row">
          <div class="brand-mark" aria-hidden="true"><img src="/guangzhou-school.jpg" alt="" /></div>
          <div class="brand-copy">
            <strong>TalentMind</strong>
            <small>面向数字经济的人才能力大脑<br />与岗位演化预测系统</small>
          </div>
          <button class="collapse-button" type="button" aria-label="折叠导航" @click="sidebarCollapsed = !sidebarCollapsed">
            <el-icon><DArrowLeft v-if="!sidebarCollapsed" /><DArrowRight v-else /></el-icon>
          </button>
        </div>

        <nav class="main-nav" aria-label="主导航">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>

          </router-link>
        </nav>

        <div class="sidebar-footer">
          <div class="footer-orbit orbit-one"></div>
          <div class="footer-orbit orbit-two"></div>
          <div class="footer-signal"><span></span><span></span><span></span></div>
          <p>数据驱动人才洞察</p>
        </div>
      </div>
    </aside>

    <main class="main-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
      <header class="topbar">
        <div class="breadcrumb">
          <span class="breadcrumb-root">岗位能力图谱</span>
          <el-icon><ArrowRight /></el-icon>
          <strong>{{ currentTitle }}</strong>
        </div>
        <div class="topbar-actions">
          <span class="system-state"><i></i>系统运行中</span>
          <el-tooltip content="当前版本的统一前端入口" placement="bottom">
            <el-icon class="topbar-info"><InfoFilled /></el-icon>
          </el-tooltip>
          <div class="user-chip"><img src="/guangzhou-school.jpg" alt="" /><b>{{ currentUser ? currentUser.username + ' · ' + currentUser.label : '未登录' }}</b></div>
          <el-button v-if="currentUser" class="btn-soft" size="small" @click="logout">退出登录</el-button>
        </div>
      </header>

      <section class="page-main">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowRight,
  Collection,
  DArrowLeft,
  DArrowRight,
  Document,
  Files,
  InfoFilled,
  MagicStick,
  TrendCharts,
  Connection,
} from '@element-plus/icons-vue'
import { clearCurrentUser, getCurrentUser, type DemoUser } from './utils/auth'

const route = useRoute()
const router = useRouter()
const sidebarCollapsed = ref(false)
const isLoginRoute = computed(() => route.path === '/login')
const currentUser = ref<DemoUser | null>(getCurrentUser())

watch(() => route.path, () => { currentUser.value = getCurrentUser() })

function logout() {
  clearCurrentUser()
  currentUser.value = null
  router.replace('/login')
}

const navItems = [
  { label: '采集模块管理', path: '/collection', icon: Connection },
  { label: 'JD岗位管理', path: '/jobs', icon: Files },
  { label: '能力动态更新', path: '/evolution', icon: TrendCharts },
  { label: '岗位星云图谱', path: '/graph', icon: Collection },
  { label: '简历分析', path: '/resume', icon: Document },
  { label: '技能学习路径', path: '/learning', icon: MagicStick },
]

const currentTitle = computed(() => String(route.meta.title || '数据概览'))
function isActive(path: string) {
  return route.path === path || route.path.startsWith(`${path}/`)
}
</script>
