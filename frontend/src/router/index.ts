import { createRouter, createWebHashHistory } from 'vue-router'
import { getCurrentUser } from '../utils/auth'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/collection' },
    { path: '/jobs', name: 'Jobs', component: () => import('../views/Jobs.vue'), meta: { title: '岗位画像探索' } },
    { path: '/graph', name: 'Graph', component: () => import('../views/Graph.vue'), meta: { title: '岗位星云图谱' } },
    { path: '/graph-collection', redirect: '/graph' },
    { path: '/collection', name: 'Collection', component: () => import('../views/Collection.vue'), meta: { title: '采集模块管理' } },
    { path: '/m2', name: 'M2', component: () => import('../views/M2.vue'), meta: { title: '岗位分析工作台' } },
    { path: '/evolution', name: 'Evolution', component: () => import('../views/JobEvolution.vue'), meta: { title: '能力动态更新' } },
    { path: '/resume', name: 'Resume', component: () => import('../views/Resume.vue'), meta: { title: '简历分析' } },
    { path: '/resume-demo', name: 'ResumeDemo', component: () => import('../views/ResumeDemo.vue'), meta: { title: '简历预览' } },
    { path: '/learning', name: 'Learning', component: () => import('../views/Learning.vue'), meta: { title: '技能学习路径' } },
    { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { title: '登录' } },
    { path: '/:pathMatch(.*)*', redirect: '/collection' },
  ],
})

router.beforeEach((to) => {
  document.title = `${String(to.meta.title || '岗位能力图谱')} - 岗位能力图谱`
  if (to.path === '/login') {
    return getCurrentUser() ? { path: '/collection' } : true
  }
  return getCurrentUser() ? true : { path: '/login', query: { redirect: to.fullPath } }
})

export default router
