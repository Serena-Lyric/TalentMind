import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      redirect: '/dashboard'
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('../views/Dashboard.vue'),
      meta: { title: '数据概览' }
    },
    {
      path: '/jobs',
      name: 'Jobs',
      component: () => import('../views/Jobs.vue'),
      meta: { title: 'JD岗位管理' }
    },
    {
      path: '/graph',
      name: 'Graph',
      component: () => import('../views/Graph.vue'),
      meta: { title: '全景能力图谱' }
    },
    {
      path: '/resume',
      name: 'Resume',
      component: () => import('../views/Resume.vue'),
      meta: { title: '简历匹配诊断' }
    },
    {
      path: '/resume-demo',
      name: 'ResumeDemo',
      component: () => import('../views/ResumeDemo.vue'),
      meta: { title: '简历预览' }
    },
    {
      path: '/learning',
      name: 'Learning',
      component: () => import('../views/Learning.vue'),
      meta: { title: '学习路径规划' }
    }
  ]
})

router.beforeEach((to, _from, next) => {
  const title = to.meta.title || '岗位能力图谱'
  document.title = title + ' - 岗位能力图谱'
  next()
})

export default router

