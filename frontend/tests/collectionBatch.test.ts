import test from 'node:test'
import assert from 'node:assert/strict'
import { collectionComponent } from './helpers/collectionComponent.ts'

const platforms = [{ platform: 'boss', label: 'BOSS', supported: true, cities: [{ name: '北京', code: '101' }, { name: '上海', code: '102' }] }, { platform: 'zhaopin', label: '智联', supported: true, cities: [{ name: '北京', code: '530' }] }]
const queued = { batch_id: 'batch-one', platform: 'boss', status: 'queued', total: 6, completed: 0, items: [{ item_id: 'one', keyword: 'Python', city: platforms[0]!.cities[0], status: 'queued', run_id: null, complete: null }] }
function batch(overrides: Record<string, any> = {}, props: Record<string, any> = {}) { return collectionComponent(overrides, { batch: true, props: { platforms, singleBusy: false, ...props } }) }
function configure(page: ReturnType<typeof batch>) { page.state.platform.value = 'boss'; page.state.keywords.value = [' Python ', 'Java', '前端', 'Python']; page.state.cityCodes.value = ['101', '102', '101'] }

test('批次创建前去重预览3×2，创建计划不会准备或开始，未执行计数为—', async () => {
  const page = batch({ createCollectionBatch: queued })
  try {
    await page.mounted(); configure(page)
    assert.equal(page.state.combinations.value.length, 6)
    await page.state.createBatch()
    assert.deepEqual(page.calls.find(call => call.method === 'createCollectionBatch')!.args[0], { platform: 'boss', keywords: ['Python', 'Java', '前端'], cities: platforms[0]!.cities, pages: 1, max_jobs: 5, detail_limit: 5 })
    assert.equal(page.calls.some(call => /prepare|start/i.test(call.method)), false)
    assert.equal(page.state.selectedBatch.value.status, 'queued')
    assert.equal(page.state.formatCount(page.state.selectedBatch.value.items[0].complete), '—')
    assert.equal(page.state.statusText('queued'), '待执行')
  } finally { page.stop() }
})

test('平台切换重置城市，未知城市与超过10关键词或50组合不可创建', async () => {
  const page = batch()
  try {
    await page.mounted(); configure(page)
    page.state.platform.value = 'zhaopin'
    assert.deepEqual(page.state.cityCodes.value, [])
    page.state.cityCodes.value = ['101']
    assert.equal(page.state.canCreate.value, false)
    page.state.cityCodes.value = ['530']; page.state.keywords.value = Array.from({ length: 11 }, (_, i) => `K${i}`)
    assert.equal(page.state.canCreate.value, false)
    page.props.platforms = [{ ...platforms[0], cities: Array.from({ length: 6 }, (_, i) => ({ name: `城市${i}`, code: String(i) })) }]
    page.state.platform.value = 'boss'; page.state.keywords.value = Array.from({ length: 9 }, (_, i) => `K${i}`); page.state.cityCodes.value = ['0', '1', '2', '3', '4', '5']
    assert.equal(page.state.combinations.value.length, 54)
    assert.equal(page.state.canCreate.value, false)
    await page.state.createBatch()
    assert.equal(page.calls.some(call => call.method === 'createCollectionBatch'), false)
  } finally { page.stop() }
})

test('开始必须显式操作且服从单任务互斥，停止统一调用批次接口', async () => {
  const running = { ...queued, status: 'running' }
  const page = batch({ getCollectionBatches: { items: [queued], total: 1 }, getCollectionBatch: queued, startCollectionBatch: running, stopCollectionBatch: { ...queued, status: 'stopping' } })
  try {
    await page.mounted(); await page.state.selectBatch(queued.batch_id)
    page.props.singleBusy = true
    await page.state.startBatch()
    assert.equal(page.calls.some(call => call.method === 'startCollectionBatch'), false)
    page.props.singleBusy = false
    await page.state.startBatch()
    assert.equal(page.state.selectedBatch.value.status, 'running')
    await page.state.stopBatch()
    assert.equal(page.state.selectedBatch.value.status, 'stopping')
    assert.deepEqual(page.calls.find(call => call.method === 'stopCollectionBatch')!.args, ['batch-one'])
    assert.equal(page.calls.some(call => /^(prepareCollection|startCollection|stopCollection)$/.test(call.method)), false)
  } finally { page.stop() }
})

test('选择新批次后旧详情响应不可覆盖；卸载清除轮询且轮询不启动', async () => {
  let finish!: (value: any) => void
  const page = batch({ getCollectionBatch: (id: string) => id === 'old' ? new Promise(resolve => { finish = resolve }) : { ...queued, batch_id: id } })
  await page.mounted()
  const previous = page.state.selectBatch('old')
  await page.state.selectBatch('new')
  finish({ ...queued, batch_id: 'old' }); await previous
  assert.equal(page.state.selectedBatch.value.batch_id, 'new')
  for (const callback of page.intervals) await callback()
  page.stop()
  assert.ok(page.cleared.length > 0)
  assert.equal(page.calls.some(call => /prepare|start/i.test(call.method)), false)
})

test('最老批次单项不在历史列表仍通过精确接口读取日志并复用原抽屉', async () => {
  const task = { run_id: 'run-one', platform: 'boss', status: 'completed', raw_log_tail: ['真实任务日志'] }
  const page = batch({ getCollectionBatchItemTask: task })
  try {
    await page.mounted()
    page.state.selectedBatch.value = queued
    await page.state.inspectItem({ ...queued.items[0], run_id: 'run-one', status: 'completed' })
    assert.deepEqual(page.events.find(event => event.name === 'inspect')!.value, task)
    assert.deepEqual(page.calls.find(call => call.method === 'getCollectionBatchItemTask')!.args, ['batch-one', 'one'])
    assert.equal(page.calls.some(call => call.method === 'getCollectionHistory'), false)
    assert.equal(page.calls.some(call => call.method === 'getCollectionRaw'), false)
  } finally { page.stop() }
})

test('切换单项后精确接口的旧响应不可覆盖新日志', async () => {
  let finish!: (value: any) => void
  const page = batch({ getCollectionBatchItemTask: (_batch: string, item: string) => item === 'old' ? new Promise(resolve => { finish = resolve }) : { run_id: 'run-new', status: 'completed', raw_log_tail: ['新日志'] } })
  try {
    await page.mounted(); page.state.selectedBatch.value = queued
    const previous = page.state.inspectItem({ ...queued.items[0], item_id: 'old', run_id: 'run-old' })
    assert.equal(typeof finish, 'function')
    await page.state.inspectItem({ ...queued.items[0], item_id: 'new', run_id: 'run-new' })
    finish({ run_id: 'run-old', raw_log_tail: ['旧日志'] }); await previous
    const inspected = page.events.filter(event => event.name === 'inspect')
    assert.equal(inspected.length, 1)
    assert.equal(inspected[0]!.value.run_id, 'run-new')
    assert.deepEqual(inspected[0]!.value.raw_log_tail, ['新日志'])
  } finally { page.stop() }
})

test('精确单项接口鉴权失败显示错误，不用当前另一任务冒充结果', async () => {
  const page = batch({ getCollectionBatchItemTask: new Error('403 仅允许本地日志访问') }, { currentTask: { run_id: 'unrelated-run', raw_log_tail: ['无关任务日志'] } })
  try {
    await page.mounted(); page.state.selectedBatch.value = queued
    await page.state.inspectItem({ ...queued.items[0], run_id: 'run-one' })
    assert.match(page.state.error.value, /403.*本地/)
    assert.equal(page.events.some(event => event.name === 'inspect'), false)
  } finally { page.stop() }
})

test('精确单项文件缺失保留服务端缺失状态，不伪造真实日志', async () => {
  const task = { run_id: 'run-one', status: 'completed', log_status: 'missing', raw_log_tail: [] }
  const page = batch({ getCollectionBatchItemTask: task })
  try {
    await page.mounted(); page.state.selectedBatch.value = queued
    await page.state.inspectItem({ ...queued.items[0], run_id: 'run-one' })
    assert.deepEqual(page.events.find(event => event.name === 'inspect')!.value, task)
  } finally { page.stop() }
})

test('执行或等待中的其他批次阻止再次开始，blocked不会自动重试', async () => {
  const active = { ...queued, batch_id: 'active', status: 'waiting_next_round' }
  const page = batch({ getCollectionBatches: { items: [active, queued], total: 2 }, getCollectionBatch: (id: string) => id === 'active' ? active : queued })
  try {
    await page.mounted(); await page.state.selectBatch(queued.batch_id)
    assert.equal(page.state.canStart.value, false)
    await page.state.startBatch()
    assert.match(page.state.launchHint.value, /active/)
    page.state.batches.value = [{ ...queued, status: 'blocked', stop_reason: 'verification_required' }]
    page.state.selectedBatch.value = page.state.batches.value[0]
    assert.equal(page.state.canStart.value, false)
    for (const callback of page.intervals) await callback()
    assert.equal(page.calls.some(call => call.method === 'startCollectionBatch'), false)
  } finally { page.stop() }
})

test('批次占用时单轮页不能准备、开始或单独停止批次子项', async () => {
  const page = collectionComponent({ getCollectionStatus: { run_id: 'batch-child', status: 'running' } })
  try {
    await page.mounted(); page.state.batchBusy.value = true
    await page.state.prepareBrowser(); await page.state.startTask(); await page.state.stopTask()
    assert.equal(page.state.canStop.value, false)
    assert.equal(page.calls.some(call => /^(prepareCollection|startCollection|stopCollection)$/.test(call.method)), false)
  } finally { page.stop() }
})

test('批次运行会撤销之前单轮准备凭据，结束后仍需重新准备目标', async () => {
  const page = collectionComponent()
  try {
    await page.mounted(); await page.state.prepareBrowser()
    assert.equal(page.state.canStart.value, true)
    page.state.batchBusy.value = true
    page.state.batchBusy.value = false
    assert.equal(page.state.canStart.value, false)
    assert.equal(page.state.preparedFor.value, null)
  } finally { page.stop() }
})
