import { test } from 'node:test'
import assert from 'node:assert/strict'

import { collectionComponent } from './helpers/collectionComponent.ts'

const platforms = [
  { platform: 'boss', label: 'BOSS直聘', supported: true, cities: [{ name: '北京', code: '101010100' }] },
]

const runId = 'bridge-11111111111111111111111111111111'

function liveSession(overrides: Record<string, any> = {}) {
  return {
    run_id: runId,
    platform: 'boss',
    status: 'waiting_for_capture',
    keywords: ['Java'],
    cities: [{ name: '北京', code: '101010100' }],
    listed: 0,
    detail_attempted: 0,
    detail_obtained: 0,
    content_eligible: 0,
    identity_verified: 0,
    identity_pending: 0,
    complete: 0,
    inserted: 0,
    updated: 0,
    skipped: 0,
    rejected: 0,
    failed: 0,
    finished_at: null,
    ...overrides,
  }
}

test('creates a paired BOSS session without preparing or starting CDP', async () => {
  const page = collectionComponent({}, { component: '../../src/components/CollectionBridge.vue', props: { platforms } })
  try {
    await page.mounted()
    page.state.keyword.value = ' Java '
    page.state.cityCode.value = '101010100'

    await page.state.createSession()

    const call = page.calls.find(item => item.method === 'createBridgeSession')!
    assert.deepEqual(call.args[0], {
      platform: 'boss',
      keyword: 'Java',
      city_name: '北京',
      city_code: '101010100',
      pages: 1,
      detail_limit: 5,
      max_jobs: 5,
    })
    assert.equal(page.calls.some(item => /^(prepareCollection|getCDPStatus|startCollection)$/.test(item.method)), false)
    assert.equal(page.state.session.value.run_id, runId)
    assert.equal(page.state.pairing.value.token, 'pair-token')
    assert.equal(page.events.filter(item => item.name === 'busy').at(-1)?.value, true)
  } finally {
    page.stop()
  }
})

test('refresh preserves independent bridge counters and exact run results', async () => {
  const page = collectionComponent({
    getBridgeSession: liveSession({
      listed: 5, detail_attempted: 1, detail_obtained: 1, content_eligible: 1,
      identity_verified: 1, complete: 1, inserted: 1,
    }),
    getCollectionResults: [{
      job_title: 'Java 后端工程师', outcome: 'inserted', jd_pool_id: 42,
      identity_status: 'verified', content_eligible: true,
      rejection_reason: null, source_detail: 'https://www.zhipin.com/job_detail/42.html',
    }],
  }, { component: '../../src/components/CollectionBridge.vue', props: { platforms } })
  try {
    await page.mounted()
    page.state.session.value = liveSession()

    await page.state.refreshSession()

    assert.equal(page.state.session.value.listed, 5)
    assert.equal(page.state.session.value.inserted, 1)
    const inserted = page.state.countItems.value.find((item: any) => item.key === 'inserted')
    const complete = page.state.countItems.value.find((item: any) => item.key === 'complete')
    assert.equal(inserted.value, '1')
    assert.equal(complete.value, '1')
    assert.equal(page.state.results.value[0].jd_pool_id, 42)
    assert.equal(page.state.identityText('verified'), '身份已验证')
  } finally {
    page.stop()
  }
})

test('finish and stop require explicit actions and preserve stopped reason', async () => {
  const page = collectionComponent({
    finishBridgeSession: (_id: string, reason?: string) => liveSession({
      status: reason ? 'stopped' : 'completed',
      finished_at: '2026-10-22T00:00:00Z',
      stop_reason: reason || null,
    }),
  }, { component: '../../src/components/CollectionBridge.vue', props: { platforms } })
  try {
    await page.mounted()
    page.state.session.value = liveSession()

    await page.state.finishSession()
    assert.equal(page.calls.filter(item => item.method === 'finishBridgeSession').length, 1)
    assert.equal(page.calls.find(item => item.method === 'finishBridgeSession')!.args[1], undefined)

    page.state.session.value = liveSession()
    await page.state.stopSession()
    assert.equal(page.calls.findLast(item => item.method === 'finishBridgeSession')!.args[1], 'user_stopped')
    assert.equal(page.state.session.value.status, 'stopped')
    assert.equal(page.events.filter(item => item.name === 'busy').at(-1)?.value, false)
  } finally {
    page.stop()
  }
})

test('invalid pairing or empty configuration does not create a bridge session', async () => {
  const page = collectionComponent({
    getBridgePairing: new Error('pairing unavailable'),
  }, { component: '../../src/components/CollectionBridge.vue', props: { platforms } })
  try {
    await page.mounted()
    page.state.keyword.value = ''
    await page.state.createSession()
    assert.equal(page.calls.some(item => item.method === 'createBridgeSession'), false)
    assert.match(page.messages.join(' '), /令牌|关键词|配对/)
  } finally {
    page.stop()
  }
})
