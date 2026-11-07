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
  const mounted: Function[] = [], unmounted: Function[] = [], calls: any[] = [], charts: any[] = [], timers = new Map(), searchTimers = new Map()
  let timerId = 0
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
    if (id === '../composables/usePagedJobs') {
      const source = readFileSync(resolve(import.meta.dirname, '../src/composables/usePagedJobs.ts'), 'utf8')
      const helper = { exports: {} as any }
      new Function('require', 'module', 'exports', 'setTimeout', 'clearTimeout', ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText)(require, helper, helper.exports,
        (fn: Function) => { const id = ++timerId; searchTimers.set(id, fn); return id }, (id: number) => searchTimers.delete(id))
      return helper.exports
    }
    if (id === '@element-plus/icons-vue') return {}
    if (id === 'echarts') return { graphic: { LinearGradient: class {} }, init: () => { const chart = { disposed: false, updates: 0, setOption() { assert.equal(this.disposed, false); this.updates++ }, resize() { assert.equal(this.disposed, false) }, dispose() { this.disposed = true } }; charts.push(chart); return chart } }
    throw new Error('Unexpected module ' + id)
  }
  new Function('require', 'module', 'exports', 'window', 'setInterval', 'clearInterval', code)(require, module, module.exports, { addEventListener() {}, removeEventListener() {} }, (fn: Function) => { const id = timers.size + 1; timers.set(id, fn); return id }, (id: number) => timers.delete(id))
  const scope = vue.effectScope()
  const state = scope.run(() => module.exports.default.setup({}, { expose() {} }))
  return { state, calls, charts, timers, searchTimers, async search() { const pending = [...searchTimers.values()]; searchTimers.clear(); pending.forEach(fn => fn()); await flush() }, mount: async () => { for (const fn of mounted) await fn() }, stop: () => { for (const fn of unmounted) fn(); scope.stop() } }
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


for (const name of ['Dashboard', 'JobEvolution']) {
  const getBrowser = (page: any) => name === 'Dashboard' ? page.state.jobBrowser : {
    jobs: page.state.jobs, total: page.state.total, page: page.state.page, keyword: page.state.keyword,
    loaded: page.state.jobsLoaded, loading: page.state.loading, error: page.state.jobsError,
    load: page.state.loadJobs, changePage: page.state.changePage, search: page.state.search,
  }
  const pageSize = name === 'Dashboard' ? 8 : 20
  const fixture = (id: string) => ({ id, title: `岗位${id}` })
  test(`${name} 使用后端总数与分页，可以浏览第100项之后的岗位`, async () => {
    const page = component(name, { getJobList: (query: any) => ({ list: [fixture(String((query.page - 1) * query.page_size + 1))], total: 241 }), getJobEvolutionTimeline: (id: string) => timeline(id) })
    try {
      await page.mount(); await flush()
      const browser = getBrowser(page)
      assert.deepEqual(page.calls.find(c => c.method === 'getJobList').args[0], { keyword: '', page: 1, page_size: pageSize })
      assert.equal(browser.total.value, 241)
      await browser.changePage(13); await flush()
      assert.equal(browser.jobs.value[0].id, String(12 * pageSize + 1))
      assert.equal(browser.page.value, 13)
      await browser.changePage(13)
      assert.equal(page.calls.filter(c => c.method === 'getJobList').length, 2)
    } finally { page.stop() }
  })
  test(`${name} 搜索先回第一页，防抖期间旧响应不能覆盖新查询`, async () => {
    const pending = deferred(); let reads = 0
    const page = component(name, { getJobList: (query: any) => ++reads === 1 ? pending.promise : { list: [fixture(query.keyword)], total: 1 }, getJobEvolutionTimeline: (id: string) => timeline(id) })
    try {
      const browser = getBrowser(page), old = browser.load()
      browser.page.value = 5
      browser.keyword.value = '数据'; browser.keyword.value = '数据工程师'
      pending.resolve({ list: [fixture('旧数据')], total: 50 }); await old
      assert.deepEqual(browser.jobs.value, [])
      assert.equal(browser.page.value, 1)
      assert.equal(browser.loading.value, true)
      await page.search()
      assert.equal(browser.jobs.value[0].id, '数据工程师')
      assert.equal(browser.total.value, 1)
      assert.equal(reads, 2)
      assert.deepEqual(page.calls.filter(c => c.method === 'getJobList').at(-1).args[0], { keyword: '数据工程师', page: 1, page_size: pageSize })
    } finally { page.stop() }
  })
  test(`${name} 搜索回车取消待发防抖，清空搜索重新查询第一页`, async () => {
    const page = component(name, { getJobList: () => ({ list: [], total: 0 }) })
    try {
      const browser = getBrowser(page)
      browser.keyword.value = '  Python  '; await browser.search(); await page.search()
      assert.equal(page.calls.filter(c => c.method === 'getJobList').length, 1)
      assert.equal(page.calls[0].args[0].keyword, 'Python')
      browser.page.value = 3; browser.keyword.value = ''; await page.search()
      assert.deepEqual(page.calls.filter(c => c.method === 'getJobList').at(-1).args[0], { keyword: '', page: 1, page_size: pageSize })
    } finally { page.stop() }
  })
  test(`${name} 查询改变后失败不借用旧页结果，重试恢复`, async () => {
    let fail = false
    const page = component(name, { getJobList: () => { if (fail) throw new Error('offline'); return { list: [fixture('A')], total: 241 } }, getJobEvolutionTimeline: (id: string) => timeline(id) })
    try {
      const browser = getBrowser(page); await browser.load(); await flush()
      fail = true; await browser.load()
      assert.equal(browser.loaded.value, true); assert.equal(browser.jobs.value[0].id, 'A')
      assert.match(browser.error.value, /保留上次/)
      await browser.changePage(2)
      assert.equal(browser.loaded.value, false); assert.deepEqual(browser.jobs.value, [])
      assert.ok(browser.error.value)
      fail = false; await browser.load()
      assert.equal(browser.loaded.value, true); assert.equal(browser.error.value, '')
    } finally { page.stop() }
  })
  test(`${name} 总页数收缩后有界回查最后一页`, async () => {
    const page = component(name, { getJobList: (query: any) => ({ list: query.page > 2 ? [] : [fixture('末页')], total: pageSize + 1 }), getJobEvolutionTimeline: (id: string) => timeline(id) })
    try {
      const browser = getBrowser(page); await browser.changePage(5)
      assert.deepEqual(page.calls.filter(c => c.method === 'getJobList').map(c => c.args[0].page), [5, 2])
      assert.equal(browser.page.value, 2); assert.equal(browser.jobs.value[0].id, '末页')
    } finally { page.stop() }
  })
  test(`${name} 回查期间页数再次缩小则报错，不循环请求或发布无效页`, async () => {
    let reads = 0
    const page = component(name, { getJobList: () => ({ list: [], total: ++reads === 1 ? pageSize + 1 : 0 }) })
    try {
      const browser = getBrowser(page); await browser.changePage(5)
      assert.equal(reads, 2); assert.equal(browser.loaded.value, false)
      assert.ok(browser.error.value); assert.equal(browser.loading.value, false)
      await browser.search(); assert.equal(browser.loaded.value, true)
      assert.equal(browser.page.value, 1); assert.equal(browser.total.value, 0)
    } finally { page.stop() }
  })
  test(`${name} 翻页倒序响应与卸载后的搜索均失效`, async () => {
    const first = deferred(), second = deferred()
    const page = component(name, { getJobList: (q: any) => q.page === 2 ? first.promise : second.promise, getJobEvolutionTimeline: (id: string) => timeline(id) })
    try {
      const browser = getBrowser(page), a = browser.changePage(2), b = browser.changePage(3)
      second.resolve({ list: [fixture('第3页')], total: 241 }); await b
      first.reject(new Error('old')); await a
      assert.equal(browser.jobs.value[0].id, '第3页'); assert.equal(browser.error.value, '')
      browser.keyword.value = '待发搜索'; const before = page.calls.length
      page.stop(); await page.search()
      assert.equal(page.calls.length, before); assert.equal(page.searchTimers.size, 0)
    } finally { page.stop() }
  })
}

test('翻页加载期间保留分页边界，不触发分页器回到第一页', async () => {
  const secondPage = deferred()
  const page = component('Dashboard', {
    getJobList: (query: any) => query.page === 2 ? secondPage.promise : { list: [{ id: 'A', title: '岗位A' }], total: 241 },
  })
  const browser = page.state.jobBrowser
  let stopPagination: (() => void) | undefined
  try {
    await browser.load()
    // 未挂载真实 Element Plus。用真实 Vue watch 复现其 2.9.4 pagination.ts
    // pageCountBridge 收缩时，经 currentPageBridge setter 发出 current-change 的行为。
    stopPagination = vue.watch(() => Math.max(1, Math.ceil(browser.total.value / 8)), count => {
      if (browser.page.value > count) void browser.changePage(count)
    })
    const pending = browser.changePage(2)
    await flush()
    assert.equal(browser.page.value, 2)
    assert.deepEqual(page.calls.filter(c => c.method === 'getJobList').map(c => c.args[0].page), [1, 2])
    secondPage.resolve({ list: [{ id: 'B', title: '岗位B' }], total: 241 })
    await pending; await flush()
    assert.equal(browser.page.value, 2)
    assert.equal(browser.jobs.value[0].id, 'B')
    await browser.changePage(2)
    assert.equal(page.calls.filter(c => c.method === 'getJobList').length, 2)
  } finally {
    stopPagination?.()
    page.stop()
    secondPage.resolve({ list: [], total: 0 })
  }
})

test('能力动态翻页时标题与旧时间线保持同一岗位，新页返回后选择新岗位，空结果清空时间线', async () => {
  const nextPage = deferred(), nextTimeline = deferred(); let empty = false
  const page = component('JobEvolution', {
    getJobList: (q: any) => empty ? { list: [], total: 0 } : q.page === 1 ? { list: [{ id: 'A', title: '岗位A' }], total: 21 } : nextPage.promise,
    getJobEvolutionTimeline: (id: string) => id === 'A' ? timeline('A') : nextTimeline.promise,
  })
  try {
    await page.mount(); await flush()
    assert.equal(page.state.selectedJob.value.title, '岗位A')
    const pending = page.state.changePage(2); await flush()
    assert.equal(page.state.selectedJob.value.title, '岗位A'); assert.equal(page.state.timeline.value.job_id, 'A')
    nextPage.resolve({ list: [{ id: 'B', title: '岗位B' }], total: 21 }); await pending; await flush()
    assert.equal(page.state.selectedJob.value.title, '岗位B'); assert.equal(page.state.timeline.value, null)
    empty = true; await page.state.search(); await flush()
    nextTimeline.resolve(timeline('B')); await flush()
    assert.equal(page.state.selectedJob.value, undefined); assert.equal(page.state.timeline.value, null)
    assert.equal(page.state.timelineLoading.value, false)
  } finally { page.stop() }
})
