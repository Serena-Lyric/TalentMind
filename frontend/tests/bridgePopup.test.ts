import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

function harness(sendError: Error | null = null) {
  const nodes = new Map<string, any>()
  for (const name of ['token', 'session', 'status', 'capture-list', 'capture-detail']) {
    nodes.set('#' + name, { value: '', textContent: '', disabled: false, handlers: {}, addEventListener(type: string, fn: any) { this.handlers[type] = fn } })
  }
  let save: any = async () => {}
  let sends = 0
  runInNewContext(readFileSync(new URL('../bridge-extension/popup.js', import.meta.url), 'utf8'), {
    document: { querySelector: (selector: string) => nodes.get(selector), querySelectorAll: () => [nodes.get('#capture-list'), nodes.get('#capture-detail')] },
    chrome: {
      storage: { local: { get: async () => ({}), set: () => save() } },
      runtime: { sendMessage: async () => { sends++; if (sendError) throw sendError; return { ok: true, data: { result: { outcome: 'captured' } } } } },
    },
  })
  return { nodes, save: (fn: any) => { save = fn }, sends: () => sends, click: () => nodes.get('#capture-list').handlers.click() }
}

test('popup locks synchronously before pairing save and suppresses rapid clicks', async () => {
  const h = harness()
  let finish: any
  h.save(() => new Promise(resolve => { finish = resolve }))
  const first = h.click()
  assert.equal(h.nodes.get('#capture-list').disabled, true)
  await h.click()
  assert.equal(h.sends(), 0)
  finish()
  await first
  assert.equal(h.sends(), 1)
  assert.equal(h.nodes.get('#capture-list').disabled, false)
})

test('pairing save failure is shown and leaves popup retryable without sending', async () => {
  const h = harness()
  h.save(async () => { throw new Error('storage unavailable') })
  await h.click()
  assert.match(h.nodes.get('#status').textContent, /storage unavailable/)
  assert.equal(h.nodes.get('#capture-detail').disabled, false)
  assert.equal(h.sends(), 0)
  h.save(async () => {})
  await h.click()
  assert.equal(h.sends(), 1)
})


test('disconnected extension channel leaves the submission explicitly uncertain', async () => {
  const h = harness(new Error('Message port closed'))
  await h.click()
  assert.match(h.nodes.get('#status').textContent, /通信中断.*结果尚未确认/)
  assert.equal(h.nodes.get('#capture-detail').disabled, false)
  assert.equal(h.sends(), 1)
})
