import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { collectionComponent } from './helpers/collectionComponent.ts'
import type { CollectionTask } from '../src/api/collection.ts'

test('进入采集页只刷新，不准备浏览器或启动任务', async () => {
  const page = collectionComponent()
  try {
    await page.mounted()
    assert.ok(page.calls.some(call => call.method === 'getCollectionPlatforms'))
    assert.equal(page.calls.some(call => /^(prepareCollection|startCollection|getCollectionRecent)$/.test(call.method)), false)
  } finally { page.stop() }
})

test('切换平台丢弃旧城市与准备凭据，城市使用目标平台代码', async () => {
  const page = collectionComponent()
  try {
    await page.mounted()
    await page.state.prepareBrowser()
    page.state.configForm.platform = 'zhaopin'
    await nextTick()
    assert.deepEqual(page.state.configForm.cities, [])
    assert.equal(page.state.availableCities.value[0].code, '530')
    assert.equal(page.state.canStart.value, false)
  } finally { page.stop() }
})

test('准备公开页面后单独启动，启动不会再次自动准备，载荷限制一轮', async () => {
  const page = collectionComponent()
  try {
    await page.mounted()
    assert.equal(page.state.canStart.value, false)
    await page.state.prepareBrowser()
    assert.equal(page.state.canStart.value, true)
    await page.state.startTask()
    assert.equal(page.calls.filter(call => call.method === 'prepareCollection').length, 1)
    const payload = page.calls.find(call => call.method === 'startCollection')!.args[0]
    assert.equal(payload.mode, 'once')
    assert.equal(payload.keywords.length, 1)
    assert.equal(payload.cities.length, 1)
    assert.equal('cdp_endpoint' in payload, false)
  } finally { page.stop() }
})

test('已归档的浏览器等待任务允许重新准备和启动新任务，历史限制原因保留', async () => {
  const blocked: CollectionTask = {
    run_id: 'blocked-run', platform: 'boss', status: 'waiting_for_browser', mode: 'once',
    started_at: '2026-10-20T10:00:00', finished_at: '2026-10-20T10:00:01',
    stop_reason: 'verification_required', last_error: '请人工完成浏览器准备后重新启动',
    listed: null, detail_attempted: null, detail_obtained: null, complete: null,
    inserted: null, updated: null, skipped: null, rejected: null, failed: null,
  }
  let current = blocked
  const page = collectionComponent({
    getCollectionStatus: () => current,
    getCollectionHistory: { items: [blocked], total: 1 },
    startCollection: () => {
      current = { ...blocked, run_id: 'retry-run', status: 'preparing', finished_at: null, stop_reason: null, last_error: null }
      return { run_id: 'retry-run', status: 'preparing' }
    },
  })
  try {
    await page.mounted()
    assert.equal(page.state.busy.value, false)
    assert.equal(page.state.canStop.value, false)
    await page.state.prepareBrowser()
    assert.equal(page.state.canStart.value, true)
    await page.state.startTask()
    assert.equal(page.state.currentTask.value.run_id, 'retry-run')
    assert.equal(page.state.busy.value, true)
    assert.equal(page.calls.filter(call => call.method === 'prepareCollection').length, 1)
    assert.equal(page.calls.filter(call => call.method === 'startCollection').length, 1)
    assert.equal(page.calls.some(call => call.method === 'stopCollection'), false)
    assert.equal(page.state.history.value[0].status, 'waiting_for_browser')
    assert.equal(page.state.history.value[0].stop_reason, 'verification_required')
  } finally { page.stop() }
})

test('尚未归档的浏览器等待任务仍阻止重准备和新任务，允许停止', async () => {
  const page = collectionComponent({ getCollectionStatus: { run_id: 'waiting-run', status: 'waiting_for_browser', finished_at: null } })
  try {
    await page.mounted()
    assert.equal(page.state.busy.value, true)
    assert.equal(page.state.canStop.value, true)
    await page.state.prepareBrowser()
    await page.state.startTask()
    assert.equal(page.calls.some(call => /^(prepareCollection|startCollection)$/.test(call.method)), false)
  } finally { page.stop() }
})

test('需要人工登录、验证或正文受限时不能启动', async () => {
  for (const access_state of ['login_required', 'verification_required', 'content_limited', 'authenticated']) {
    const page = collectionComponent({ prepareCollection: { access_state, can_collect: false, message: access_state } })
    try {
      await page.mounted()
      await page.state.prepareBrowser()
      assert.equal(page.state.canStart.value, false)
      await page.state.startTask()
      assert.equal(page.calls.some(call => call.method === 'startCollection'), false)
    } finally { page.stop() }
  }
})

test('准备响应内标记正文受限时，即使顶层可采集也不能启动', async () => {
  const page = collectionComponent({ prepareCollection: { access_state: 'public_accessible', can_collect: true, cdp: { reachable: true, platform_access: { boss: { access_state: 'public_accessible', can_collect: true, content_limited: true } } } } })
  try {
    await page.mounted()
    await page.state.prepareBrowser()
    assert.equal(page.state.accessState.value, 'content_limited')
    assert.equal(page.state.canStart.value, false)
    assert.match(page.state.accessMessage.value, /正文.*受限/)
    assert.match(page.state.startHint.value, /正文.*受限/)
  } finally { page.stop() }
})

test('定时状态发现验证门禁时撤销旧准备结果，恢复后仍须重新准备', async () => {
  let access_state = 'public_accessible'
  const page = collectionComponent({ getCDPStatus: () => ({ reachable: true, platform_access: { boss: { access_state, can_collect: access_state === 'public_accessible' } } }) })
  try {
    await page.mounted()
    await page.state.prepareBrowser()
    assert.equal(page.state.canStart.value, true)
    access_state = 'verification_required'
    await page.state.refreshAll()
    assert.equal(page.state.accessState.value, 'verification_required')
    assert.equal(page.state.canStart.value, false)
    access_state = 'public_accessible'
    await page.state.refreshAll()
    assert.equal(page.state.canStart.value, false)
  } finally { page.stop() }
})

test('不可启动平台与错误城市代码不能提交任务', async () => {
  const page = collectionComponent()
  try {
    await page.mounted()
    await page.state.prepareBrowser()
    page.state.configForm.cities = [{ name: '北京', code: '530' }]
    await page.state.startTask()
    assert.equal(page.calls.some(call => call.method === 'startCollection'), false)
    page.state.configForm.platform = 'hn'
    await nextTick()
    await page.state.prepareBrowser()
    assert.equal(page.calls.filter(call => call.method === 'prepareCollection').length, 1)
  } finally { page.stop() }
})

test('历史details不冒充取得详情或完整JD，未知计数显示破折号', async () => {
  const page = collectionComponent({ getCollectionStatus: { run_id: 'old', status: 'completed', details: 99, new: 50, listed: null } })
  try {
    await page.mounted()
    assert.equal(page.state.formatNumber(null), '—')
    const items = page.state.progressItems.value
    assert.equal(items.find((item: any) => item.key === 'detail_obtained').value, '—')
    assert.equal(items.find((item: any) => item.key === 'complete').value, '—')
    assert.equal(items.find((item: any) => item.key === 'inserted').value, '—')
    assert.equal(page.state.formatNumber(0), '0')
  } finally { page.stop() }
})

test('数据库不可用时展示真实错误，平台统计不制造历史回退值', async () => {
  const page = collectionComponent({ getDatabaseStats: { available: false, error: 'connection refused', database_total: null, platform_counts: [] } })
  try {
    await page.mounted()
    assert.equal(page.state.databaseError.value, 'connection refused')
    assert.equal(page.state.formatNumber(page.state.stats.value.database_total), '—')
    assert.equal(page.state.platformStats.value.find((item: any) => item.platform === 'hn').count, null)
  } finally { page.stop() }
})

test('本轮结果只按run_id读取，切换任务读取失败会清空旧结果并显示错误', async () => {
  let run = 'one'
  const page = collectionComponent({ getCollectionStatus: () => ({ run_id: run, status: 'completed' }), getCollectionResults: (id: string) => {
    if (id === 'two') throw new Error('result unavailable')
    return [{ job_title: '本轮岗位', raw_text: '正文', outcome: 'inserted', jd_pool_id: 7 }]
  } })
  try {
    await page.mounted()
    assert.equal(page.state.results.value[0].job_title, '本轮岗位')
    run = 'two'
    await page.state.refreshAll()
    assert.equal(page.state.results.value.length, 0)
    assert.match(page.state.resultsError.value, /result unavailable/)
    assert.deepEqual(page.calls.filter(call => call.method === 'getCollectionResults').map(call => call.args[0]), ['one', 'two'])
  } finally { page.stop() }
})

test('数据库正文按id显式读取，授权失败不把事件摘要冒充完整库原文', async () => {
  const page = collectionComponent({ getCollectionRaw: new Error('local access disabled') })
  try {
    await page.mounted()
    await page.state.openRaw({ job_title: '岗位', jd_pool_id: 7, raw_text: '事件原文' })
    assert.match(page.state.rawError.value, /local access disabled/)
    assert.equal(page.state.rawRecord.value, null)
    assert.equal(page.calls.find(call => call.method === 'getCollectionRaw')!.args[0], 7)
  } finally { page.stop() }
})

test('查看历史结果不替换当前任务，本轮与历史分别读取', async () => {
  const page = collectionComponent({ getCollectionStatus: { run_id: 'current', status: 'completed' }, getCollectionResults: (id: string) => [{ job_title: id }] })
  try {
    await page.mounted()
    await page.state.openHistory({ run_id: 'history', status: 'completed', raw_log_tail: ['历史日志'] })
    assert.equal(page.state.currentTask.value.run_id, 'current')
    assert.equal(page.state.results.value[0].job_title, 'current')
    assert.equal(page.state.historyResults.value[0].job_title, 'history')
  } finally { page.stop() }
})

test('准备使用当前完整有界搜索配置，不提交采集或保存配置', async () => {
  const page = collectionComponent()
  try {
    await page.mounted()
    page.state.keyword.value = ' Java '
    page.state.configForm.detail_limit = 3
    await page.state.prepareBrowser()
    const call = page.calls.find(call => call.method === 'prepareCollection')!
    assert.deepEqual(call.args, [false, 'boss', { keywords: ['Java'], cities: [{ name: '北京', code: '101010100' }], pages: 1, detail_limit: 3, max_jobs: 5 }])
    assert.equal(page.calls.some(call => /^(startCollection|updateCollectionConfig)$/.test(call.method)), false)
  } finally { page.stop() }
})

test('无效配置明确提示且不请求浏览器准备', async () => {
  for (const config of [{ keywords: [] }, { cities: [{ name: '北京', code: '530' }] }, { pages: 2 }, { max_jobs: 6 }, { keywords: ['x'.repeat(81)] }]) {
    const page = collectionComponent()
    try {
      await page.mounted()
      Object.assign(page.state.configForm, config)
      await page.state.prepareBrowser()
      assert.equal(page.calls.some(call => call.method === 'prepareCollection'), false)
      assert.match(page.messages.join(' '), /配置|关键词|城市|上限/)
    } finally { page.stop() }
  }
})

test('关键词或城市变化立即撤销准备凭据，切回旧配置也不能复用', async () => {
  const page = collectionComponent()
  try {
    await page.mounted()
    await page.state.prepareBrowser()
    page.state.configForm.keywords[0] = 'Java'
    assert.equal(page.state.canStart.value, false)
    page.state.configForm.keywords[0] = 'Python'
    assert.equal(page.state.canStart.value, false)
    await page.state.prepareBrowser()
    page.state.configForm.cities[0].code = '530'
    page.state.configForm.cities[0].code = '101010100'
    assert.equal(page.state.canStart.value, false)
  } finally { page.stop() }
})

test('准备前发出的延迟状态响应不能覆盖新准备结果', async () => {
  for (const fails of [false, true]) {
    let respond!: (value: any) => void
    let reject!: (error: Error) => void
    let delayed = false
    const stale = new Promise((resolve, fail) => { respond = resolve; reject = fail })
    const page = collectionComponent({ getCDPStatus: () => delayed ? stale : { reachable: false } })
    try {
      await page.mounted()
      delayed = true
      const refresh = page.state.refreshAll()
      await page.state.prepareBrowser()
      if (fails) reject(new Error('stale connection error'))
      else respond({ reachable: true, platform_access: { boss: { access_state: 'page_error', can_collect: false, reason: 'no_access_evidence' } } })
      await refresh
      assert.equal(page.state.canStart.value, true)
      assert.equal(page.state.accessState.value, 'public_accessible')
      assert.equal(page.state.refreshErrors.value.length, 0)
    } finally { page.stop() }
  }
})

test('准备过程中只读刷新不发浏览器状态请求，准备完成后可再检查', async () => {
  let finish!: (value: any) => void
  const pending = new Promise(resolve => { finish = resolve })
  const page = collectionComponent({ prepareCollection: () => pending })
  try {
    await page.mounted()
    const before = page.calls.filter(call => call.method === 'getCDPStatus').length
    const prepare = page.state.prepareBrowser()
    await page.state.refreshAll()
    assert.equal(page.calls.filter(call => call.method === 'getCDPStatus').length, before)
    finish({ access_state: 'public_accessible', can_collect: true, message: '搜索页可访问', cdp: { reachable: true } })
    await prepare
    await page.state.refreshAll()
    assert.equal(page.calls.filter(call => call.method === 'getCDPStatus').length, before + 1)
  } finally { page.stop() }
})

test('本次准备提示优先于CDP诊断，限制原因也显示在启动提示', async () => {
  const page = collectionComponent({ prepareCollection: { access_state: 'page_error', can_collect: false, message: '搜索页尚未出现职位内容，请稍后重新检查', cdp: { reachable: true, platform_access: { boss: { access_state: 'page_error', can_collect: false, reason: 'no_access_evidence' } } } } })
  try {
    await page.mounted()
    await page.state.prepareBrowser()
    assert.match(page.state.accessMessage.value, /搜索页尚未出现职位内容/)
    assert.match(page.state.startHint.value, /搜索页尚未出现职位内容/)
  } finally { page.stop() }
})

test('后端明确无搜索结果可启动验证，正文受限仍禁止', async () => {
  for (const content_limited of [false, true]) {
    const page = collectionComponent({ prepareCollection: { access_state: 'empty_results', can_collect: true, content_limited, message: '当前搜索没有结果', cdp: { reachable: true } } })
    try {
      await page.mounted()
      await page.state.prepareBrowser()
      assert.equal(page.state.canStart.value, !content_limited)
    } finally { page.stop() }
  }
})

test('准备超时清除loading与旧CDP证据，可刷新并重新准备但不自动启动', async () => {
  let fail = false
  const page = collectionComponent({
    prepareCollection: () => {
      if (fail) throw new Error('timeout of 120000ms exceeded')
      return { access_state: 'public_accessible', can_collect: true, message: '公开可访问', cdp: { reachable: true } }
    },
    getCDPStatus: { reachable: true, platform_access: { boss: { access_state: 'public_accessible', can_collect: true } } },
  })
  try {
    await page.mounted()
    await page.state.prepareBrowser()
    fail = true
    await page.state.prepareBrowser()
    assert.equal(page.state.preparing.value, false)
    assert.equal(page.state.canStart.value, false)
    assert.match(page.state.accessMessage.value, /超时/)
    assert.match(page.state.startHint.value, /超时/)
    await page.state.refreshAll()
    assert.equal(page.state.canStart.value, false)
    fail = false
    await page.state.prepareBrowser()
    assert.equal(page.state.canStart.value, true)
    assert.equal(page.calls.some(call => call.method === 'startCollection'), false)
  } finally { page.stop() }
})

test('浏览器只给技术reason时展示中文诊断并保留技术详情', async () => {
  const page = collectionComponent({ getCDPStatus: { reachable: true, platform_access: { boss: { access_state: 'page_error', can_collect: false, reason: 'no_access_evidence' } } } })
  try {
    await page.mounted()
    assert.match(page.state.accessMessage.value, /页面|职位内容/)
    assert.match(page.state.accessMessage.value, /no_access_evidence/)
  } finally { page.stop() }
})

test('准备请求未完成时改变搜索配置，旧成功响应不能绑定到新配置', async () => {
  let finish!: (value: any) => void
  const page = collectionComponent({ prepareCollection: () => new Promise(resolve => { finish = resolve }) })
  try {
    await page.mounted()
    const prepare = page.state.prepareBrowser()
    page.state.keyword.value = 'Java'
    finish({ access_state: 'public_accessible', can_collect: true, message: 'Python页面可访问', cdp: { reachable: true } })
    await prepare
    assert.equal(page.state.canStart.value, false)
    assert.equal(page.state.preparation.value, null)
    assert.equal(page.state.preparing.value, false)
  } finally { page.stop() }
})

test('后台受限轮询不抹去最近准备失败的具体提示和搜索目标', async () => {
  const page = collectionComponent({
    prepareCollection: { access_state: 'page_error', can_collect: false, message: '已打开Python北京搜索页，尚未看到职位内容', target_url: 'https://www.zhipin.com/web/geek/job?query=Python&city=101010100', cdp: { reachable: true } },
    getCDPStatus: { reachable: true, platform_access: { boss: { access_state: 'page_error', can_collect: false, reason: 'no_access_evidence' } } },
  })
  try {
    await page.mounted()
    await page.state.prepareBrowser()
    await page.state.refreshAll()
    assert.match(page.state.accessMessage.value, /已打开Python北京搜索页/)
    assert.match(page.state.startHint.value, /已打开Python北京搜索页/)
    assert.equal(page.state.preparation.value.target_url, 'https://www.zhipin.com/web/geek/job?query=Python&city=101010100')
    assert.equal(page.state.canStart.value, false)
  } finally { page.stop() }
})

test('准备成功后的新门禁撤销凭据且展示新原因，保留搜索目标', async () => {
  let fail = false
  const page = collectionComponent({
    prepareCollection: { access_state: 'public_accessible', can_collect: true, message: '搜索页可访问', target_url: 'https://www.zhipin.com/web/geek/job?query=Python&city=101010100', cdp: { reachable: true } },
    getCDPStatus: () => { if (fail) throw new Error('connection refused'); return { reachable: true, platform_access: { boss: { access_state: 'verification_required', can_collect: false, reason: 'manual_verification_or_access_limit' } } } },
  })
  try {
    await page.mounted()
    await page.state.prepareBrowser()
    await page.state.refreshAll()
    assert.equal(page.state.canStart.value, false)
    assert.match(page.state.accessMessage.value, /人工验证/)
    assert.ok(page.state.preparation.value?.target_url)
    fail = true
    await page.state.refreshAll()
    assert.equal(page.state.canStart.value, false)
    assert.match(page.state.accessMessage.value, /浏览器检查失败/)
    assert.ok(page.state.preparation.value?.target_url)
  } finally { page.stop() }
})
