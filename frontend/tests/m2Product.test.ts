import test from 'node:test'
import assert from 'node:assert/strict'
import { m2Component } from './helpers/m2Component.ts'

const draft = { run_id: 'a'.repeat(32), status: 'queued', items: [], versions: { revision: 'v1' }, summary: { input_total: 5, stage_complete: 0, finalized: 0, final_counts: {} } }

test('进入和轮询不启动，创建只冻结；开始和停止必须显式操作', async () => {
  const page = m2Component({ createM2Run: draft, getM2Run: draft, startM2Run: { ...draft, status: 'running' }, stopM2Run: { ...draft, status: 'stopping' } })
  try {
    await page.mounted(); for (const poll of page.intervals) await poll()
    assert.equal(page.calls.some(c => /start|create/i.test(c.method)), false)
    await page.state.createRun()
    assert.equal(page.state.selected.value.status, 'queued')
    assert.equal(page.calls.some(c => c.method === 'startM2Run'), false)
    await page.state.startRun(); await page.state.stopRun()
    assert.deepEqual(page.calls.find(c => c.method === 'startM2Run').args, [draft.run_id])
    assert.deepEqual(page.calls.find(c => c.method === 'stopM2Run').args, [draft.run_id])
    assert.equal(page.calls.some(c => /Collection/.test(c.method)), false)
  } finally { page.stop() }
  assert.ok(page.cleared.length)
})

test('历史成员模式不携带范围过滤，输入上限和反向ID范围阻止创建', async () => {
  const page = m2Component({ createM2Run: draft })
  try {
    await page.mounted()
    page.state.idMin.value = 9; page.state.idMax.value = 2
    await page.state.createRun()
    assert.equal(page.calls.some(c => c.method === 'createM2Run'), false)
    page.state.cohort.value = 'main120'
    await page.state.createRun()
    assert.deepEqual(page.calls.find(c => c.method === 'createM2Run').args[0], { cohort: 'main120', limit: 120, sources: [], id_min: null, id_max: null })
  } finally { page.stop() }
})

test('选择新任务后旧任务和旧JD响应不能覆盖', async () => {
  let finish!: (v: any) => void, finishItem!: (v: any) => void
  const page = m2Component({ getM2Run: (id: string) => id === 'old' ? new Promise(resolve => { finish = resolve }) : { ...draft, run_id: id }, getM2Item: (_id: string, ordinal: number) => ordinal === 1 ? new Promise(resolve => { finishItem = resolve }) : { ordinal } })
  try {
    await page.mounted()
    const first = page.state.selectRun('old'); await page.state.selectRun('new')
    finish({ ...draft, run_id: 'old' }); await first
    assert.equal(page.state.selected.value.run_id, 'new')
    const item = page.state.inspectItem(1); await page.state.inspectItem(2)
    finishItem({ ordinal: 1 }); await item
    assert.equal(page.state.detail.value.ordinal, 2)
  } finally { page.stop() }
})

test('失败显示原因且不补造结果，版本重放生成待执行任务', async () => {
  const page = m2Component({ getM2Run: draft, getM2Item: new Error('本地原文门禁拒绝'), replayM2Run: { ...draft, run_id: 'replay' } })
  try {
    await page.mounted(); await page.state.selectRun(draft.run_id)
    await page.state.inspectItem(1)
    assert.equal(page.state.detail.value, null)
    assert.match(page.state.error.value, /门禁拒绝/)
    page.state.revision.value = 'v2'
    await page.state.replayRun()
    assert.equal(page.state.selected.value.run_id, 'replay')
    assert.deepEqual(page.calls.find(c => c.method === 'replayM2Run').args, [draft.run_id, 'v2'])
    assert.equal(page.calls.some(c => c.method === 'startM2Run'), false)
  } finally { page.stop() }
})

test('冻结创建较慢时，不能覆盖用户后来选择的历史任务', async () => {
  let finish!: (v: any) => void
  const page = m2Component({ createM2Run: () => new Promise(resolve => { finish = resolve }), getM2Run: { ...draft, run_id: 'chosen' } })
  try {
    await page.mounted()
    const pending = page.state.createRun()
    await page.state.selectRun('chosen')
    finish(draft); await pending
    assert.equal(page.state.selected.value.run_id, 'chosen')
  } finally { page.stop() }
})
