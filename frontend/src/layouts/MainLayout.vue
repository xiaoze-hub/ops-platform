<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import {
  DataAnalysis,
  Document,
  Fold,
  Expand,
  Monitor,
  Moon,
  Search,
  Setting,
  Sunny,
  User,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { globalSearch, useThemeStore } from '@/stores/theme'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { isDark, toggleTheme } = useThemeStore()

const collapsed = ref(false)
const pageTitle = computed(() => {
  const title = route.meta.title as string | undefined
  return title || '运维平台'
})

const menus = [
  { path: '/', icon: DataAnalysis, title: '总览' },
  { path: '/nodes', icon: Monitor, title: '节点管理' },
  { path: '/logs', icon: Document, title: '日志检索' },
  { path: '/settings', icon: Setting, title: '系统设置' },
]

function isActive(path: string) {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
}

async function onLogout() {
  try {
    await ElMessageBox.confirm('确认退出登录？', '提示', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  auth.logout()
  ElMessage.success('已退出')
  router.push({ name: 'login' })
}

async function onChangePassword() {
  let oldPassword = ''
  let newPassword = ''
  let confirm = ''
  try {
    await ElMessageBox.prompt('请输入当前密码', '修改密码', {
      inputType: 'password',
      inputPlaceholder: '当前密码',
      confirmButtonText: '下一步',
      cancelButtonText: '取消',
      inputValidator: (v: string) => (v && v.length > 0 ? true : '请输入当前密码'),
    }).then(({ value }) => {
      oldPassword = value
    })
    await ElMessageBox.prompt('请输入新密码（至少 8 位）', '修改密码', {
      inputType: 'password',
      inputPlaceholder: '新密码',
      confirmButtonText: '下一步',
      cancelButtonText: '取消',
      inputValidator: (v: string) => (v && v.length >= 8 ? true : '新密码至少 8 位'),
    }).then(({ value }) => {
      newPassword = value
    })
    await ElMessageBox.prompt('请再次输入新密码', '修改密码', {
      inputType: 'password',
      inputPlaceholder: '确认新密码',
      confirmButtonText: '确认修改',
      cancelButtonText: '取消',
      inputValidator: (v: string) => (v === newPassword ? true : '两次密码不一致'),
    }).then(({ value }) => {
      confirm = value
    })
  } catch {
    return
  }
  if (confirm !== newPassword) return
  try {
    await auth.changePassword(oldPassword, newPassword)
    ElMessage.success('密码已更新')
  } catch {
    // error already toasted by axios
  }
}

function onUserCommand(cmd: string | number | object) {
  const key = String(cmd)
  if (key === 'logout') void onLogout()
  if (key === 'password') void onChangePassword()
  if (key === 'settings') void router.push({ name: 'settings' })
}

</script>

<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar">
      <div class="brand">
        <span v-if="!collapsed" class="brand-title">运维平台</span>
        <span v-else class="brand-title mini">运</span>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="collapsed"
        class="side-menu"
        router
      >
        <el-menu-item
          v-for="item in menus"
          :key="item.path"
          :index="item.path"
          :class="{ 'is-active-custom': isActive(item.path) }"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="main-col">
      <el-header class="topbar" height="56px">
        <div class="topbar-left">
          <el-button text @click="collapsed = !collapsed">
            <el-icon>
              <Expand v-if="collapsed" />
              <Fold v-else />
            </el-icon>
          </el-button>
          <span class="page-title">{{ pageTitle }}</span>
        </div>
        <div class="topbar-right">
          <el-input
            v-model="globalSearch"
            class="search-input"
            placeholder="搜索 hostname / IP"
            clearable
            :prefix-icon="Search"
          />
          <el-tooltip :content="isDark ? '切换到浅色' : '切换到深色'">
            <el-button circle @click="toggleTheme">
              <el-icon>
                <Sunny v-if="isDark" />
                <Moon v-else />
              </el-icon>
            </el-button>
          </el-tooltip>
          <el-dropdown trigger="click" @command="onUserCommand">
            <div class="avatar-wrap">
              <el-avatar :size="32" class="avatar">
                <el-icon><User /></el-icon>
              </el-avatar>
              <span v-if="!collapsed" class="username">{{ auth.username.value || 'admin' }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item command="settings">系统设置</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="content">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  min-height: 100vh;
}

.sidebar {
  background: var(--ops-card);
  border-right: 1px solid var(--ops-border);
  transition: width 0.2s ease;
  overflow: hidden;
}

.brand {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid var(--ops-border);
  font-weight: 700;
  font-size: 16px;
  color: var(--ops-text);
}

.brand-title.mini {
  font-size: 18px;
}

.side-menu {
  border-right: none;
  background: transparent;
}

.main-col {
  min-width: 0;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--ops-card);
  border-bottom: 1px solid var(--ops-border);
  padding: 0 16px;
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.page-title {
  font-weight: 600;
  font-size: 15px;
  white-space: nowrap;
}

.search-input {
  width: 220px;
}

.avatar-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--ops-text);
}

.username {
  font-size: 13px;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content {
  padding: 0;
  background: var(--ops-bg);
}

@media (max-width: 720px) {
  .search-input {
    width: 140px;
  }

  .username {
    display: none;
  }
}
</style>
