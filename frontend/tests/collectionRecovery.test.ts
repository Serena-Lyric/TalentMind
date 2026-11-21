import test from 'node:test'
import assert from 'node:assert/strict'
import { collectionComponent } from './helpers/collectionComponent.ts'

const clear = (platform: string) => ({ platform, state: 'clear', can_recover: false, recovery_token: null, message: '频率状态正常' })
const unfinished = { ...clear('boss'), state: 'unfinished', can_recover: true, recovery_token: 'generation-one', reason: 'collection_action_unfinished', message: '上一次采集动作未结束，请确认恢复' }
function button(page: ReturnType<typeof collectionComponent>, id: string) {
  const node = page.renderedNodes().find(node => node.props?.['data-testid'] === id)
  assert.ok(node, `模板应包含 ${id}`)
  return node
}

test('执行结束与实际结果分开，全拒绝、部分写入、无结果和未知分母均有明确摘要', async () => {
  const page = collectionComponent()
  try {
    await page.mounted()
    const base = { run_id: 'r', status: 'completed', listed: 2, inserted: 0, updated: 0, skipped: 0, rejected: 2, failed: 0 }
    assert.equal(page.state.statusText('completed'), '执行结束')
    assert.match(page.state.taskOutcome(base), /未入库.*拒绝 2/)
    assert.match(page.state.taskOutcome({ ...base, inserted: 1, rejected: 1 }), /新增 1.*拒绝 1/)
    assert.match(page.state.taskOutcome({ ...base, listed: 0, rejected: 0 }), /未识别到列表岗位/)
    assert.match(page.state.taskOutcome({ run_id: 'legacy', status: 'completed' }), /写入计数未知/)
    assert.doesNotMatch(page.state.taskOutcome({ run_id: 'legacy', status: 'completed' }), /0|100%/)
    assert.match(page.state.taskOutcome({ run_id: 'partial', status: 'completed', inserted: 1 }), /新增 1.*更新 —/)
    for (const task of [base, { ...base, inserted: 1, rejected: 1 }, { run_id: 'legacy', status: 'completed' }]) {
      page.state.currentTask.value = task
      assert.ok(page.renderedNodes().some(node => node.props?.class === 'outcome-summary' && node.children === page.state.taskOutcome(task)))
    }
  } finally { page.stop() }
})

test('schema缺列提示具体字段，准备诊断与历史仍可操作', async () => {
  const page = collectionComponent({ getCollectionReadiness: { ready: false, missing_columns: ['identity_status'], message: '数据库缺少身份字段', next_step: '请先申请数据库迁移授权' } })
  try {
    await page.mounted()
    assert.match(page.state.readinessMessage.value, /identity_status.*迁移授权/)
    assert.equal(button(page, 'prepare-browser').props.disabled, false)
    await button(page, 'prepare-browser').props.onClick()
    assert.equal(page.calls.some(call => call.method === 'prepareCollection'), true)
    await page.state.openHistory({ run_id: 'old', status: 'completed' })
    assert.equal(page.state.showHistory.value, true)
  } finally { page.stop() }
})

test('模板恢复动作携带诊断token，重复点击只请求一次，恢复后仍需显式准备', async () => {
  let value: any = unfinished
  let finish!: (value: any) => void
  const page = collectionComponent({
    getCollectionFrequency: (platform: string) => platform === 'boss' ? value : clear(platform),
    recoverCollectionFrequency: () => new Promise(resolve => { finish = resolve }),
  })
  try {
    await page.mounted()
    assert.equal(button(page, 'prepare-browser').props.disabled, true)
    const action = button(page, 'recover-boss').props.onClick
    const pending = action()
    await action()
    assert.deepEqual(page.calls.filter(call => call.method === 'recoverCollectionFrequency').map(call => call.args), [['boss', 'generation-one']])
    value = clear('boss')
    finish({ ...value, recovered: true })
    await pending
    assert.equal(page.state.preparedFor.value, null)
    assert.equal(button(page, 'prepare-browser').props.disabled, false)
    assert.equal(page.calls.some(call => call.method === 'prepareCollection'), false)
  } finally { page.stop() }
})

test('刷新后的访问证据替换旧busy错误，并保留重新准备要求', async () => {
  const page = collectionComponent({
    prepareCollection: new Error('collection_action_unfinished'),
    getCDPStatus: { reachable: true, platform_access: { boss: { access_state: 'public_accessible', can_collect: true, message: '当前页面可访问' } } },
  })
  try {
    await page.mounted()
    await page.state.prepareBrowser()
    assert.match(page.state.accessMessage.value, /未结束|未完成/)
    await page.state.refreshAll(true)
    assert.doesNotMatch(page.state.accessMessage.value, /collection_action_unfinished|准备失败/)
    assert.equal(page.state.preparedFor.value, null)
  } finally { page.stop() }
})

test('最近任务结果模板入口打开对应历史，不覆盖最近任务', async () => {
  const page = collectionComponent({ getCollectionStatus: { run_id: 'all-rejected', status: 'completed', inserted: 0, updated: 0, rejected: 2 }, getCollectionResults: [{ job_title: '详情标题', outcome: 'rejected', rejection_reason: 'missing_list_title' }] })
  try {
    await page.mounted()
    await button(page, 'inspect-current').props.onClick()
    assert.equal(page.state.selectedTask.value.run_id, 'all-rejected')
    assert.equal(page.state.historyResults.value[0].rejection_reason, 'missing_list_title')
    assert.equal(page.state.currentTask.value.run_id, 'all-rejected')
    await button(page, 'retry-prepare').props.onClick()
    assert.equal(page.calls.filter(call => call.method === 'prepareCollection').length, 1)
  } finally { page.stop() }
})

test('数据库检查失败保持未知，准备动作不依赖就绪状态', async () => {
  let unavailable = true
  const page = collectionComponent({ getCollectionReadiness: () => {
    if (unavailable) throw new Error('offline')
    return { ready: true, missing_columns: [], message: '就绪', next_step: '' }
  } })
  try {
    await page.mounted()
    assert.match(page.state.readinessMessage.value, /未知.*offline/)
    assert.doesNotMatch(page.state.readinessMessage.value, /缺少字段/)
    await page.state.prepareBrowser()
    assert.equal(page.state.preparedFor.value, 'boss')
    unavailable = false
    await page.state.refreshAll()
    assert.equal(page.state.preparedFor.value, 'boss')
  } finally { page.stop() }
})

test('迟到的恢复前诊断不覆盖新恢复结果，失败会刷新并显示中文原因', async () => {
  let delayed = false
  let respond!: (value: any) => void
  let value: any = unfinished
  let failRecovery = true
  const page = collectionComponent({
    getCollectionFrequency: (platform: string) => {
      if (platform !== 'boss') return clear(platform)
      if (delayed) { delayed = false; return new Promise(resolve => { respond = resolve }) }
      return value
    },
    recoverCollectionFrequency: () => {
      if (failRecovery) throw new Error('collection_action_changed: refresh before recovery')
      value = clear('boss')
      return { ...value, recovered: true }
    },
  })
  try {
    await page.mounted()
    await button(page, 'recover-boss').props.onClick()
    assert.match(page.state.recoveryMessage.value, /动作已变化/)
    assert.equal(page.state.frequencies.value.boss.state, 'unfinished')
    failRecovery = false
    delayed = true
    const pending = page.state.loadFrequencies()
    await button(page, 'recover-boss').props.onClick()
    respond(unfinished)
    await pending
    assert.equal(page.state.frequencies.value.boss.state, 'clear')
  } finally { page.stop() }
})

test('历史切换与卸载丢弃迟到响应，诊断读取失败禁止恢复', async () => {
  let finish!: (value: any) => void
  const page = collectionComponent({
    getCollectionFrequency: new Error('offline'),
    getCollectionResults: (id: string) => id === 'old' ? new Promise(resolve => { finish = resolve }) : [{ job_title: id }],
  })
  try {
    await page.mounted()
    assert.equal(page.state.frequencies.value.boss.state, 'unavailable')
    assert.equal(page.renderedNodes().some(node => node.props?.['data-testid'] === 'recover-boss'), false)
    const old = page.state.openHistory({ run_id: 'old', status: 'completed' })
    await page.state.openHistory({ run_id: 'new', status: 'completed' })
    finish([{ job_title: 'old' }])
    await old
    assert.equal(page.state.historyResults.value[0].job_title, 'new')
    const pending = page.state.openHistory({ run_id: 'old', status: 'completed' })
    page.stop()
    finish([{ job_title: 'after unmount' }])
    await pending
    assert.equal(page.state.historyResults.value.length, 0)
  } finally { page.stop() }
})
