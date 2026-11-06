import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parse, compileScript } from 'vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'

function deferred() {
  let resolve!: (value: any) => void, reject!: (error: Error) => void
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const overview = (n: number) => ({ totalJobs: n, totalResumes: 2, matchSuccess: 0, skillGaps: 0, coralBlocks: [] })
const timeline = (id: string) => ({ job_id: id, job_title: id, records: [{ id, reason: id }], total_changes: 1, current_version: 1 })
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); await vue.nextTick() }

function component(name: string, overrides: Record<string, any> = {}) {
  const mounted: Function[] = [], unmounted: Function[] = [], calls: any[] = [], charts: any[] = [], timers = new Map()
  const defaults: Record<string, any> = { getDashboardOverview: overview(3), getDashboardTrend: { months: [], series: [] }, getSkillDistribution: [], getJobList: { list: [{ id: 'A', title: '岗位A' }, { id: 'B', title: '岗位B' }], total: 2 } }
  const api = new Proxy({}, { get: (_, method: string) => async (...args: any[]) => {
    calls.push({ method, args }); const value = method in overrides ? overrides[method] : defaults[method]
    if (value instanceof Error) throw value
    return typeof value === 'function' ? value(...args) : value
  } })
  const compiled = compileScript(parse(readFileSync(resolve(import.meta.dirname, `../src/views/${name}.vue`), 'utf8')).descriptor, { id: name }).content
  const code = ts.transpileModule(compiled, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const module = { exports: {} as any }
  const require = (id: string) => {
    if (id === 'vue') return { ...vue, onMounted: (fn: Function) => mounted.push(fn), onUnmounted: (fn: Function) => unmounted.push(fn) }
    if (id.startsWith('../api/')) return api
    if (id === '@element-plus/icons-vue') return {}
    if (id === 'echarts') return { graphic: { LinearGradient: class {} }, init: () => { const chart = { disposed: false, updates: 0, setOption() { assert.equal(this.disposed, false); this.updates++ }, resize() { assert.equal(this.disposed, false) }, dispose() { this.disposed = true } }; charts.push(chart); return chart } }
    throw new Error('Unexpected module ' + id)
  }
  new Function('require', 'module', 'exports', 'window', 'setInterval', 'clearInterval', code)(require, module, module.exports, { addEventListener() {}, removeEventListener() {} }, (fn: Function) => { const id = timers.size + 1; timers.set(id, fn); return id }, (id: number) => timers.delete(id))
  const scope = vue.effectScope()
  const state = scope.run(() => module.exports.default.setup({}, { expose() {} }))
  return { state, calls, charts, timers, mount: async () => { for (const fn of mounted) await fn() }, stop: () => { for (const fn of unmounted) fn(); scope.stop() } }
}

test('能力动态只接纳当前岗位的请求，刷新再次读取当前时间线', async () => {
  const a = deferred(), b = deferred()
  const page = component('JobEvolution', { getJobEvolutionTimeline: (id: string) => id === 'A' ? a.promise : b.promise })
  try {
    const first = page.state.selectJob('A'), second = page.state.selectJob('B')
    b.resolve(timeline('B')); await second; a.resolve(timeline('A')); await first
    assert.equal(page.state.timeline.value.job_id, 'B')
    await page.state.loadData()
    assert.equal(page.calls.filter(c => c.method === 'getJobEvolutionTimeline' && c.args[0] === 'B').length, 2)
  } finally { page.stop() }
})

test('能力动态区分失败与成功空记录并可重试，卸载后不回写', async () => {
  let fail = true
  const page = component('JobEvolution', { getJobEvolutionTimeline: () => { if (fail) throw new Error('offline'); return { ...timeline('A'), records: [], total_changes: 0 } } })
  try {
    await page.state.selectJob('A')
    assert.ok(page.state.timelineError.value)
    assert.equal(page.state.timeline.value, null)
    fail = false; await page.state.selectJob('A')
    assert.equal(page.state.timelineError.value, '')
    assert.deepEqual(page.state.timeline.value.records, [])
  } finally { page.stop() }
  const pending = deferred(), late = component('JobEvolution', { getJobEvolutionTimeline: pending.promise })
  const load = late.state.selectJob('A'); late.stop(); pending.resolve(timeline('A')); await load
  assert.equal(late.state.timeline.value, null)
})

for (const name of ['Dashboard', 'Analytics']) {
  const load = (state: any) => name === 'Dashboard' ? state.loadDashboardData() : state.loadData()
  const total = (state: any) => name === 'Dashboard' ? state.statCards[0].value : state.overview.value.totalJobs
  test(`${name} 各面板独立更新，失败保留旧数据并标错，重试恢复`, async () => {
    let fail = false, n = 5
    const pending = deferred()
    const page = component(name, { getDashboardOverview: () => overview(n), getDashboardTrend: () => fail ? Promise.reject(new Error('offline')) : { months: ['2026-11'], series: [{ name: 'signal', data: [1] }] }, getSkillDistribution: pending.promise })
    try {
      const first = load(page.state); await flush()
      assert.equal(total(page.state), 5)
      pending.resolve([]); await first
      fail = true; n = 9; await load(page.state)
      assert.equal(total(page.state), 9)
      assert.ok(page.state.panelState.trend.error)
      assert.equal(page.state.panelState.trend.loaded, true)
      assert.equal((name === 'Dashboard' ? page.state.months.value : page.state.trend.value.months)[0], '2026-11')
      fail = false; await load(page.state)
      assert.equal(page.state.panelState.trend.error, '')
    } finally { page.stop() }
  })
  test(`${name} 迟到响应和卸载不能覆盖数据或操作已销毁图表`, async () => {
    const old = deferred(); let request = 0
    const page = component(name, { getDashboardOverview: () => ++request === 1 ? old.promise : overview(8) })
    try {
      const first = load(page.state); await load(page.state); old.resolve(overview(1)); await first
      assert.equal(total(page.state), 8)
    } finally { page.stop() }
    const pending = deferred(), late = component(name, { getDashboardOverview: pending.promise })
    const before = total(late.state), loading = load(late.state)
    late.stop(); pending.resolve(overview(99)); await loading
    assert.equal(total(late.state), before)
    assert.equal(late.timers.size, 0)
    assert.equal(late.charts.length, 0)
  })
  test(`${name} 首屏失败不冒充零数据，重试成功空结果后才显示空态`, async () => {
    let fail = true
    const page = component(name, {
      getDashboardOverview: () => fail ? Promise.reject(new Error('offline')) : overview(0),
      getDashboardTrend: () => fail ? Promise.reject(new Error('offline')) : { months: [], series: [] },
      getSkillDistribution: () => fail ? Promise.reject(new Error('offline')) : [],
      getJobList: () => fail ? Promise.reject(new Error('offline')) : { list: [], total: 0 },
    })
    try {
      const pending = load(page.state)
      assert.equal(page.state.panelState.trend.loading, true)
      await pending
      for (const state of Object.values(page.state.panelState) as any[]) {
        assert.equal(state.loaded, false); assert.equal(state.loading, false); assert.ok(state.error)
      }
      fail = false; await load(page.state)
      for (const state of Object.values(page.state.panelState) as any[]) {
        assert.equal(state.loaded, true); assert.equal(state.loading, false); assert.equal(state.error, '')
      }
      assert.equal(total(page.state), 0)
    } finally { page.stop() }
  })
  test(`${name} 已创建图表在卸载后不被迟到请求重建或更新`, async () => {
    let pending: ReturnType<typeof deferred> | undefined
    const page = component(name, { getDashboardTrend: () => pending ? pending.promise : { months: ['2026-11'], series: [{ name: 'signal', data: [1] }] }, getSkillDistribution: [{ name: 'SQL', count: 1, percentage: 50 }] })
    if (name === 'Dashboard') {
      page.state.lineChartRef.value = {}; page.state.barChartRef.value = {}; page.state.initCharts()
    } else {
      page.state.trendRef.value = {}; page.state.skillsRef.value = {}
    }
    await load(page.state)
    assert.equal(page.charts.length, 2)
    pending = deferred()
    const late = load(page.state)
    page.stop()
    const updates = page.charts.map(chart => chart.updates)
    pending.resolve({ months: ['2026-12'], series: [{ name: 'late', data: [3] }] }); await late
    assert.deepEqual(page.charts.map(chart => chart.updates), updates)
    assert.equal(page.charts.length, 2)
    assert.ok(page.charts.every(chart => chart.disposed))
    assert.equal(page.timers.size, 0)
  })
}
