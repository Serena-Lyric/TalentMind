<template>
  <div class="app-shell">
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
          <div class="user-chip"><img src="/guangzhou-school.jpg" alt="广州应用科技学院" /><b>广州应用科技学院</b></div>
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
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
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

const route = useRoute()
const sidebarCollapsed = ref(false)

const navItems = [
  { label: '能力动态更新', path: '/evolution', icon: TrendCharts },
  { label: 'JD岗位管理', path: '/jobs', icon: Files },
  { label: '采集图谱', path: '/graph', icon: Collection },
  { label: '采集模块管理', path: '/collection', icon: Connection },
  { label: '简历分析', path: '/resume', icon: Document },
  { label: '技能学习路径', path: '/learning', icon: MagicStick },
]

const currentTitle = computed(() => String(route.meta.title || '数据概览'))
function isActive(path: string) {
  return route.path === path || route.path.startsWith(`${path}/`)
}
</script>
