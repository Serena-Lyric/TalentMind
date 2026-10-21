import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parse, compileScript } from 'vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'

// 执行真实采集页 setup，外部 API 与计时器隔离；不连接浏览器或数据库。
export function collectionComponent(overrides: Record<string, any> = {}, options: { batch?: boolean; props?: Record<string, any> } = {}) {
  const filename = resolve(import.meta.dirname, options.batch ? '../../src/components/CollectionBatch.vue' : '../../src/views/Collection.vue')
  const mounted: (() => any)[] = []
  const unmounted: (() => any)[] = []
  const intervals: (() => any)[] = []
  const cleared: any[] = []
  const events: { name: string; value: any }[] = []
  const calls: { method: string; args: any[] }[] = []
  const messages: string[] = []
  const defaults: Record<string, any> = {
    getCollectionPlatforms: [{ platform: 'boss', label: 'BOSS', supported: true, cities: [{ name: '北京', code: '101010100' }] }, { platform: 'zhaopin', label: '智联', supported: true, cities: [{ name: '北京', code: '530' }] }, { platform: 'hn', label: 'HN', supported: false, cities: [] }],
    getCollectionStatus: { run_id: null, status: 'idle' },
    getCollectionConfig: { platform: 'boss', keywords: ['Python'], cities: [{ name: '北京', code: '101010100' }], pages: 1, detail_limit: 5, max_jobs: 5 },
    getDatabaseStats: { available: true, database_total: 17, platform_counts: [] },
    getCollectionStats: { available: true, database_total: 17, platform_counts: [] },
    getCDPStatus: { reachable: false, platform_access: {} },
    getCollectionHistory: { items: [], total: 0 },
    getCollectionResults: [],
    getCollectionRecent: [],
    getCollectionBatches: { items: [], total: 0 },
    prepareCollection: { access_state: 'public_accessible', can_collect: true, message: '公开可访问', cdp: { reachable: true } },
    startCollection: { run_id: 'new-run', status: 'preparing' },
    getCollectionRaw: { jd_pool_id: 7, raw_text: '完整正文\n第二行' },
  }
  const api = new Proxy({}, {
    get: (_, method: string) => async (...args: any[]) => {
      calls.push({ method, args })
      const value = method in overrides ? overrides[method] : defaults[method]
      if (value instanceof Error) throw value
      return typeof value === 'function' ? value(...args) : value
    },
  })
  const input = compileScript(parse(readFileSync(filename, 'utf8')).descriptor, { id: 'collection-test' }).content
  const code = ts.transpileModule(input, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const module = { exports: {} as any }
  const require = (id: string): any => {
    if (id === 'vue') return { ...vue, onMounted: (callback: () => any) => mounted.push(callback), onUnmounted: (callback: () => any) => unmounted.push(callback) }
    if (id.endsWith('CollectionBatch.vue')) return {}
    if (id === '../api/collection') return api
    if (id === '@element-plus/icons-vue') return {}
    if (id === 'element-plus') return { ElMessage: Object.fromEntries(['info', 'success', 'warning', 'error'].map(key => [key, (message: string) => messages.push(message)])), ElMessageBox: { confirm: async () => {} } }
    throw new Error(`Unexpected dependency: ${id}`)
  }
  new Function('require', 'module', 'exports', 'setInterval', 'clearInterval', code)(require, module, module.exports, (callback: () => any) => intervals.push(callback), (id: any) => cleared.push(id))
  const scope = vue.effectScope()
  const props = vue.reactive(options.props || {})
  const state = scope.run(() => module.exports.default.setup(props, { expose() {}, emit: (name: string, value: any) => events.push({ name, value }) }))
  return { state, calls, messages, props, intervals, cleared, events, mounted: async () => { for (const callback of mounted) await callback() }, stop: () => { for (const callback of unmounted) callback(); scope.stop() } }
}
