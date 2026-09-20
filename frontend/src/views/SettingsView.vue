<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { healthApi } from '@/api/auth'
import { isProjectDeployEnabled } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

const auth = useAuthStore()
const { isDark, toggleTheme } = useThemeStore()
const health = ref<{ ok: boolean; project_deploy_enabled: boolean } | null>(null)
const deployEnabled = isProjectDeployEnabled()

const pwd = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})
const saving = ref(false)

async function loadHealth() {
  try {
    const { data } = await healthApi()
    health.value = data
  } catch {
    health.value = null
  }
}

async function savePassword() {
  if (!pwd.value.oldPassword || !pwd.value.newPassword) {
    ElMessage.warning('请填写完整')
    return
  }
  if (pwd.value.newPassword.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (pwd.value.newPassword !== pwd.value.confirmPassword) {
    ElMessage.warning('两次密码不一致')
    return
  }
  saving.value = true
  try {
    await auth.changePassword(pwd.value.oldPassword, pwd.value.newPassword)
    ElMessage.success('密码已更新')
    pwd.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
  } catch {
    // interceptor
  } finally {
    saving.value = false
  }
}

onMounted(loadHealth)
</script>

<template>
  <div class="ops-page">
    <div class="ops-card">
      <h3 class="card-title">系统设置</h3>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="当前用户">{{ auth.username.value || '—' }}</el-descriptions-item>
        <el-descriptions-item label="主题">
          <div class="row">
            <span>{{ isDark ? '深色' : '浅色' }}</span>
            <el-button size="small" @click="toggleTheme">切换主题</el-button>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="project_deploy 按钮">
          <el-tag :type="deployEnabled ? 'danger' : 'info'">
            {{ deployEnabled ? '已启用（VITE）' : '默认关闭（VITE_PROJECT_DEPLOY_ENABLED=false）' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="后端 health">
          <template v-if="health">
            ok={{ health.ok }} · project_deploy_enabled={{ health.project_deploy_enabled }}
          </template>
          <template v-else>不可用</template>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="ops-card">
      <h3 class="card-title">修改密码</h3>
      <el-form label-width="120px" class="pwd-form" @submit.prevent="savePassword">
        <el-form-item label="当前密码">
          <el-input v-model="pwd.oldPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwd.newPassword" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="pwd.confirmPassword" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="savePassword">保存</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.card-title {
  margin: 0 0 14px;
  font-size: 15px;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pwd-form {
  max-width: 480px;
}
</style>
