<template>
  <el-container class="app-shell">
    <!-- 页面装饰：右上角小圆点 -->
    <div class="page-deco deco-dots-tr">
      <svg width="120" height="80" viewBox="0 0 120 80" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="10" cy="10" r="3" fill="#E07B6D" opacity="0.12"/>
        <circle cx="30" cy="6" r="2" fill="#A8C5B8" opacity="0.15"/>
        <circle cx="50" cy="14" r="4" fill="#E07B6D" opacity="0.08"/>
        <circle cx="75" cy="8" r="2.5" fill="#B8C4D0" opacity="0.12"/>
        <circle cx="100" cy="12" r="3" fill="#A8C5B8" opacity="0.1"/>
        <circle cx="20" cy="30" r="2" fill="#B8C4D0" opacity="0.1"/>
        <circle cx="60" cy="35" r="3" fill="#E07B6D" opacity="0.06"/>
        <circle cx="90" cy="28" r="2" fill="#A8C5B8" opacity="0.12"/>
        <circle cx="110" cy="40" r="3.5" fill="#E07B6D" opacity="0.08"/>
        <circle cx="40" cy="55" r="2" fill="#B8C4D0" opacity="0.1"/>
        <circle cx="80" cy="60" r="2.5" fill="#A8C5B8" opacity="0.08"/>
        <circle cx="15" cy="70" r="3" fill="#E07B6D" opacity="0.06"/>
      </svg>
    </div>

    <aside class="sidebar">
      <div class="sidebar-inner">
        <div class="brand">
          <div class="brand-mark">
            <!-- 品牌图标：简约数据分析符号 -->
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect x="2" y="10" width="4" height="8" rx="1" fill="#fff" opacity="0.9"/>
              <rect x="8" y="6" width="4" height="12" rx="1" fill="#fff" opacity="0.7"/>
              <rect x="14" y="2" width="4" height="16" rx="1" fill="#fff" opacity="0.5"/>
            </svg>
          </div>
          <div class="brand-text">
            <span class="brand-name">职能图谱</span>
            <span class="brand-sub">岗位能力系统</span>
          </div>
        </div>

        <nav>
          <router-link
            v-for="item in nav"
            :key="item.key"
            :to="item.path"
            :class="{ active: route.path === item.path }"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </router-link>
        </nav>

        <div class="side-foot">
          <div class="side-illustration">
            <!-- 卡通风景+人物：窗边办公场景 -->
            <svg width="200" height="180" viewBox="0 0 200 180" fill="none" xmlns="http://www.w3.org/2000/svg">
              <!-- 窗户 -->
              <rect x="30" y="8" width="140" height="90" rx="8" fill="#E8F4FD" stroke="#D5C8BC" stroke-width="1.5"/>
              <line x1="100" y1="8" x2="100" y2="98" stroke="#D5C8BC" stroke-width="1"/>
              <line x1="30" y1="52" x2="170" y2="52" stroke="#D5C8BC" stroke-width="1"/>
              <!-- 窗外天空和云 -->
              <ellipse cx="60" cy="30" rx="18" ry="8" fill="#fff" opacity="0.7"/>
              <ellipse cx="72" cy="26" rx="12" ry="6" fill="#fff" opacity="0.6"/>
              <ellipse cx="140" cy="35" rx="14" ry="7" fill="#fff" opacity="0.5"/>
              <!-- 窗外山丘 -->
              <path d="M30 70 Q55 40 80 65 Q105 45 130 60 Q155 42 170 70 L170 98 L30 98 Z" fill="#A8C5B8" opacity="0.3"/>
              <path d="M30 80 Q60 55 90 75 Q120 58 150 72 Q165 60 170 80 L170 98 L30 98 Z" fill="#8BBFA0" opacity="0.25"/>
              <!-- 太阳 -->
              <circle cx="145" cy="22" r="10" fill="#FFD699" opacity="0.5"/>
              <circle cx="145" cy="22" r="6" fill="#FFBE5C" opacity="0.4"/>
              <!-- 小鸟 -->
              <path d="M50 18 Q53 14 56 18" stroke="#B8C4D0" stroke-width="1" fill="none" opacity="0.4"/>
              <path d="M60 15 Q63 11 66 15" stroke="#B8C4D0" stroke-width="1" fill="none" opacity="0.3"/>

              <!-- 桌子 -->
              <rect x="20" y="105" width="160" height="5" rx="2" fill="#D5C8BC" opacity="0.5"/>
              <rect x="35" y="110" width="3" height="25" rx="1.5" fill="#D5C8BC" opacity="0.3"/>
              <rect x="162" y="110" width="3" height="25" rx="1.5" fill="#D5C8BC" opacity="0.3"/>

              <!-- 笔记本电脑 -->
              <rect x="55" y="88" width="50" height="18" rx="2" fill="#F7F0EA" stroke="#D5C8BC" stroke-width="1"/>
              <rect x="58" y="91" width="44" height="10" rx="1" fill="#fff"/>
              <rect x="45" y="106" width="70" height="3" rx="1.5" fill="#D5C8BC" opacity="0.5"/>
              <!-- 屏幕内容 -->
              <rect x="61" y="94" width="8" height="5" rx="0.5" fill="#E07B6D" opacity="0.3"/>
              <rect x="72" y="93" width="12" height="6" rx="0.5" fill="#A8C5B8" opacity="0.3"/>
              <rect x="87" y="94" width="6" height="5" rx="0.5" fill="#B8C4D0" opacity="0.3"/>

              <!-- 咖啡杯 -->
              <rect x="120" y="95" width="14" height="16" rx="3" fill="#F5D5C8" stroke="#E0D5CA" stroke-width="0.8"/>
              <path d="M134 99 Q140 99 140 105 Q140 111 134 111" stroke="#E0D5CA" stroke-width="0.8" fill="none"/>
              <path d="M124 93 Q126 89 128 93" stroke="#D5C8BC" stroke-width="0.6" fill="none" opacity="0.4"/>
              <path d="M130 92 Q132 88 134 92" stroke="#D5C8BC" stroke-width="0.6" fill="none" opacity="0.3"/>

              <!-- 人物 - 坐着的姿态 -->
              <!-- 椅子 -->
              <rect x="75" y="115" width="30" height="4" rx="2" fill="#D5C8BC" opacity="0.4"/>
              <rect x="78" y="119" width="24" height="20" rx="4" fill="#D5C8BC" opacity="0.2"/>
              <!-- 身体 -->
              <path d="M78 108 Q78 100 90 100 Q102 100 102 108 L104 125 Q104 130 90 130 Q76 130 76 125 Z" fill="#E07B6D" opacity="0.2"/>
              <!-- 头部 -->
              <circle cx="90" cy="88" r="12" fill="#F5D5C8"/>
              <path d="M78 85 Q80 75 90 73 Q100 75 102 85" fill="#8B7B6B" opacity="0.5"/>
              <!-- 眼睛 -->
              <circle cx="85" cy="88" r="1.5" fill="#555" opacity="0.5"/>
              <circle cx="95" cy="88" r="1.5" fill="#555" opacity="0.5"/>
              <!-- 微笑 -->
              <path d="M86 92 Q90 95 94 92" stroke="#C09080" stroke-width="0.8" fill="none" opacity="0.5"/>
              <!-- 手臂操作键盘 -->
              <path d="M80 112 L65 104" stroke="#F5D5C8" stroke-width="2.5" stroke-linecap="round"/>
              <path d="M100 112 L115 104" stroke="#F5D5C8" stroke-width="2.5" stroke-linecap="round"/>
              <circle cx="64" cy="103.5" r="2" fill="#F5D5C8"/>
              <circle cx="116" cy="103.5" r="2" fill="#F5D5C8"/>

              <!-- 桌面装饰 -->
              <circle cx="145" cy="100" r="4" fill="#A8C5B8" opacity="0.2"/>
              <rect x="140" y="96" width="8" height="8" rx="2" fill="#A8C5B8" opacity="0.15"/>
              <circle cx="155" cy="98" r="2" fill="#D98B6E" opacity="0.15"/>

              <!-- 地面植物 -->
              <rect x="15" y="135" width="4" height="15" rx="2" fill="#A8C5B8" opacity="0.3"/>
              <circle cx="17" cy="130" r="6" fill="#A8C5B8" opacity="0.15"/>
              <circle cx="13" cy="133" r="4" fill="#A8C5B8" opacity="0.12"/>
              <circle cx="21" cy="133" r="4" fill="#A8C5B8" opacity="0.12"/>

              <!-- 右侧书架装饰 -->
              <rect x="165" y="80" width="20" height="3" rx="1" fill="#D5C8BC" opacity="0.3"/>
              <rect x="165" y="70" width="20" height="3" rx="1" fill="#D5C8BC" opacity="0.3"/>
              <rect x="168" y="73" width="5" height="7" rx="1" fill="#E07B6D" opacity="0.15"/>
              <rect x="174" y="74" width="5" height="6" rx="1" fill="#A8C5B8" opacity="0.15"/>
              <rect x="168" y="83" width="6" height="7" rx="1" fill="#B8C4D0" opacity="0.15"/>
            </svg>
          </div>
          <p class="side-copy">数据驱动人才洞察</p>
        </div>
      </div>
    </aside>

    <el-container>
      <el-header>
        <div class="breadcrumb">
          <span class="bc-root">岗位能力图谱</span>
          <span class="bc-sep">/</span>
          <span class="bc-cur">{{ currentTitle }}</span>
        </div>
        <div class="header-right">
          <div class="header-search">
            <el-icon><Search /></el-icon>
            <span>搜索...</span>
          </div>
          <el-badge is-dot :offset="[-2, 2]">
            <el-icon :size="18"><Bell /></el-icon>
          </el-badge>
          <el-avatar :size="32" style="background:#E07B6D;font-size:13px">管</el-avatar>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Bell, Search, DataAnalysis, Files, DocumentChecked, MagicStick, PieChart } from '@element-plus/icons-vue'

const route = useRoute()

const nav = [
  { key: 'dashboard', label: '数据概览', path: '/dashboard', icon: DataAnalysis },
  { key: 'jobs', label: 'JD岗位管理', path: '/jobs', icon: Files },
  { key: 'graph', label: '全景知识图谱', path: '/graph', icon: PieChart },
  { key: 'resume', label: '简历解析匹配', path: '/resume', icon: DocumentChecked },
  { key: 'path', label: '技能学习路径', path: '/learning', icon: MagicStick }
]

const currentTitle = computed(() => {
  const item = nav.find(x => x.path === route.path)
  return item ? item.label : '数据概览'
})
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: #FDFBF7;
  position: relative;
  overflow: hidden;
}

/* ===== 页面装饰 ===== */
.page-deco {
  position: fixed;
  z-index: 0;
  pointer-events: none;
}
.deco-dots-tr {
  top: 0;
  right: 0;
}

/* ===== 侧边栏：内部圆角区域，不顶天立地 ===== */
.sidebar {
  width: 240px;
  padding: 20px 14px;
  position: fixed;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 5;
  display: flex;
  flex-direction: column;
}

.sidebar-inner {
  background: #FFFFFF;
  border-radius: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px 16px;
  margin: 8px 0;
  overflow: hidden;
}

/* ===== 品牌区 ===== */
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 8px 20px;
  border-bottom: 1px solid #F5F0EA;
  margin-bottom: 8px;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #E07B6D 0%, #E8948A 100%);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.brand-text {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-size: 15px;
  font-weight: 600;
  color: #3D3D3D;
  line-height: 1.2;
}

.brand-sub {
  font-size: 11px;
  color: #B0B0B0;
  margin-top: 2px;
}

/* ===== 导航 ===== */
nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 8px;
}

nav a {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  color: #8C8C8C;
  font-size: 13px;
  font-weight: 400;
  text-decoration: none;
  transition: all 0.2s ease;
  border: none;
  background: none;
  cursor: pointer;
  width: 100%;
}

nav a .el-icon {
  font-size: 17px;
  flex-shrink: 0;
}

nav a:hover {
  background: #FDF7F5;
  color: #E07B6D;
}

nav a.active {
  background: #FDE8E4;
  color: #D96C63;
  font-weight: 500;
}

nav a.active .el-icon {
  color: #D96C63;
}

/* ===== 底部插图 ===== */
.side-foot {
  margin-top: auto;
  padding-top: 12px;
  text-align: center;
}

.side-illustration {
  display: flex;
  justify-content: center;
  margin-bottom: 6px;
  padding: 0 4px;
}

.side-copy {
  font-size: 11px;
  color: #B0B0B0;
  margin: 0;
  letter-spacing: 0.5px;
}

/* ===== 主容器 ===== */
.el-container > .el-container {
  margin-left: 240px;
}

.el-header {
  height: 64px;
  background: #FDFBF7;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  position: sticky;
  top: 0;
  z-index: 4;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.bc-root { color: #B0B0B0; }
.bc-sep { color: #D9D9D9; }
.bc-cur { color: #3D3D3D; font-weight: 500; }

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  color: #8C8C8C;
}

.header-search {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #FFFFFF;
  border: 1px solid #F0EBE3;
  border-radius: 10px;
  padding: 7px 14px;
  font-size: 12px;
  color: #B0B0B0;
  cursor: pointer;
  transition: border-color 0.2s;
}

.header-search:hover { border-color: #E07B6D; }
.header-search .el-icon { font-size: 14px; }

.el-main {
  padding: 24px 32px 40px;
  min-height: calc(100vh - 64px);
  background: #FDFBF7;
}

/* ===== 响应式 ===== */
@media (max-width: 760px) {
  .sidebar { width: 72px; padding: 12px 8px; }
  .sidebar-inner { padding: 16px 8px; }
  .brand-text, nav a span, .side-foot { display: none; }
  .brand { justify-content: center; padding-bottom: 16px; }
  nav a { justify-content: center; padding: 12px 0; }
  .el-container > .el-container { margin-left: 72px; }
  .el-header { padding: 0 16px; }
  .el-main { padding: 16px; }
  .header-search span { display: none; }
  .page-deco { display: none; }
}
</style>