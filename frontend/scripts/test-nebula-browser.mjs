import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { buildRelationLayout } from '../src/graph/nebulaLayout.ts'

// Run against a running isolated frontend; all business GETs use its real API.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright')
const base = process.env.NEBULA_URL || 'http://127.0.0.1:18087/'
const output = resolve(process.env.NEBULA_OUTPUT || '../docs/review/assets/issue-26-p05')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true, channel: 'msedge' })
const results = { browser: browser.version(), base, checks: [], screenshots: [], errors: [], writes: [] }
const check = (name, details) => { results.checks.push({ name, details }); console.log('PASS', name) }
try {
  const context = await browser.newContext({ viewport: { width: 1600, height: 900 } })
  await context.route('**/api/**', route => {
    if (['GET', 'HEAD'].includes(route.request().method())) return route.continue()
    results.writes.push(route.request().method() + ' ' + route.request().url())
    return route.abort()
  })
  const page = await context.newPage()
  page.on('pageerror', error => results.errors.push(error.message))
  const state = () => page.locator('.nebula-page').evaluate(el => JSON.parse(el.dataset.nebula))
  const settle = () => page.waitForTimeout(250)
  const blur = () => page.locator('.nebula-title').click()
  const shot = async name => {
    await page.screenshot({ path: resolve(output, name + '.png') })
    results.screenshots.push(name + '.png')
  }
  const graphReady = async () => {
    await page.waitForFunction(() => {
      const el = document.querySelector('.nebula-page')
      return el?.dataset.nebula && JSON.parse(el.dataset.nebula).lastFit?.points === 7845
    })
    await page.locator('.nebula-state').waitFor({ state: 'hidden' })
    await settle()
  }
  await page.goto(base + '?nebulaDebug=1#/graph')
  await page.locator('.login-card').waitFor()
  await page.keyboard.press('y'); await page.keyboard.press('h')
  assert.equal(await page.locator('.app-shell--graph-immersive').count(), 0)
  await page.getByPlaceholder('账号', { exact: true }).fill('admin')
  await page.getByPlaceholder('密码', { exact: true }).fill('wrong')
  await page.locator('.login-btn').click()
  assert.match(await page.locator('.login-error').innerText(), /账号或密码错误/)
  await page.locator('.chip').first().click(); await page.locator('.login-btn').click()
  await graphReady()
  check('登录守卫、错误密码、演示登录及登录页热键隔离')

  for (const [width, height] of [[1600, 900], [1920, 1080]]) {
    await page.setViewportSize({ width, height }); await settle()
    await page.getByRole('button', { name: '重置视图', exact: true }).click(); await settle()
    let s = await state()
    assert.equal(s.lastFit.outside, 0); assert.equal(s.lastFit.points, 7845)
    const bounds = await page.evaluate(() => {
      const box = selector => { const b = document.querySelector(selector).getBoundingClientRect(); return { x: b.x, y: b.y, bottom: b.bottom, width: b.width, height: b.height } }
      return { nav: box('.sidebar-card'), graph: box('.nebula-page'), overflow: document.documentElement.scrollHeight > innerHeight }
    })
    assert.equal(bounds.nav.y, bounds.graph.y); assert.equal(bounds.nav.bottom, bounds.graph.bottom); assert.equal(bounds.overflow, false)
    await shot(`overview-${width}x${height}`)
    const camera = s.transform
    await blur(); await page.keyboard.press('y'); await settle()
    s = await state(); assert.equal(s.immersive, true); assert.deepEqual(s.transform, camera)
    const full = await page.locator('.graph-page').boundingBox()
    assert.deepEqual(full, { x: 0, y: 0, width, height })
    assert.equal(await page.evaluate(() => document.fullscreenElement), null)
    await shot(`immersive-${width}x${height}`)
    await page.keyboard.press('h'); await settle()
    assert.equal(await page.locator('.nebula-control').isVisible(), false)
    assert.deepEqual((await state()).transform, camera)
    await shot(`immersive-hidden-${width}x${height}`)
    await page.keyboard.press('y'); await settle()
    assert.deepEqual((await state()).transform, camera)
    await page.keyboard.press('h'); await settle()
    assert.equal(await page.locator('.nebula-control').isVisible(), true)
    assert.deepEqual((await state()).transform, camera)
    check(`${width}×${height} P0 边缘对齐、完整全览、Y/H 交叉及精确相机往返`, { bounds, camera })
  }

  await page.setViewportSize({ width: 1600, height: 900 }); await settle()
  const search = page.getByPlaceholder('输入岗位或技能...')
  await search.fill('python'); await settle()
  const before = (await state()).transform
  await search.press('Enter'); await settle()
  let s = await state()
  assert.equal(s.search.count, 87); assert.equal(s.search.index, 0); assert.equal(s.selectedId, 'skill:python')
  assert.equal(s.transform.scale, before.scale)
  assert.deepEqual(s.direct, { dataDegree: 222, typeFiltered: 222, drawable: 222, submitted: 222, intersecting: s.direct.intersecting })
  await shot('search-python-1600x900')
  await search.press('Enter'); await settle(); assert.equal((await state()).search.index, 1)
  await search.press('Shift+Enter'); await settle(); assert.equal((await state()).search.index, 0)
  await page.getByRole('button', { name: '上一个搜索结果' }).click(); await settle(); assert.equal((await state()).search.index, 86)
  await page.getByRole('button', { name: '下一个搜索结果' }).click(); await settle(); assert.equal((await state()).search.index, 0)
  check('真实 Python 87 项搜索、Enter/Shift+Enter、前后按钮循环，222 条真实直连')
  await page.locator('.nebula-filters button').filter({ hasText: '岗位' }).click(); await settle()
  assert.deepEqual((await state()).direct, { dataDegree: 222, typeFiltered: 0, drawable: 0, submitted: 0, intersecting: 0 })
  const filtered = await state()
  await blur(); await page.keyboard.press('h'); await page.keyboard.press('y'); await settle()
  await page.keyboard.press('h'); await page.keyboard.press('y'); await settle()
  for (const prop of ['selectedId', 'search', 'activeKinds', 'transform', 'direct']) assert.deepEqual((await state())[prop], filtered[prop])
  await page.locator('.nebula-filters button').filter({ hasText: '岗位' }).click(); await settle()
  await search.press('Enter'); await settle()
  check('隐藏岗位后真实度数仍 222、可绘制直连为 0，Y/H 保留非默认筛选')
  await blur()
  await page.keyboard.down('h'); await page.keyboard.down('h'); await settle()
  assert.equal((await state()).panelsHidden, true)
  await page.keyboard.up('h'); await page.keyboard.press('h'); await settle()
  assert.equal((await state()).panelsHidden, false)
  const selected = await state()
  await page.keyboard.press('h'); await settle()
  assert.equal(await page.locator('.nebula-control').isVisible(), false)
  assert.equal(await page.locator('.nebula-detail').isVisible(), false)
  await page.keyboard.press('y'); await settle(); await page.keyboard.press('h'); await settle()
  assert.equal(await page.locator('.nebula-detail').isVisible(), true)
  assert.equal(await search.inputValue(), 'python')
  await page.keyboard.press('y'); await settle()
  s = await state()
  for (const prop of ['selectedId', 'search', 'activeKinds', 'transform', 'direct']) assert.deepEqual(s[prop], selected[prop])
  check('已选中时双面板显隐与沉浸交叉保留搜索、筛选、相机及高亮')

  const original = s.transform
  await page.getByRole('button', { name: '查看全部关联', exact: true }).click(); await settle()
  s = await state(); assert.equal(s.lastFit.outside, 0); assert.equal(s.lastFit.points, 223); assert.equal(s.savedView, true)
  await shot('connections-python-1600x900')
  await page.getByRole('button', { name: '查看全部关联', exact: true }).click(); await settle()
  await page.getByRole('button', { name: '返回原视角', exact: true }).click(); await settle()
  assert.deepEqual((await state()).transform, original)
  await page.getByRole('button', { name: '关闭详情' }).click(); await settle()
  assert.deepEqual((await state()).transform, original)
  check('主动完整关联 223 节点全入视野、重复查看与返回/关闭详情保持原视角')

  // Derive a target from the real API and deterministic projection, then use
  // actual mouse input; never call component event handlers through evaluate.
  const data = (await (await context.request.get(base + 'api/graph/data?year=2026&focusJob=all')).json()).data
  const positions = await buildRelationLayout(data.nodes, data.edges)
  await search.fill('python'); await search.press('Enter'); await settle()
  await blur()
  const canvas = page.locator('canvas')
  const box = await canvas.boundingBox()
  const current = (await state()).transform
  const python = positions.get('skill:python')
  const target = { x: box.x + box.width / 2 + (python.x + current.x) * current.scale, y: box.y + box.height / 2 + (python.y + current.y) * current.scale }
  await page.mouse.move(target.x, target.y)
  const zoomBefore = (await state()).transform.scale
  for (let i = 0; i < 24; i++) { await page.mouse.wheel(0, -120); await page.waitForTimeout(35) }
  await settle()
  assert.ok((await state()).transform.scale > zoomBefore)
  const clickCamera = (await state()).transform
  await page.getByRole('button', { name: '关闭详情' }).click(); await settle()
  await page.mouse.click(target.x, target.y); await settle()
  assert.ok((await state()).selectedId)
  assert.deepEqual((await state()).transform, clickCamera)
  await page.mouse.click(box.x + 10, box.y + box.height - 10); await settle()
  assert.equal((await state()).selectedId, null)
  assert.deepEqual((await state()).transform, clickCamera)
  const zoomed = (await state()).transform
  await page.setViewportSize({ width: 1280, height: 720 }); await settle()
  assert.deepEqual((await state()).transform, zoomed)
  await page.setViewportSize({ width: 1600, height: 900 }); await settle()
  await shot('zoom-1600x900')
  await page.mouse.move(box.x + 550, box.y + 500); await page.mouse.down()
  await page.mouse.move(box.x + 630, box.y + 530, { steps: 5 }); await page.mouse.up(); await settle()
  assert.notDeepEqual((await state()).transform, zoomed)
  check('真实滚轮缩放、节点/空白原位点击、近景 resize 保持相机、指针拖拽')

  await page.getByRole('button', { name: '重置视图', exact: true }).click(); await settle()
  assert.equal((await state()).lastFit.outside, 0)
  await page.locator('.nebula-filters button').filter({ hasText: '行业' }).click(); await settle()
  assert.equal((await state()).lastFit.points, 5388)
  await page.locator('.nebula-filters button').filter({ hasText: '岗位' }).click(); await settle()
  assert.equal((await state()).lastFit.points, 4671)
  await page.locator('.nebula-filters button').filter({ hasText: '技能' }).click(); await settle()
  assert.equal((await state()).lastFit.points, 0)
  for (const button of await page.locator('.nebula-filters button').all()) await button.click()
  await page.getByRole('button', { name: '刷新数据', exact: true }).click(); await graphReady()
  await page.setViewportSize({ width: 1280, height: 600 }); await settle()
  assert.equal((await state()).lastFit.outside, 0)
  await page.setViewportSize({ width: 390, height: 844 }); await settle()
  assert.equal((await state()).lastFit.outside, 0)
  await search.fill('python'); await search.press('Enter'); await settle()
  const narrowBefore = (await state()).transform
  assert.equal((await state()).selectedId, 'skill:python')
  await page.getByRole('button', { name: '查看全部关联', exact: true }).click(); await settle()
  const leftPanel = await page.locator('.nebula-control').boundingBox()
  const rightPanel = await page.locator('.nebula-detail').boundingBox()
  assert.ok(leftPanel.y + leftPanel.height <= rightPanel.y || rightPanel.y + rightPanel.height <= leftPanel.y, '窄屏左右面板不得相互遮挡')
  await page.getByRole('button', { name: '返回原视角', exact: true }).click(); await settle()
  assert.deepEqual((await state()).transform, narrowBefore)
  await shot('narrow-selected-390x844')
  await blur(); await page.keyboard.press('y'); await settle()
  assert.equal((await page.locator('.graph-page').boundingBox()).height, 844)
  await page.keyboard.press('h'); await settle(); await shot('narrow-immersive-hidden-390x844')
  await page.keyboard.press('h'); await page.keyboard.press('y'); await settle()
  await page.setViewportSize({ width: 1600, height: 900 }); await settle()
  check('筛选三类/全关闭、刷新、全览 resize、1280×600 与 390×844')

  await search.fill('yh'); await search.press('y'); await search.press('h'); await settle()
  assert.equal((await state()).immersive, false); assert.equal((await state()).panelsHidden, false)
  await blur()
  for (const modifier of ['Control', 'Alt', 'Meta', 'Shift']) {
    for (const letter of ['y', 'h']) await page.keyboard.press(`${modifier}+${letter}`)
  }
  await page.evaluate(() => {
    for (const key of ['h', 'y']) {
      window.dispatchEvent(new KeyboardEvent('keydown', { key, repeat: true, bubbles: true }))
      window.dispatchEvent(new KeyboardEvent('keydown', { key, isComposing: true, bubbles: true }))
      window.dispatchEvent(new CompositionEvent('compositionstart'))
      window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }))
      window.dispatchEvent(new CompositionEvent('compositionend'))
    }
  })
  assert.equal((await state()).immersive, false); assert.equal((await state()).panelsHidden, false)
  for (const kind of ['textarea', 'select', 'editable']) {
    await page.evaluate(kind => {
      const el = document.createElement(kind === 'editable' ? 'div' : kind)
      el.id = 'shortcut-input-fixture'
      if (kind === 'editable') el.contentEditable = 'true'
      document.body.append(el); el.focus()
    }, kind)
    try { await page.keyboard.press('y'); await page.keyboard.press('h'); assert.equal((await state()).immersive, false); assert.equal((await state()).panelsHidden, false) }
    finally { await page.evaluate(() => document.querySelector('#shortcut-input-fixture').remove()) }
  }
  check('输入框/textarea/select/contenteditable、修饰组合、repeat 与 IME 保护')

  await blur(); await page.keyboard.press('y'); await page.keyboard.press('h'); await settle()
  await page.evaluate(() => { location.hash = '#/jobs' }); await page.locator('.topbar').waitFor(); await settle()
  assert.equal(await page.locator('.app-shell--graph-immersive').count(), 0)
  assert.equal(await page.locator('.sidebar').isVisible(), true)
  for (const route of ['jobs', 'dashboard', 'analytics', 'evolution', 'resume', 'learning', 'resume-demo', 'collection']) {
    await page.evaluate(route => { location.hash = '#/' + route }, route)
    await page.waitForTimeout(500)
    assert.equal(await page.locator('.topbar').isVisible(), true)
    await page.keyboard.press('h'); await page.keyboard.press('y')
    assert.equal(await page.locator('.app-shell--graph-immersive').count(), 0)
  }
  await page.getByRole('button', { name: '退出登录', exact: true }).click(); await page.locator('.login-card').waitFor()
  await page.evaluate(() => { location.hash = '#/graph' }); await settle(); await page.locator('.login-card').waitFor()
  await page.locator('.chip').first().click(); await page.locator('.login-btn').click(); await graphReady()
  assert.equal((await state()).selectedId, null); assert.equal((await state()).panelsHidden, false); assert.equal((await state()).immersive, false)
  await blur(); await page.keyboard.press('h'); await settle(); assert.equal((await state()).panelsHidden, true)
  await page.keyboard.press('h'); await settle(); assert.equal((await state()).panelsHidden, false)
  check('离开沉浸页恢复外壳、八业务页顶栏/热键隔离、注销守卫及重入无重复监听')
  assert.deepEqual(results.errors, []); assert.deepEqual(results.writes, [])
  check('无浏览器 pageerror、无 API 写请求')
} catch (error) {
  results.failure = error.stack
  console.error(error)
  process.exitCode = 1
} finally {
  await writeFile(resolve(output, 'browser-results.json'), JSON.stringify(results, null, 2))
  await browser.close()
}
