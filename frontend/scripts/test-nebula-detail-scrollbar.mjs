import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href)
const phase = process.argv.includes('--before') ? 'before' : 'after'
const base = 'http://127.0.0.1:18087/'
const output = resolve('../docs/review/assets/issue-26-p05-scrollbar')
await mkdir(output, { recursive: true })
// 排除 headless 的隐藏滚动条参数，截图必须反映组件自身样式。
const browser = await chromium.launch({ headless: true, channel: 'msedge', ignoreDefaultArgs: ['--hide-scrollbars'] })
const result = { phase, browser: browser.version(), base, errors: [], writes: [], cases: [] }
try {
  const context = await browser.newContext({ viewport: { width: 1600, height: 900 } })
  await context.route('**/api/**', route => {
    if (['GET', 'HEAD'].includes(route.request().method())) return route.continue()
    result.writes.push(route.request().method() + ' ' + route.request().url())
    return route.abort()
  })
  const page = await context.newPage()
  page.on('pageerror', error => result.errors.push(error.message))
  await page.goto(base + '?nebulaDebug=1#/graph')
  await page.locator('.chip').first().click()
  await page.locator('.login-btn').click()
  await page.waitForFunction(() => JSON.parse(document.querySelector('.nebula-page')?.dataset.nebula || '{}').lastFit?.points > 0)
  const data = (await (await context.request.get(base + 'api/graph/data?year=2026&focusJob=all')).json()).data
  const target = data.nodes.filter(node => node.kind === 'job').sort((a, b) => JSON.stringify(b).length - JSON.stringify(a).length)[0]
  const search = page.getByPlaceholder('输入岗位或技能...')
  await search.fill(target.label)
  await search.press('Enter')
  const state = () => page.locator('.nebula-page').evaluate(el => JSON.parse(el.dataset.nebula))
  for (let i = 1; (await state()).selectedId !== target.id && i < data.nodes.length; i++) await search.press('Enter')
  assert.equal((await state()).selectedId, target.id)
  result.target = { id: target.id, label: target.label }
  const panel = page.locator('.nebula-detail')
  const metrics = locator => locator.evaluate(el => {
    const css = getComputedStyle(el), bar = getComputedStyle(el, '::-webkit-scrollbar'), rect = el.getBoundingClientRect()
    return { rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }, overflowY: css.overflowY,
      scrollbarWidth: css.scrollbarWidth, webkitDisplay: bar.display, scrollTop: el.scrollTop,
      scrollHeight: el.scrollHeight, clientHeight: el.clientHeight, clientWidth: el.clientWidth }
  })
  const baseline = phase === 'after' ? JSON.parse(await readFile(resolve(output, 'before.json'), 'utf8')) : null
  for (const [width, height] of [[1600, 900], [390, 844]]) {
    await page.setViewportSize({ width, height }); await page.waitForTimeout(250)
    await panel.getByRole('button', { name: '关闭详情' }).focus()
    await page.keyboard.press('Home'); await page.waitForTimeout(200)
    const start = await metrics(panel)
    assert.ok(start.scrollHeight > start.clientHeight, '真实长内容必须溢出面板')
    assert.equal(start.overflowY, 'auto')
    const camera = (await state()).transform
    const left = await metrics(page.locator('.nebula-control'))
    const textHash = createHash('sha256').update(await panel.innerText()).digest('hex')
    await page.screenshot({ path: resolve(output, `${phase}-${width}x${height}-top.png`) })
    await page.mouse.move(start.rect.x + start.rect.width / 2, start.rect.y + start.rect.height / 2)
    await page.mouse.wheel(0, 180); await page.waitForTimeout(200)
    const wheel = await metrics(panel)
    assert.ok(wheel.scrollTop > start.scrollTop, '鼠标滚轮应滚动详情')
    for (let i = 0; i < 5; i++) await page.mouse.wheel(0, 8)
    await page.waitForTimeout(200)
    const smallDelta = await metrics(panel)
    assert.ok(smallDelta.scrollTop > wheel.scrollTop, '连续小增量 wheel 应滚动详情')
    await page.keyboard.press('End'); await page.waitForTimeout(250)
    const end = await metrics(panel)
    assert.ok(Math.abs(end.scrollHeight - end.clientHeight - end.scrollTop) <= 1, '键盘 End 应到达内容末尾')
    const last = await panel.locator('.detail-section').last().boundingBox()
    assert.ok(last.y >= end.rect.y && last.y + last.height <= end.rect.y + end.rect.height, '末尾内容应在面板内完整可见')
    await page.screenshot({ path: resolve(output, `${phase}-${width}x${height}-end.png`) })
    await page.keyboard.press('Home'); await page.waitForTimeout(250)
    assert.equal((await metrics(panel)).scrollTop, 0, '键盘 Home 应回到顶部')
    assert.deepEqual((await state()).transform, camera, '滚动详情不得缩放或平移画布')
    const row = { width, height, start, wheel: wheel.scrollTop, smallDelta: smallDelta.scrollTop, end, left, textHash, camera }
    result.cases.push(row)
    if (baseline) {
      const previous = baseline.cases.find(item => item.width === width)
      assert.deepEqual(start.rect, previous.start.rect, '详情外框尺寸和位置保持不变')
      assert.deepEqual(left, previous.left, '左侧面板保持不变')
      assert.equal(textHash, previous.textHash, '详情文字保持不变')
      assert.deepEqual(camera, previous.camera, '初始选中相机保持不变')
    }
  }
  assert.deepEqual(result.errors, []); assert.deepEqual(result.writes, [])
  for (const row of result.cases) {
    assert.equal(row.start.scrollbarWidth, 'none', '右侧可见滚动条应隐藏')
    assert.equal(row.start.webkitDisplay, 'none', 'Chromium 伪元素应隐藏')
  }
  result.passed = true
} catch (error) {
  result.failure = error.stack
  process.exitCode = 1
  console.error(error)
} finally {
  await writeFile(resolve(output, phase + '.json'), JSON.stringify(result, null, 2))
  await browser.close()
}
console.log(JSON.stringify(result))
