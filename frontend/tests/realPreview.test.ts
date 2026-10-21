import { test } from 'node:test'
import assert from 'node:assert/strict'
import { allowRealPreviewRequest } from '../realPreview.ts'

test('私有原文仅允许同源 loopback；拒绝外部 Origin、Host 和远端地址',()=>{
  assert.equal(allowRealPreviewRequest('127.0.0.1','127.0.0.1:18090','http://127.0.0.1:18090'),true)
  assert.equal(allowRealPreviewRequest('::1','localhost:18090',undefined),true)
  assert.equal(allowRealPreviewRequest('127.0.0.1','127.0.0.1:18090','https://foreign.example'),false)
  assert.equal(allowRealPreviewRequest('127.0.0.1','foreign.example',undefined),false)
  assert.equal(allowRealPreviewRequest('192.168.1.2','localhost:18090',undefined),false)
})
