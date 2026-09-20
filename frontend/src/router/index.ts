import { createRouter, createWebHistory } from 'vue-router'
import { getMustChangePassword, getToken } from '@/api/http'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { requiresAuth: false, title: '登录' },
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: '总览' },
        },
        {
          path: 'nodes',
          name: 'nodes',
          component: () => import('@/views/NodesView.vue'),
          meta: { title: '节点管理' },
        },
        {
          path: 'nodes/:node_id',
          name: 'node-detail',
          component: () => import('@/views/NodeDetailView.vue'),
          meta: { title: '节点详情' },
        },
        {
          path: 'logs',
          name: 'logs',
          component: () => import('@/views/LogsView.vue'),
          meta: { title: '日志检索' },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
          meta: { title: '系统设置' },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const authed = !!getToken()
  const mustChange = getMustChangePassword()
  if (to.meta.requiresAuth === false) {
    // Default-password sessions must stay on login until change-password succeeds.
    if (authed && mustChange) {
      return true
    }
    if (authed && to.name === 'login') {
      return { name: 'dashboard' }
    }
    return true
  }
  if (!authed) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (mustChange) {
    return { name: 'login', query: { force_change: '1', redirect: to.fullPath } }
  }
  return true
})

export default router
