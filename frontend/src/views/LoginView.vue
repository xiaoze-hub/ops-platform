<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { getMustChangePassword, getUsername } from '@/api/http'
import { Moon, Sunny } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { isDark, toggleTheme } = useThemeStore()

const form = reactive({
  username: 'admin',
  password: '',
})

const loading = ref(false)
const showChange = ref(false)
const changeForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})
const changeLoading = ref(false)

let pendingRedirect = ''

onMounted(() => {
  const force = route.query.force_change === '1'
  if ((force || getMustChangePassword()) && auth.isLoggedIn.value) {
    form.username = getUsername() || form.username
    showChange.value = true
    ElMessage.warning('请先修改默认密码后再使用平台')
  }
})

async function onSubmit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const data = await auth.login(form.username, form.password)
    pendingRedirect = (route.query.redirect as string) || '/'
    if (data.must_change_password) {
      showChange.value = true
      changeForm.oldPassword = form.password
      ElMessage.warning('首次登录请修改默认密码')
      return
    }
    redirectAfterLogin()
  } catch {
    // axios interceptor already showed error
  } finally {
    loading.value = false
  }
}

function redirectAfterLogin() {
  const redirect = (route.query.redirect as string) || pendingRedirect || '/'
  router.push(redirect)
}

async function onChangeSubmit() {
  if (!changeForm.oldPassword || !changeForm.newPassword) {
    ElMessage.warning('请填写完整密码信息')
    return
  }
  if (changeForm.newPassword.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (changeForm.newPassword !== changeForm.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  changeLoading.value = true
  try {
    await auth.changePassword(changeForm.oldPassword, changeForm.newPassword)
    ElMessage.success('密码修改成功，请重新登录')
    showChange.value = false
    auth.logout()
    form.password = ''
  } catch {
    // axios interceptor
  } finally {
    changeLoading.value = false
  }
}
</script>

<template>
  <div class="ops-login-wrap">
    <div class="ops-login-card">
      <div class="ops-login-brand">
        <div class="brand-badge">OPS</div>
        <h1>运维平台</h1>
        <p>
          Agent 主动上报 · 节点状态 / 资源指标 / 日志检索 / 受限运维指令。<br />
          平台不反连节点，指令经心跳队列下发。
        </p>
        <div class="brand-meta ops-muted">PostgreSQL · FastAPI · Vue 3</div>
      </div>

      <div class="ops-login-form">
        <div class="form-header">
          <h2>{{ showChange ? '修改密码' : '登录' }}</h2>
          <el-button circle text @click="toggleTheme">
            <el-icon>
              <Sunny v-if="isDark" />
              <Moon v-else />
            </el-icon>
          </el-button>
        </div>

        <el-alert
          v-if="showChange"
          class="mb16"
          type="warning"
          :closable="false"
          title="检测到默认密码 / 首次登录，请立即修改"
          description="新密码至少 8 位。修改成功后请使用新密码重新登录。"
          show-icon
        />

        <template v-if="!showChange">
          <el-form label-position="top" @submit.prevent="onSubmit">
            <el-form-item label="用户名">
              <el-input v-model="form.username" placeholder="admin" autocomplete="username" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input
                v-model="form.password"
                type="password"
                show-password
                placeholder="请输入密码"
                autocomplete="current-password"
                @keyup.enter="onSubmit"
              />
            </el-form-item>
            <el-button
              type="primary"
              class="submit-btn"
              :loading="loading"
              native-type="submit"
            >
              登录
            </el-button>
          </el-form>
        </template>

        <template v-else>
          <el-form label-position="top" @submit.prevent="onChangeSubmit">
            <el-form-item label="当前密码">
              <el-input v-model="changeForm.oldPassword" type="password" show-password />
            </el-form-item>
            <el-form-item label="新密码（至少 8 位）">
              <el-input v-model="changeForm.newPassword" type="password" show-password />
            </el-form-item>
            <el-form-item label="确认新密码">
              <el-input
                v-model="changeForm.confirmPassword"
                type="password"
                show-password
                @keyup.enter="onChangeSubmit"
              />
            </el-form-item>
            <el-button
              type="primary"
              class="submit-btn"
              :loading="changeLoading"
              native-type="submit"
            >
              修改并重新登录
            </el-button>
          </el-form>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.brand-badge {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(64, 158, 255, 0.2);
  color: #8ec5ff;
  font-weight: 800;
  letter-spacing: 1px;
}

.brand-meta {
  margin-top: auto;
  font-size: 12px;
}

.form-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.form-header h2 {
  margin: 0;
  font-size: 20px;
}

.submit-btn {
  width: 100%;
  margin-top: 4px;
}

.mb16 {
  margin-bottom: 16px;
}
</style>
