<template>
  <div class="login-page">
    <div class="login-card">
      <header class="login-brand">
        <div class="brand-mark" aria-hidden="true"><img src="/brand-nebula-girl.png" alt="" /></div>
        <div class="brand-copy">
          <strong>TalentMind</strong>
          <small>面向数字经济的人才能力大脑<br />与岗位演化预测系统</small>
        </div>
      </header>

      <div class="login-body">
        <h1>欢迎回来</h1>
        <p class="login-sub">请使用下方演示账号登录系统</p>

        <el-form @submit.prevent="handleLogin">
          <el-form-item>
            <el-input v-model="form.username" size="large" placeholder="账号" clearable :prefix-icon="User" autocomplete="off" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.password" size="large" type="password" placeholder="密码" show-password :prefix-icon="Lock" autocomplete="off" />
          </el-form-item>

          <div v-if="errorText" class="login-error"><el-icon><WarningFilled /></el-icon><span>{{ errorText }}</span></div>

          <el-button native-type="submit" class="btn-coral login-btn" :loading="loading">登 录</el-button>
        </el-form>

        <div class="demo-accounts">
          <p class="demo-tip">演示账号（点击自动填充）</p>
          <div class="account-chips">
            <button type="button" class="chip" @click="fill('admin', '13579')">
              <span>admin</span><small>13579 · 管理员</small>
            </button>
            <button type="button" class="chip" @click="fill('user', '24680')">
              <span>user</span><small>24680 · 演示用户</small>
            </button>
          </div>
        </div>
      </div>

      <footer class="login-foot"><i></i>数据驱动人才洞察 · 演示环境</footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Lock, User, WarningFilled } from '@element-plus/icons-vue'
import { setCurrentUser, verifyLogin } from '../utils/auth'

const route = useRoute()
const router = useRouter()

const form = reactive({ username: '', password: '' })
const errorText = ref('')
const loading = ref(false)

function fill(username: string, password: string) {
  form.username = username
  form.password = password
  errorText.value = ''
}

async function handleLogin() {
  errorText.value = ''
  if (!form.username.trim() || !form.password) {
    errorText.value = '请输入账号和密码'
    return
  }
  loading.value = true
  const user = verifyLogin(form.username, form.password)
  if (!user) {
    errorText.value = '账号或密码错误，请使用下方演示账号登录'
    loading.value = false
    return
  }
  setCurrentUser(user)
  const redirect = typeof route.query.redirect === 'string' && route.query.redirect ? route.query.redirect : '/collection'
  await router.replace(redirect)
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 28px 18px;
  background-color: var(--bg);
  background-image:
    linear-gradient(var(--bg-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--bg-grid) 1px, transparent 1px);
  background-size: 30px 30px;
  background-position: 0 0;
  background-attachment: fixed;
}
.login-card {
  width: min(430px, 100%);
  overflow: hidden;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: 0 12px 32px rgba(30, 57, 73, .08);
}
.login-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 22px 24px 18px;
  border-bottom: 1px solid var(--line);
}
.login-brand .brand-copy { display: flex; }
.login-brand .brand-copy strong { color: #142b62; }
.login-brand .brand-copy small { color: var(--muted); white-space: normal; }
.login-body { padding: 24px; }
.login-body h1 { margin: 0 0 5px; font-size: 21px; font-weight: 650; }
.login-sub { margin: 0 0 20px; color: var(--muted); font-size: 11px; }
.login-error {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: -3px 0 11px;
  color: var(--danger);
  font-size: 11px;
}
.login-error .el-icon { flex: 0 0 auto; }
.login-btn {
  width: 100%;
  height: 40px;
  margin: 2px 0 0;
  font-size: 14px;
  letter-spacing: 4px;
}
.demo-accounts {
  margin-top: 20px;
  padding: 13px 14px;
  background: var(--card-soft);
  border: 1px solid var(--line);
  border-radius: 6px;
}
.demo-tip { margin: 0; color: var(--muted); font-size: 10px; }
.chip { margin-top: 10px; border: 0; background: transparent; }
.chip span { color: var(--text); font-size: 12px; font-weight: 600; }
.chip small { margin-left: 8px; color: var(--muted); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; }
.login-foot {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 12px;
  color: var(--muted);
  font-size: 10px;
  letter-spacing: 0;
  border-top: 1px solid var(--line);
}
.login-foot i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--green);
}
@media (max-width: 520px) {
  .login-card { border-radius: 0; }
  .login-page { padding: 0; place-items: stretch; }
}
</style>