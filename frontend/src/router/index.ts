import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '数据概览' } },
    { path: '/jobs', name: 'Jobs', component: () => import('../views/Jobs.vue'), meta: { title: 'JD岗位管理' } },
    { path: '/graph', name: 'Graph', component: () => import('../views/Graph.vue'), meta: { title: '岗位星云图谱' } },
    { path: '/graph-collection', redirect: '/graph' },
    { path: '/analytics', name: 'Analytics', component: () => import('../views/Analytics.vue'), meta: { title: '数据分析' } },
    { path: '/collection', name: 'Collection', component: () => import('../views/Collection.vue'), meta: { title: '采集模块管理' } },
    { path: '/evolution', name: 'Evolution', component: () => import('../views/JobEvolution.vue'), meta: { title: '能力动态更新' } },
    { path: '/resume', name: 'Resume', component: () => import('../views/Resume.vue'), meta: { title: '简历分析' } },
    { path: '/resume-demo', name: 'ResumeDemo', component: () => import('../views/ResumeDemo.vue'), meta: { title: '简历预览' } },
    { path: '/learning', name: 'Learning', component: () => import('../views/Learning.vue'), meta: { title: '技能学习路径' } },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach((to) => {
  document.title = `${String(to.meta.title || '岗位能力图谱')} - 岗位能力图谱`
})

export default router