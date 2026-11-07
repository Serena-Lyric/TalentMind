import { getActivePinia } from 'pinia'
import { useResumeStore } from '../store/resume'

function clearSessionData() { if (getActivePinia()) useResumeStore().clear() }

// 登录演示工具：仅前端校验，不接入后端鉴权（用于功能演示）
export interface DemoUser { username: string; label: string }

const ACCOUNTS: Record<string, { password: string; label: string }> = {
  admin: { password: '13579', label: '管理员' },
  user: { password: '24680', label: '演示用户' },
}

const STORAGE_KEY = 'tm_demo_user'

export function verifyLogin(username: string, password: string): DemoUser | null {
  const name = username.trim().toLowerCase()
  const account = ACCOUNTS[name]
  if (!account || account.password !== password) return null
  return { username: name, label: account.label }
}

export function getCurrentUser(): DemoUser | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw) as DemoUser
    return data && data.username ? data : null
  } catch {
    return null
  }
}

export function setCurrentUser(user: DemoUser): void {
  clearSessionData()
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(user))
}

export function clearCurrentUser(): void {
  clearSessionData()
  sessionStorage.removeItem(STORAGE_KEY)
}
