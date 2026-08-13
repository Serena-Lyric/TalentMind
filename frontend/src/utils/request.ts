/**
 * 统一 axios 请求封装
 * 
 * 功能：
 * 1. 配置基础请求地址（通过环境变量或默认值）
 * 2. 请求拦截器：自动附加 token、通用 headers
 * 3. 响应拦截器：统一错误处理、数据提取
 * 4. 统一错误提示（Element Plus ElMessage）
 * 5. 支持 mock 模式切换
 */

import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

// ============================================================
// 配置区：切换真实后端接口时，只需修改 BASE_URL
// ============================================================

/** 后端 API 基础地址 —— 对接真实后端时改为实际地址 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

/** 是否使用 mock 数据（本地调试时设为 true，对接后端时设为 false） */
export const USE_MOCK = true

// ============================================================
// 创建 axios 实例
// ============================================================

const service: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json;charset=UTF-8'
  }
})

// ============================================================
// 请求拦截器
// ============================================================

service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 自动附加 token（对接真实后端时取消注释）
    // const token = localStorage.getItem('token')
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error) => {
    ElMessage.error('请求发送失败，请检查网络')
    return Promise.reject(error)
  }
)

// ============================================================
// 响应拦截器
// ============================================================

service.interceptors.response.use(
  (response: AxiosResponse) => {
    const { data, status } = response

    // 后端约定的统一响应格式：{ code, data, message }（D29：code=0 成功）
    if (data.code !== 0) {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message))
    }

    if (status >= 200 && status < 300) {
      return data
    }

    ElMessage.error('请求异常，状态码：' + status)
    return Promise.reject(new Error('请求异常'))
  },
  (error) => {
    const status = error.response?.status
    const msgMap: Record<number, string> = {
      400: '请求参数错误',
      401: '未授权，请重新登录',
      403: '没有访问权限',
      404: '请求的资源不存在',
      500: '服务器内部错误',
      502: '网关错误',
      503: '服务不可用'
    }
    ElMessage.error(msgMap[status as number] || `请求失败：${error.message}`)
    return Promise.reject(error)
  }
)

// ============================================================
// 导出请求方法
// ============================================================

export function get<T = any>(url: string, params?: any, config?: AxiosRequestConfig): Promise<T> {
  return service.get(url, { params, ...config })
}

export function post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
  return service.post(url, data, config)
}

export function put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
  return service.put(url, data, config)
}

export function del<T = any>(url: string, params?: any): Promise<T> {
  return service.delete(url, { params })
}

export default service