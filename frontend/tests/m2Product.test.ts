import test from 'node:test'
import assert from 'node:assert/strict'
import { m2Component } from './helpers/m2Component.ts'

const draft = { run_id: 'a'.repeat(32), status: 'queued', items: [], versions: { revision: 'v1' }, summary: { input_total: 5, stage_complete: 0, finalized: 0, final_counts: {} } }

test('候选图只从当前已完成任务显式生成，错误不导航', async () => {
  const page = m2Component({ generateM2Graph: new Error('graph version mismatch') })
  try {
    page.state.selected.value = draft
    await page.state.openGraph()
    assert.equal(page.calls.length, 0)
    page.state.selected.value = { ...draft, status: 'completed_with_issues' }
    await page.state.openGraph()
    assert.deepEqual(page.calls[0], { method: 'generateM2Graph', args: [draft.run_id] })
    assert.match(page.state.error.value, /version mismatch/)
  } finally { page.stop() }
})

test('生成候选图期间的新建和重放会使旧导航失效', async () => {
  let complete!: (value:any) => void
  const page = m2Component({ generateM2Graph: () => new Promise(resolve => { complete=resolve }), createM2Run:new Promise(() => {}) })
  try {
    page.state.selected.value={...draft,status:'completed_with_issues'}
    page.state.selectedId.value=draft.run_id
    const graph=page.state.openGraph()
    void page.state.createRun()
    complete({run_id:draft.run_id,url:'/old-graph'})
    await graph
    assert.equal(page.state.error.value,'')
    assert.deepEqual(page.navigations,[])
  } finally { page.stop() }
})

test('进入和轮询不启动，创建只冻结；开始和停止必须显式操作', async () => {
  const page = m2Component({ createM2Run: draft, getM2Run: draft, startM2Run: { ...draft, status: 'running' }, stopM2Run: { ...draft, status: 'stopping' } })
  try {
    await page.mounted(); for (const poll of page.intervals) await poll()
    assert.equal(page.calls.some(c => /start|create/i.test(c.method)), false)
    await page.state.createRun()
    assert.equal(page.state.selected.value.status, 'queued')
    assert.equal(page.calls.some(c => c.method === 'startM2Run'), false)
    await page.state.startRun(); await page.state.stopRun()
    assert.deepEqual(page.calls.find(c => c.method === 'startM2Run').args, [draft.run_id])
    assert.deepEqual(page.calls.find(c => c.method === 'stopM2Run').args, [draft.run_id])
    assert.equal(page.calls.some(c => /Collection/.test(c.method)), false)
  } finally { page.stop() }
  assert.ok(page.cleared.length)
})

test('历史成员模式不携带范围过滤，输入上限和反向ID范围阻止创建', async () => {
  const page = m2Component({ createM2Run: draft })
  try {
    await page.mounted()
    page.state.idMin.value = 9; page.state.idMax.value = 2
    await page.state.createRun()
    assert.equal(page.calls.some(c => c.method === 'createM2Run'), false)
    page.state.cohort.value = 'main120'
    await page.state.createRun()
    assert.deepEqual(page.calls.find(c => c.method === 'createM2Run').args[0], { cohort: 'main120', limit: 120, sources: [], id_min: null, id_max: null })
  } finally { page.stop() }
})

test('选择新任务后旧任务和旧JD响应不能覆盖', async () => {
  let finish!: (v: any) => void, finishItem!: (v: any) => void
  const page = m2Component({ getM2Run: (id: string) => id === 'old' ? new Promise(resolve => { finish = resolve }) : { ...draft, run_id: id }, getM2Item: (_id: string, ordinal: number) => ordinal === 1 ? new Promise(resolve => { finishItem = resolve }) : { ordinal } })
  try {
    await page.mounted()
    const first = page.state.selectRun('old'); await page.state.selectRun('new')
    finish({ ...draft, run_id: 'old' }); await first
    assert.equal(page.state.selected.value.run_id, 'new')
    const item = page.state.inspectItem(1); await page.state.inspectItem(2)
    finishItem({ ordinal: 1 }); await item
    assert.equal(page.state.detail.value.ordinal, 2)
  } finally { page.stop() }
})

test('失败显示原因且不补造结果，版本重放生成待执行任务', async () => {
  const page = m2Component({ getM2Run: draft, getM2Item: new Error('本地原文门禁拒绝'), replayM2Run: { ...draft, run_id: 'replay' } })
  try {
    await page.mounted(); await page.state.selectRun(draft.run_id)
    await page.state.inspectItem(1)
    assert.equal(page.state.detail.value, null)
    assert.match(page.state.error.value, /门禁拒绝/)
    page.state.revision.value = 'v2'
    await page.state.replayRun()
    assert.equal(page.state.selected.value.run_id, 'replay')
    assert.deepEqual(page.calls.find(c => c.method === 'replayM2Run').args, [draft.run_id, 'v2'])
    assert.equal(page.calls.some(c => c.method === 'startM2Run'), false)
  } finally { page.stop() }
})

test('冻结创建较慢时，不能覆盖用户后来选择的历史任务', async () => {
  let finish!: (v: any) => void
  const page = m2Component({ createM2Run: () => new Promise(resolve => { finish = resolve }), getM2Run: { ...draft, run_id: 'chosen' } })
  try {
    await page.mounted()
    const pending = page.state.createRun()
    await page.state.selectRun('chosen')
    finish(draft); await pending
    assert.equal(page.state.selected.value.run_id, 'chosen')
  } finally { page.stop() }
})

test('待审身份显示为独立标签并进入报告汇总', async () => {
  const pendingRun = {
    ...draft,
    status: 'completed_with_issues',
    summary: {
      input_total: 1, finalized: 1, stage_complete: 1,
      final_counts: { needs_review: 1 },
      identity: { verified: 0, pending: 1, unknown: 0 },
      content: { eligible: 1, ineligible: 0, unknown: 0 },
    },
    items: [{
      ordinal: 1, jd_id: 101, source: 'zhaopin', title: 'Python 工程师',
      identity_status: 'pending', content_eligible: true,
      identity_evidence: { binding_policy: 'zhaopin-dom-panel-v1' },
      final_status: 'needs_review', evidence: { matched: 0, invalid: 0 },
      stages: {},
    }],
  }
  const page = m2Component({ getM2Runs: [pendingRun], getM2Run: pendingRun })
  try {
    await page.mounted()
    page.state.selected.value = pendingRun
    assert.equal(page.state.identityText('pending'), '身份待审')
    assert.equal(page.state.identityText('verified'), '身份已验证')
    assert.equal(page.state.identityText('unknown'), '身份未知')
    assert.equal(page.state.stageMetrics.value.identity.pending, 1)
    assert.equal(page.state.stageMetrics.value.content.eligible, 1)
  } finally { page.stop() }
})

test('人工审核绑定机器摘要并可读取历史和导出', async () => {
  const completed = {
    ...draft,
    status: 'completed_with_issues',
    summary: {
      ...draft.summary,
      review: { total_items: 1, reviewed_items: 1, unreviewed_items: 0, accepted: 1, rejected: 0, needs_followup: 0 },
    },
  }
  const detail:any = {
    ordinal: 1, jd_id: 101, source: 'boss', title: '后端工程师', final_status: 'needs_review',
    evidence: { matched: 1, invalid: 0 }, machine_sha256: 'a'.repeat(64),
    human_review: null, reviews: [], warnings: [], input_sha256: 'b'.repeat(64),
    input: { id: 101, raw_text: '负责软件开发' },
    stages: {
      b2: { status: 'saved', result: { body: {
        statements: [
          { id: 's1', state: 'required', relation: null, condition: null, skills: [{ name: 'python' }], evidence: { quote: '必须掌握 Python' } },
          { id: 's2', state: 'uncertain', relation: null, condition: null, skills: [{ name: '未登记框架' }], evidence: { quote: '了解未登记框架' } },
        ],
      } } },
      b22: { status: 'saved', result: { body: {
        skills: [{ id: 'k1', canonical: 'python', statement_ids: ['s1'] }],
        original_semantics: { statements: [{ id: 's1', state: 'required', relation: null, condition: null, evidence: { quote: '必须掌握 Python' } }] },
      } } },
      b3: { status: 'saved', result: { body: {
        candidates: [{ family_id: 'software_engineering', clues: [{ evidence: { quote: '负责软件开发' } }] }],
      } } },
    },
  }
  const event = {
    review_id: 1, schema_version: 'm2-human-review-1', run_id: completed.run_id,
    ordinal: 1, jd_id: 101, input_sha256: 'b'.repeat(64), machine_sha256: 'a'.repeat(64),
    machine_status: 'needs_review', decision: 'accepted', reviewer: '审核员',
    note: '职责证据明确', reviewed_at: '2026-10-22T10:00:00+00:00',
    sha256: 'c'.repeat(64), formal_truth_claim: false,
  }
  const page = m2Component({
    getM2Run: completed,
    getM2Item: detail,
    reviewM2Item: { ...detail, human_review: event, reviews: [event] },
    exportM2Reviews: { schema_version: 'm2-human-review-export-1', reviews: [event], items: [] },
  })
  try {
    await page.mounted()
    page.state.selected.value = completed
    page.state.selectedId.value = completed.run_id
    await page.state.inspectItem(1)
    page.state.reviewDecision.value = 'accepted'
    page.state.reviewReviewer.value = '审核员'
    page.state.reviewNote.value = '职责证据明确'
    if (page.state.reviewScopeStatus) page.state.reviewScopeStatus.value = 'in_scope'
    if (page.state.humanStatementStates) page.state.humanStatementStates.s1 = 'required'
    if (page.state.humanStatementStates) page.state.humanStatementStates.s2 = 'not_skill'
    if (page.state.humanB3Decisions) page.state.humanB3Decisions.software_engineering = 'accepted'
    await page.state.submitReview()

    assert.deepEqual(page.calls.find(c => c.method === 'reviewM2Item').args, [
      completed.run_id, 1,
      {
        decision: 'accepted', reviewer: '审核员', note: '职责证据明确', machine_sha256: 'a'.repeat(64),
        annotations: {
          b1_scope: { scope_status: 'in_scope', note: '' },
          b2_statements: [
            { statement_id: 's1', skill_ids: ['k1'], human_state: 'required', note: '' },
            { statement_id: 's2', skill_ids: [], human_state: 'not_skill', note: '' },
          ],
          b3_categories: [{ family_id: 'software_engineering', human_decision: 'accepted', note: '' }],
        },
      },
    ])
    assert.equal(page.state.detail.value.human_review.decision, 'accepted')
    assert.equal(page.state.reviewDecision.value, '')
    await page.state.downloadReviews()
    assert.equal(page.downloads[0].download, `m2-reviews-${completed.run_id}.json`)
  } finally { page.stop() }
})

test('审核返回不能覆盖后来打开的 JD', async () => {
  let finishReview!: (value:any) => void
  const completed = { ...draft, status: 'completed_with_issues' }
  const first:any = {
    ordinal: 1, jd_id: 101, title: '岗位一', final_status: 'needs_review',
    machine_sha256: 'a'.repeat(64), reviews: [], stages: {}, evidence: { matched: 0, invalid: 0 },
  }
  const second:any = { ...first, ordinal: 2, jd_id: 102, title: '岗位二', machine_sha256: 'd'.repeat(64) }
  const page = m2Component({
    getM2Run: completed,
    getM2Item: (_id: string, ordinal: number) => ordinal === 1 ? first : second,
    reviewM2Item: () => new Promise(resolve => { finishReview = resolve }),
  })
  try {
    await page.mounted()
    page.state.selected.value = completed
    page.state.selectedId.value = completed.run_id
    await page.state.inspectItem(1)
    page.state.reviewDecision.value = 'accepted'
    page.state.reviewReviewer.value = '审核员'
    const pending = page.state.submitReview()
    await page.state.inspectItem(2)
    finishReview({ ...first, human_review: { decision: 'accepted' } })
    await pending
    assert.equal(page.state.detail.value.ordinal, 2)
    assert.equal(page.state.detail.value.human_review, undefined)
  } finally { page.stop() }
})

test('重新打开 JD 显示跨事件有效标签和冲突，不把旧标签自动重提', async () => {
  const completed = { ...draft, status: 'completed_with_issues' }
  const provenance = (reviewId: number, reviewer: string) => ({
    review_id: reviewId, event_sha256: String(reviewId).repeat(64).slice(0, 64),
    reviewer, reviewed_at: `2026-10-22T10:0${reviewId}:00+00:00`,
    machine_sha256: 'a'.repeat(64), input_sha256: 'b'.repeat(64),
  })
  const detail:any = {
    ordinal: 1, jd_id: 101, title: '跨事件审核', final_status: 'needs_review',
    machine_sha256: 'a'.repeat(64), input_sha256: 'b'.repeat(64), warnings: [],
    evidence: { matched: 1, invalid: 0 },
    stages: {
      b2: { status: 'saved', result: { body: { statements: [
        { id: 's1', state: 'required', relation: null, condition: null, skills: [{ name: 'python' }], evidence: { quote: '必须掌握 Python' } },
      ] } } },
      b22: { status: 'saved', result: { body: { skills: [{ id: 'k1', canonical: 'python', statement_ids: ['s1'] }] } } },
      b3: { status: 'saved', result: { body: { candidates: [
        { family_id: 'software_engineering', clues: [{ evidence: { quote: '负责软件开发' } }] },
      ] } } },
    },
    human_review: { decision: 'needs_followup', review_id: 3 },
    reviews: [{ review_id: 1 }, { review_id: 2 }, { review_id: 3 }],
    human_effective: {
      schema_version: 'm2-human-effective-1',
      b1_scope: { scope_status: 'in_scope', note: '范围', provenance: provenance(1, '范围审核员') },
      b2_statements: [{
        statement_id: 's1', skill_ids: ['k1'], human_state: 'required', note: '技能',
        provenance: provenance(2, '技能审核员'),
      }],
      b3_categories: [{
        family_id: 'software_engineering', human_decision: 'accepted', note: '大类',
        provenance: provenance(3, '大类审核员'),
      }],
      conflicts: [{
        dimension: 'b2_statement', key: 's1',
        previous: {
          statement_id: 's1', skill_ids: ['k1'], human_state: 'uncertain', note: '旧值',
          provenance: provenance(2, '技能审核员'),
        },
        effective: {
          statement_id: 's1', skill_ids: ['k1'], human_state: 'required', note: '技能',
          provenance: provenance(3, '技能审核员'),
        },
      }],
      event_count: 3, annotation_event_count: 3, legacy_review_count: 0, has_dimension_truth: true,
    },
  }
  const page = m2Component({ getM2Run: completed, getM2Item: detail, reviewM2Item: { ...detail, human_review: { decision: 'needs_followup', review_id: 4 } } })
  try {
    await page.mounted()
    page.state.selected.value = completed
    page.state.selectedId.value = completed.run_id
    await page.state.inspectItem(1)
    assert.equal(page.state.effectiveB2Map?.value.get('s1')?.human_state, 'required')
    assert.equal(page.state.effectiveB2Map?.value.get('s1')?.provenance.reviewer, '技能审核员')
    assert.equal(page.state.effectiveB3Map?.value.get('software_engineering')?.human_decision, 'accepted')
    assert.equal(page.state.detail.value.human_effective.conflicts.length, 1)
    assert.equal(page.state.reviewScopeStatus.value, '')
    assert.equal(page.state.humanStatementStates.s1, undefined)
    assert.equal(page.state.humanB3Decisions.software_engineering, undefined)

    page.state.reviewDecision.value = 'needs_followup'
    page.state.reviewReviewer.value = '新增审核员'
    page.state.humanStatementStates.s1 = 'preferred'
    await page.state.submitReview()
    const payload = page.calls.find(c => c.method === 'reviewM2Item').args[2]
    assert.deepEqual(payload.annotations, {
      b1_scope: null,
      b2_statements: [{ statement_id: 's1', skill_ids: ['k1'], human_state: 'preferred', note: '' }],
      b3_categories: [],
    })
  } finally { page.stop() }
})

test('延迟导出使用发起时的 run_id 命名结果', async () => {
  let finishExport!: (value:any) => void
  const page = m2Component({
    exportM2Reviews: () => new Promise(resolve => { finishExport = resolve }),
  })
  try {
    page.state.selected.value = { ...draft, run_id: 'a'.repeat(32) }
    page.state.selectedId.value = 'a'.repeat(32)
    const pending = page.state.downloadReviews()
    page.state.selected.value = { ...draft, run_id: 'b'.repeat(32) }
    page.state.selectedId.value = 'b'.repeat(32)
    finishExport({ reviews: [] })
    await pending
    assert.equal(page.downloads[0].download, `m2-reviews-${'a'.repeat(32)}.json`)
  } finally { page.stop() }
})
