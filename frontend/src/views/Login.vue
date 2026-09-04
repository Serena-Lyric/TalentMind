<template>
  <div class="login-page">
    <div class="orb orb-a"></div>
    <div class="orb orb-b"></div>
    <div class="login-card">
      <header class="login-brand">
        <div class="brand-mark" aria-hidden="true"><img src="/guangzhou-school.jpg" alt="" /></div>
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
  position: relative;
  display: flex;
  min-height: 100vh;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  overflow: hidden;
  background: linear-gradient(160deg, #fdfbf8 0%, var(--bg) 55%, #f3ece6 100%);
}
.orb { position: absolute; border-radius: 50%; pointer-events: none; }
.orb-a { width: 320px; height: 320px; top: -110px; left: -90px; background: radial-gradient(circle, rgba(223, 141, 112, .18) 0%, rgba(223, 141, 112, 0) 70%); }
.orb-b { width: 380px; height: 380px; right: -130px; bottom: -140px; background: radial-gradient(circle, rgba(131, 188, 154, .20) 0%, rgba(131, 188, 154, 0) 70%); }
.login-card {
  position: relative;
  z-index: 1;
  width: min(430px, 100%);
  overflow: hidden;
  background: var(--card);
  border: 1px solid rgba(241, 235, 228, .9);
  border-radius: 22px;
  box-shadow: 0 18px 50px rgba(82, 63, 46, .10);
}
.login-brand { display: flex; align-items: center; gap: 12px; padding: 24px 26px 20px; border-bottom: 1px solid #f5f0ea; }
.login-brand .brand-copy { display: flex; }
.login-brand .brand-copy small { white-space: normal; }
.login-body { padding: 26px 26px 22px; }
.login-body h1 { margin: 0 0 4px; font-size: 21px; font-weight: 700; }
.login-sub { margin: 0 0 20px; color: #a39d99; font-size: 12px; }
.login-error { display: flex; align-items: center; gap: 6px; margin: -4px 0 12px; color: #d9534f; font-size: 12px; }
.login-error .el-icon { flex: 0 0 auto; }
.login-btn { width: 100%; height: 42px; margin: 2px 0 0; font-size: 15px; letter-spacing: 6px; }
.demo-accounts { margin-top: 22px; padding: 14px; background: var(--card-soft); border: 1px dashed var(--line-strong); border-radius: 14px; }
.demo-tip { margin: 0; color: #9f9995; font-size: 11px; }
.account-chips { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
.chip { display: flex; flex-direction: column; gap: 3px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 12px; background: #fff; color: var(--text); text-align: left; transition: border-color .16s, background .16s; }
.chip:hover { border-color: #e4b5a4; background: #fff7f2; }
.chip span { font-size: 13px; font-weight: 600; }
.chip small { color: #a39d99; font-size: 11px; }
.login-foot { display: flex; align-items: center; justify-content: center; gap: 7px; padding: 14px; color: #b8b2ae; font-size: 11px; letter-spacing: .6px; border-top: 1px solid #f5f0ea; }
.login-foot i { width: 6px; height: 6px; border-radius: 50%; background: var(--green); box-shadow: 0 0 0 4px var(--green-soft); }
</style>
