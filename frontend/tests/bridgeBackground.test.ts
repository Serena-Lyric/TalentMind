import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

function harness(overrides: any = {}) {
  let listener: any
  let expire: any
  let timerCleared = 0
  let extractions = 0
  const posted: any[] = []
  const authorized: any[] = []
  const source = readFileSync(new URL('../bridge-extension/background.js', import.meta.url), 'utf8').replace(/^import .*$/m, '')
  runInNewContext(source, {
    captureCurrentPage() {}, AbortController, TypeError, SyntaxError,
    setTimeout: (callback: any, delay: number) => { assert.equal(delay, 15000); expire = callback; return 1 },
    clearTimeout: () => { timerCleared++ },
    chrome: {
      storage: { local: { get: overrides.get || (async () => ({ token: 'synthetic', sessionId: 'bridge-synthetic' })) } },
      tabs: { query: async () => [{ id: 1 }] },
      scripting: { executeScript: async () => { extractions++; return [{ result: overrides.extracted || {
        ok: false, reason: 'security_verification', page_url: 'https://www.zhipin.com/web/passport/zp/security.html',
      } }] } },
      runtime: { onMessage: { addListener: (value: any) => { listener = value } } },
    },
    fetch: async (url: string, options: any) => {
      if (url.endsWith('/permit')) {
        authorized.push({ url, payload: JSON.parse(options.body) })
        if (overrides.permitFetch) return overrides.permitFetch(url, options)
        return { ok: true, json: async () => ({ code: 0, data: { permit: 'synthetic-permit', expires_at: Date.now() / 1000 + 15 } }) }
      }
      posted.push({ url, payload: JSON.parse(options.body), options })
      if (overrides.fetch) return overrides.fetch(url, options)
      return { ok: true, json: async () => ({ code: 0, data: { result: { outcome: 'blocked' } } }) }
    },
  })
  return {
    send: (type = 'capture-detail'): Promise<any> => new Promise(resolve => listener({ type }, {}, resolve)),
    posted, authorized, expire: () => expire(), extractions: () => extractions, cleared: () => timerCleared,
  }
}

const tick = () => new Promise(resolve => setImmediate(resolve))

test('explicit verification capture posts one body-free blocked event', async () => {
  const h = harness()
  const result = await h.send()
  assert.equal(h.posted.length, 1)
  assert.deepEqual(h.posted[0].payload, {
    schema_version: 'm1-browser-bridge-v1', kind: 'blocked',
    page_url: 'https://www.zhipin.com/web/passport/zp/security.html', blocked_reason: 'security_verification',
  })
  assert.equal(result.ok, true)
  assert.equal(h.cleared(), 2)
})

test('background rejects overlapping popup requests before reading the page', async () => {
  let finish: any
  const h = harness({ fetch: () => new Promise(resolve => { finish = resolve }) })
  const first = h.send()
  await tick()
  const duplicate = await h.send('capture-list')
  assert.equal(duplicate.ok, false)
  assert.match(duplicate.error, /已有采集/)
  assert.equal(h.extractions(), 1)
  assert.equal(h.posted.length, 1)
  finish({ ok: true, json: async () => ({ code: 0, data: {} }) })
  assert.equal((await first).ok, true)
  const next = h.send()
  await tick()
  finish({ ok: true, json: async () => ({ code: 0, data: {} }) })
  assert.equal((await next).ok, true)
  assert.equal(h.posted.length, 2)
})

for (const phase of ['fetch', 'body']) {
  test(`timeout during ${phase} aborts without retry and reports uncertain submission`, async () => {
    const h = harness({ fetch: (_url: string, options: any) => {
      const pending = () => new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(new Error('aborted'))))
      return phase === 'fetch' ? pending() : { ok: true, json: pending }
    } })
    const result = h.send()
    await tick()
    h.expire()
    const response = await result
    assert.equal(response.ok, false)
    assert.match(response.error, /超时.*尚未确认/)
    assert.equal(h.posted.length, 1)
    assert.equal(h.posted[0].options.signal.aborted, true)
    assert.equal(h.cleared(), 2)
  })
}

test('network errors and invalid JSON do not claim a failed database write', async () => {
  for (const error of [new TypeError('Failed to fetch'), new SyntaxError('Invalid JSON')]) {
    const h = harness({ fetch: async () => {
      if (error instanceof SyntaxError) return { ok: true, json: async () => { throw error } }
      throw error
    } })
    const response = await h.send()
    assert.match(response.error, /提交结果尚未确认/)
    assert.equal(h.posted.length, 1)
    assert.equal(h.cleared(), 2)
  }
})

test('missing pairing and extractor failures never post, and release the lock', async () => {
  const h = harness({ get: async () => ({}) })
  for (let i = 0; i < 2; i++) assert.match((await h.send()).error, /配对令牌/)
  assert.equal(h.extractions(), 0)
  assert.equal(h.posted.length, 0)
  const page = harness({ extracted: { ok: false, reason: 'unsupported_page' } })
  for (let i = 0; i < 2; i++) assert.match((await page.send()).error, /unsupported_page/)
  assert.equal(page.posted.length, 0)
})

test('server rejection is surfaced and does not leave capture busy', async () => {
  const h = harness({ fetch: async () => ({ ok: false, status: 409, json: async () => ({ detail: 'session_stopped' }) }) })
  for (let i = 0; i < 2; i++) assert.match((await h.send()).error, /session_stopped/)
  assert.equal(h.posted.length, 2)
})


test('frequency authorization happens before extraction and is attached to capture', async () => {
  const h = harness()
  await h.send()
  assert.equal(h.authorized.length, 1)
  assert.equal(h.authorized[0].payload.kind, 'detail')
  assert.equal(h.posted[0].options.headers['X-TalentMind-Capture-Permit'], 'synthetic-permit')
})

test('frequency denial never extracts or submits page content', async () => {
  const h = harness({ permitFetch: async () => ({ ok: false, status: 400, json: async () => ({ code: 4001, message: 'collection_frequency_limited' }) }) })
  const response = await h.send()
  assert.match(response.error, /frequency_limited/)
  assert.equal(h.extractions(), 0)
  assert.equal(h.posted.length, 0)
})

test('missing preflight permit fails closed before reading the active tab', async () => {
  const h = harness({ permitFetch: async () => ({ ok: true, json: async () => ({ code: 0, data: {} }) }) })
  assert.equal((await h.send()).ok, false)
  assert.equal(h.extractions(), 0)
})


test('expired preflight response never dispatches DOM extraction', async () => {
  const h = harness({ permitFetch: async () => ({ ok: true, json: async () => ({ code: 0, data: { permit: 'expired', expires_at: Date.now() / 1000 - 1 } }) }) })
  assert.equal((await h.send()).ok, false)
  assert.equal(h.extractions(), 0)
})
