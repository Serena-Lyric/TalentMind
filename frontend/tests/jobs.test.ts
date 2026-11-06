import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'

// 执行真实页面 setup，仅隔离网络与防抖计时，不连接后端或数据库。
function component(overrides: Record<string, any> = {}) {
  const calls: { method: string; args: any[] }[] = []
  const messages: string[] = []
  const mounted: Function[] = [], unmounted: Function[] = []
  const timers = new Map<number, Function>()
  let timerId = 0
  const defaults: Record<string, any> = { getJobList: { list: [], total: 0 }, getJobPlatformStats: [], getJobDetail: job('A'), updateJob: { success: true } }
  const api = new Proxy({}, { get: (_, method: string) => async (...args: any[]) => {
    calls.push({ method, args })
    const value = method in overrides ? overrides[method] : defaults[method]
    if (value instanceof Error) throw value
    return typeof value === 'function' ? value(...args) : value
  } })
  const source = readFileSync(resolve(import.meta.dirname, '../src/views/Jobs.vue'), 'utf8')
  const descriptor = parse(source).descriptor
  const compiled = compileScript(descriptor, { id: 'jobs-test' }).content
  const code = ts.transpileModule(compiled, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const module = { exports: {} as any }
  const require = (id: string) => {
    if (id === 'vue') return { ...vue, onMounted: (fn: Function) => mounted.push(fn), onUnmounted: (fn: Function) => unmounted.push(fn), resolveComponent: (name: string) => ({ name }), resolveDirective: () => ({}), withDirectives: (node: any) => node }
    if (id === '../api/jobs') return api
    if (id === '@element-plus/icons-vue') return {}
    if (id === 'element-plus') return { ElMessage: Object.fromEntries(['success', 'error', 'warning'].map(key => [key, (s: string) => messages.push(s)])) }
    throw new Error(`Unexpected dependency: ${id}`)
  }
  new Function('require', 'module', 'exports', 'setTimeout', 'clearTimeout', code)(require, module, module.exports,
    (fn: Function) => { timers.set(++timerId, fn); return timerId }, (id: number) => timers.delete(id))
  const scope = vue.effectScope()
  const state = scope.run(() => module.exports.default.setup({}, { expose() {} }))
  const template = compileTemplate({ source: descriptor.template!.content, filename: 'Jobs.vue', id: 'jobs-test', transformAssetUrls: false }).code
  const renderModule = { exports: {} as any }
  new Function('require', 'module', 'exports', ts.transpileModule(template, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText)(require, renderModule, renderModule.exports)
  const elements = (type: string) => {
    const found: any[] = []
    const visit = (node: any) => {
      if (!node || typeof node !== 'object') return
      if (Array.isArray(node)) { node.forEach(visit); return }
      if ((node.type?.name || node.type) === type) found.push(node)
      if (node.type?.name === 'el-table') return // 表格行插槽由真实表格提供 row，与筛选事件无关。
      visit(typeof node.children?.default === 'function' ? node.children.default() : node.children)
    }
    visit(renderModule.exports.render(vue.proxyRefs(state), []))
    return found
  }
  return { state, calls, messages, mounted: () => Promise.all(mounted.map(fn => fn())),
    elements,
    async timers() { await vue.nextTick(); const pending = [...timers.values()]; timers.clear(); pending.forEach(fn => fn()); await tick() },
    stop() { unmounted.forEach(fn => fn()); scope.stop() } }
}

function job(id: string, skills = ['Python']) {
  return { id, title: `岗位${id}`, job_name: `岗位${id}`, company: '', city: '', type: 'boss', salary: '', status: '', updated: '', skills, required_skills: skills, bonus_skills: [], core_duties: '合成职责' }
}
function deferred() {
  let resolve!: (value: any) => void, reject!: (reason: any) => void
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const tick = async () => { await vue.nextTick(); for (let i = 0; i < 6; i++) await Promise.resolve() }
function addSkill(state: any, name: string) { state.startAddSkill(); state.newSkill.value = name; state.confirmAddSkill() }

test('详情倒序返回只更新当前岗位，关闭后重开同岗位使用新会话', async () => {
  const pending = [deferred(), deferred(), deferred(), deferred()]
  let index = 0
  const view = component({ getJobDetail: () => pending[index++].promise })
  try {
    const a = view.state.openDetail(job('A'))
    const b = view.state.openDetail(job('B'))
    pending[1].resolve(job('B', ['SQL'])); await b
    pending[0].resolve(job('A')); await a
    assert.equal(view.state.detailJob.value.id, 'B')
    assert.deepEqual(view.state.detailSkills.value, ['SQL'])
    const old = view.state.openDetail(job('A'))
    view.state.detailVisible.value = false; await tick()
    const reopened = view.state.openDetail(job('A'))
    pending[3].resolve(job('A', ['新会话技能'])); await reopened
    pending[2].resolve(job('A', ['迟到技能'])); await old
    assert.deepEqual(view.state.detailSkills.value, ['新会话技能'])
  } finally { view.stop() }
})

test('详情未返回时可编辑且返回不覆盖草稿，保存等待完整详情', async () => {
  const pending = deferred()
  const view = component({ getJobDetail: () => pending.promise })
  try {
    const opening = view.state.openDetail(job('A'))
    addSkill(view.state, 'SQL')
    const prematureSave = view.state.saveSkills(); await tick()
    assert.equal(view.calls.filter(c => c.method === 'updateJob').length, 0)
    pending.resolve({ ...job('A'), bonus_skills: ['Python'], required_skills: [] }); await opening
    await prematureSave
    assert.deepEqual(view.state.detailSkills.value, ['Python', 'SQL'])
    assert.equal(view.state.skillDirty.value, true)
    await view.state.saveSkills()
    const payload = view.calls.find(c => c.method === 'updateJob')!.args[1]
    assert.deepEqual(payload.required_skills, ['SQL'])
    assert.deepEqual(payload.bonus_skills, ['Python'])
  } finally { view.stop() }
})

test('保存A期间切换编辑B，A迟到成功不覆盖B草稿和保存状态', async () => {
  const saved = deferred()
  const view = component({ getJobDetail: (id: string) => job(id), updateJob: () => saved.promise })
  try {
    await view.state.openDetail(job('A')); addSkill(view.state, 'SQL')
    const saving = view.state.saveSkills()
    await view.state.openDetail(job('B')); addSkill(view.state, 'Java')
    saved.resolve({ success: true }); await saving
    assert.equal(view.state.detailJob.value.id, 'B')
    assert.deepEqual(view.state.detailSkills.value, ['Python', 'Java'])
    assert.equal(view.state.skillDirty.value, true)
    assert.equal(view.state.savingSkills.value, false)
    assert.equal(view.messages.length, 0)
  } finally { view.stop() }
})

test('同岗位保存期间继续编辑，响应保留较新内容且下一次保存以已提交结果为基线', async () => {
  const first = deferred()
  let saves = 0
  const view = component({ updateJob: () => ++saves === 1 ? first.promise : { success: true } })
  try {
    await view.state.openDetail(job('A')); addSkill(view.state, 'SQL')
    const saving = view.state.saveSkills()
    view.state.removeDetailSkill(0); addSkill(view.state, 'Java')
    first.resolve({ success: true }); await saving
    assert.deepEqual(view.state.detailSkills.value, ['SQL', 'Java'])
    assert.equal(view.state.skillDirty.value, true)
    await view.state.saveSkills()
    assert.deepEqual(view.calls.filter(c => c.method === 'updateJob')[1].args[1].required_skills, ['SQL', 'Java'])
    assert.equal(view.state.skillDirty.value, false)
  } finally { view.stop() }
})

test('未确认的编辑框内容不会被详情响应或切换岗位遗留索引破坏', async () => {
  const pending = deferred()
  const view = component({ getJobDetail: (id: string) => id === 'A' ? pending.promise : job(id, ['Go']) })
  try {
    const opening = view.state.openDetail(job('A'))
    view.state.startEditSkill(0); view.state.editValue.value = '草稿'
    pending.resolve(job('A', ['SQL'])); await opening
    assert.deepEqual(view.state.detailSkills.value, ['Python'])
    assert.equal(view.state.editValue.value, '草稿')
    await view.state.openDetail(job('B', ['Go']))
    view.state.confirmEditSkill()
    assert.deepEqual(view.state.detailSkills.value, ['Go'])
    assert.equal(view.state.editingIndex.value, -1)
  } finally { view.stop() }
})

test('列表倒序成功与失败均不覆盖最新列表或提前结束loading', async () => {
  const pending = [deferred(), deferred(), deferred(), deferred()]
  let index = 0
  const view = component({ getJobList: () => pending[index++].promise })
  try {
    const a = view.state.loadPage(), b = view.state.loadPage()
    pending[0].resolve({ list: [job('A')], total: 1 }); await a
    assert.equal(view.state.loading.value, true)
    pending[1].resolve({ list: [job('B')], total: 2 }); await b
    const c = view.state.loadPage(), d = view.state.loadPage()
    pending[3].resolve({ list: [job('D')], total: 4 }); await d
    pending[2].reject(new Error('old')); await c
    assert.equal(view.state.jobs.value[0].id, 'D')
    assert.equal(view.state.total.value, 4)
    assert.equal(view.messages.length, 0)
  } finally { view.stop() }
})

test('搜索、筛选、重置先回第一页且每次只发一个列表请求', async () => {
  const view = component()
  try {
    view.state.page.value = 5
    let input = view.elements('el-input')[0]
    input.props['onUpdate:modelValue']('工程师')
    await input.props.onKeyup({ key: 'Enter' }); await view.timers()
    assert.equal(view.calls.filter(c => c.method === 'getJobList').length, 1)
    assert.equal(view.calls[0].args[0].page, 1)
    view.state.page.value = 5
    const select = view.elements('el-select')[0]
    select.props['onUpdate:modelValue']('boss')
    await select.props.onChange('boss'); await view.timers()
    assert.equal(view.calls.filter(c => c.method === 'getJobList').length, 2)
    view.state.page.value = 5
    await view.state.resetFilters(); await view.timers()
    const queries = view.calls.filter(c => c.method === 'getJobList')
    assert.equal(queries.length, 3)
    assert.deepEqual(queries[2].args[0], { keyword: '', platform: '', category: '', page: 1, page_size: 20 })
  } finally { view.stop() }
})

test('详情失败后重试仍保留此前草稿，成功保存不再额外回读详情', async () => {
  let reads = 0
  const view = component({ getJobDetail: () => { if (++reads === 1) throw new Error('offline'); return job('A') } })
  try {
    await view.state.openDetail(job('A')); addSkill(view.state, 'SQL')
    assert.ok(view.state.detailError.value)
    await view.state.retryDetail()
    assert.deepEqual(view.state.detailSkills.value, ['Python', 'SQL'])
    await view.state.saveSkills()
    assert.equal(reads, 2)
    assert.equal(view.state.skillDirty.value, false)
  } finally { view.stop() }
})

test('页大小变化及相同页码通知仅查询一次，页码先复位', async () => {
  const view = component()
  try {
    view.state.page.value = 5
    const pagination = view.elements('el-pagination')[0]
    await pagination.props.onSizeChange(50)
    await pagination.props.onCurrentChange(1)
    const queries = view.calls.filter(c => c.method === 'getJobList')
    assert.equal(queries.length, 1)
    assert.equal(queries[0].args[0].page, 1)
    assert.equal(queries[0].args[0].page_size, 50)
  } finally { view.stop() }
})

test('平台统计失败不丢正常列表、不显示成功零值，翻页不重复取统计', async () => {
  const view = component({ getJobList: { list: [job('A')], total: 1 }, getJobPlatformStats: new Error('stats offline') })
  try {
    await view.mounted()
    assert.equal(view.state.jobs.value[0]?.id, 'A')
    assert.ok(view.state.statsError.value)
    assert.equal(view.state.statCards.value[0].count, null)
    await view.state.changePage(2)
    assert.equal(view.calls.filter(c => c.method === 'getJobPlatformStats').length, 1)
  } finally { view.stop() }
})

test('列表失败不影响正常平台统计', async () => {
  const view = component({ getJobList: new Error('list offline'), getJobPlatformStats: [{ platform: 'boss', label: 'BOSS', count: 8, unique_titles: 3 }] })
  try {
    await view.mounted()
    assert.equal(view.state.platformStats.value[0]?.count, 8)
    assert.equal(view.state.loading.value, false)
  } finally { view.stop() }
})

test('卸载后列表、详情和统计迟到结果不再更新状态或弹消息', async () => {
  const list = deferred(), detail = deferred(), stats = deferred()
  const view = component({ getJobList: () => list.promise, getJobDetail: () => detail.promise, getJobPlatformStats: () => stats.promise })
  const mounting = view.mounted(), opening = view.state.openDetail(job('A'))
  view.stop()
  list.resolve({ list: [job('late')], total: 1 }); detail.resolve(job('late')); stats.reject(new Error('late'))
  await Promise.all([mounting, opening])
  assert.deepEqual(view.state.jobs.value, [])
  assert.equal(view.state.detailJob.value.id, 'A')
  assert.equal(view.messages.length, 0)
})

test('陈旧列表上先编辑，详情出现服务端新增技能时禁止覆盖保存并可明确放弃草稿重读', async () => {
  const pending = deferred()
  let reads = 0
  const server = job('A', ['Python', '服务端新技能'])
  const view = component({ getJobDetail: () => ++reads === 1 ? pending.promise : server })
  try {
    const opening = view.state.openDetail(job('A')); addSkill(view.state, '我的草稿')
    pending.resolve(server); await opening
    assert.deepEqual(view.state.detailSkills.value, ['Python', '我的草稿'])
    await view.state.saveSkills()
    assert.equal(view.calls.filter(c => c.method === 'updateJob').length, 0)
    assert.ok(view.state.detailError.value)
    await view.state.retryDetail(); await view.state.saveSkills()
    assert.equal(view.calls.filter(c => c.method === 'updateJob').length, 0)
    await view.state.discardAndReload()
    assert.deepEqual(view.state.detailSkills.value, ['Python', '服务端新技能'])
    assert.equal(view.state.skillDirty.value, false)
  } finally { view.stop() }
})

test('列表失败显示错误和重试，失败不能显示成功空态', async () => {
  const view = component({ getJobList: new Error('offline') })
  try {
    await view.state.loadPage()
    assert.ok(view.state.listError.value)
    assert.equal(view.elements('div').some(node => node.props?.class === 'table-empty'), false)
    assert.ok(view.elements('el-alert').some(node => node.props?.type === 'error'))
  } finally { view.stop() }
})

test('卸载后导出迟到不再下载或报告失败', async () => {
  const pending = deferred()
  const view = component({ exportJobs: () => pending.promise })
  const downloading = view.state.exportCurrent()
  view.stop()
  // Node 没有 document；若继续下载会落入 catch 并产生错误消息。
  pending.resolve(new Blob(['synthetic']))
  await downloading
  assert.equal(view.messages.length, 0)
})
