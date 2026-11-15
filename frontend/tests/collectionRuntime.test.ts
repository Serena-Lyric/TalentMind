import test from 'node:test'
import assert from 'node:assert/strict'
import { collectionComponent } from './helpers/collectionComponent.ts'

const platform = (name: string, status: string, extra: Record<string, any> = {}) => ({
  platform: name, status, keyword_index: 0, city_index: 0, page: 1,
  next_run_at: null, last_saved_identity: null, last_success_at: null,
  stop_reason: null, stats: { listed: 2, inserted: 1, failed: 0 }, updated_at: 1000,
  ...extra,
})
const snapshot = (boss = 'waiting', zhaopin = 'waiting', liepin = 'waiting') => ({
  status: 'running',
  platforms: { boss: platform('boss', boss), zhaopin: platform('zhaopin', zhaopin), liepin: platform('liepin', liepin) },
})

function button(page: ReturnType<typeof collectionComponent>, id: string) {
  const node = page.renderedNodes().find(node => node.props?.['data-testid'] === id)
  assert.ok(node, `模板应包含 ${id}`)
  return node
}

test('持续采集面板显示三站状态并启动/停止真实接口', async () => {
  const stopped = { status: 'stopped', platforms: { boss: platform('boss', 'stopped'), zhaopin: platform('zhaopin', 'stopped'), liepin: platform('liepin', 'stopped') } }
  const page = collectionComponent({
    getCollectionRuntimeStatus: stopped,
    startCollectionRuntime: snapshot('running', 'running', 'running'),
    stopCollectionRuntime: stopped,
  }, { component: '../../src/components/CollectionRuntime.vue' })
  try {
    await page.mounted()
    assert.equal(page.calls.filter(call => call.method === 'getCollectionRuntimeStatus').length, 1)
    assert.equal(page.renderedNodes().filter(node => node.props?.class === 'runtime-card').length, 3)
    assert.equal(page.renderedNodes().some(node => node.props?.['data-testid'] === 'runtime-reset-checkpoint'), false)
    assert.equal(button(page, 'runtime-start').props.disabled, false)
    assert.equal(button(page, 'runtime-stop').props.disabled, true)

    await button(page, 'runtime-start').props.onClick()
    const startCall = page.calls.find(call => call.method === 'startCollectionRuntime')
    assert.deepEqual(startCall?.args, [{}])
    assert.equal(page.state.notice.value.includes('worker'), true)

    await button(page, 'runtime-stop').props.onClick()
    assert.equal(page.calls.some(call => call.method === 'stopCollectionRuntime'), true)
    assert.equal(page.state.runtime.value.status, 'stopped')
  } finally {
    page.stop()
  }
})

test('单站 blocked/needs_login 分别按确认语义恢复，不触碰其他站', async () => {
  const page = collectionComponent({
    getCollectionRuntimeStatus: snapshot('blocked', 'needs_login', 'failed'),
    resumeCollectionRuntime: (platform: string, confirmed: boolean) => {
      const value = snapshot('blocked', 'needs_login', 'failed')
      value.platforms[platform].status = 'waiting'
      return { ...value, last_resume: { platform, confirmed } }
    },
  }, { component: '../../src/components/CollectionRuntime.vue' })
  try {
    await page.mounted()
    await button(page, 'runtime-resume-boss').props.onClick()
    await button(page, 'runtime-resume-zhaopin').props.onClick()
    await button(page, 'runtime-resume-liepin').props.onClick()
    const resumes = page.calls.filter(call => call.method === 'resumeCollectionRuntime')
    assert.deepEqual(resumes.map(call => call.args), [['boss', true], ['zhaopin', false], ['liepin', true]])
  } finally {
    page.stop()
  }
})


test('全站受限时提供纯本地计划与游标复位入口', async () => {
  const restricted = snapshot('blocked', 'needs_login', 'failed')
  restricted.status = 'attention'
  const calls: any[] = []
  const page = collectionComponent({
    getCollectionRuntimeStatus: restricted,
    startCollectionRuntime: (payload: Record<string, unknown>) => {
      calls.push(payload)
      return restricted
    },
  }, { component: '../../src/components/CollectionRuntime.vue' })
  try {
    await page.mounted()
    const resetButton = page.renderedNodes().find(node => node.props?.['data-testid'] === 'runtime-reset-checkpoint')
    assert.ok(resetButton)
    assert.equal(button(page, 'runtime-start').props.disabled, true)

    await resetButton.props.onClick()

    assert.deepEqual(calls, [{ reset_checkpoint: true }])
    assert.match(page.state.notice.value, /本地计划与游标已复位/)
    assert.equal(page.state.runtime.value.platforms.boss.status, 'blocked')
    assert.equal(page.state.runtime.value.platforms.zhaopin.status, 'needs_login')
    assert.equal(page.state.runtime.value.platforms.liepin.status, 'failed')
  } finally {
    page.stop()
  }
})


test('partial start notice reports only workers actually started', async () => {
  const stopped = { status: 'stopped', platforms: { boss: platform('boss', 'stopped'), zhaopin: platform('zhaopin', 'stopped'), liepin: platform('liepin', 'stopped') } }
  const partial = snapshot('waiting', 'blocked', 'waiting')
  const page = collectionComponent({
    getCollectionRuntimeStatus: stopped,
    startCollectionRuntime: partial,
  }, { component: '../../src/components/CollectionRuntime.vue' })
  try {
    await page.mounted()
    await button(page, 'runtime-start').props.onClick()
    assert.match(page.state.notice.value, /已为 2 个可运行平台启动 worker/)
    assert.match(page.state.notice.value, /智联招聘/)
  } finally {
    page.stop()
  }
})
