import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync, existsSync } from 'node:fs'

test('七页路由不再注册看板和分析中心，专属页面与 API 被删除', () => {
  const router = readFileSync(new URL('../src/router/index.ts', import.meta.url), 'utf8')
  assert.doesNotMatch(router, /path: '\/(dashboard|analytics)'/)
  for (const path of ['views/Dashboard.vue', 'views/Analytics.vue', 'api/dashboard.ts']) {
    assert.equal(existsSync(new URL(`../src/${path}`, import.meta.url)), false, path)
  }
})
