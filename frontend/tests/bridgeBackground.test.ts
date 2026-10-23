import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

test('explicit capture on a verification page reports the block once to its bridge session', async () => {
  let listener: any
  const posted: any[] = []
  const source = readFileSync(new URL('../bridge-extension/background.js', import.meta.url), 'utf8').replace(/^import .*$/m, '')
  runInNewContext(source, {
    captureCurrentPage() {},
    chrome: {
      storage: { local: { get: async () => ({ token: 'synthetic', sessionId: 'bridge-synthetic' }) } },
      tabs: { query: async () => [{ id: 1 }] },
      scripting: { executeScript: async () => [{ result: {
        ok: false, reason: 'security_verification', page_url: 'https://www.zhipin.com/web/passport/zp/security.html',
      } }] },
      runtime: { onMessage: { addListener: (value: any) => { listener = value } } },
    },
    fetch: async (url: string, options: any) => {
      posted.push({ url, payload: JSON.parse(options.body) })
      return { ok: true, json: async () => ({ code: 0, data: { result: { outcome: 'blocked' } } }) }
    },
  })
  const result: any = await new Promise(resolve => listener({ type: 'capture-detail' }, {}, resolve))
  assert.equal(posted.length, 1)
  assert.equal(posted[0].payload.kind, 'blocked')
  assert.equal(posted[0].payload.blocked_reason, 'security_verification')
  assert.equal(result.ok, true)
})
