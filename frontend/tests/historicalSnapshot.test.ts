import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { adaptSnapshot, validateBinding, visibleKnowledgeIds, sha256LF, loadHistoricalGraph } from '../src/graph/historicalSnapshot.ts'

const snapshot = JSON.parse(readFileSync(new URL('../../exchange/m3/graph.json', import.meta.url), 'utf8'))

test('历史快照复访复用已验证输入，显式刷新重读且失败后可重试', async t => {
  const graphText = readFileSync(new URL('../../exchange/m3/graph.json', import.meta.url), 'utf8')
  const layoutText = readFileSync(new URL('../../exchange/m3/overlays/p2-1-layout.json', import.meta.url), 'utf8')
  const previous = Object.getOwnPropertyDescriptor(globalThis, '__GRAPH_LAYOUT_SHA256_LF__')
  Object.defineProperty(globalThis, '__GRAPH_LAYOUT_SHA256_LF__', { configurable: true, value: await sha256LF(layoutText) })
  t.after(() => {
    if (previous) Object.defineProperty(globalThis, '__GRAPH_LAYOUT_SHA256_LF__', previous)
    else delete (globalThis as any).__GRAPH_LAYOUT_SHA256_LF__
  })
  let calls = 0, broken = false
  t.mock.method(globalThis, 'fetch', async (url: string) => {
    calls++
    return { ok: !broken, text: async () => url.endsWith('layout.json') ? layoutText : graphText }
  })
  const first = await loadHistoricalGraph(true)
  first.graph.nodes[0].label = 'changed-in-first-view'
  const second = await loadHistoricalGraph()
  assert.equal(calls, 2)
  assert.notEqual(second.graph.nodes[0].label, first.graph.nodes[0].label)
  broken = true
  await assert.rejects(loadHistoricalGraph(true))
  broken = false
  const recovered = await loadHistoricalGraph()
  assert.equal(calls, 6)
  assert.equal(recovered.graph.nodes.length, 7845)
})
test('摘要验证不支持普通 HTTP LAN 时明确报错，不悄悄跳过校验',async()=>{
  await assert.rejects(sha256LF('test',null),/localhost.*HTTPS/)
})
test('历史图适配完整保留身份、来源对象、原数组索引和真实 Python 直连', () => {
  const graph = adaptSnapshot(snapshot)
  assert.equal(graph.nodes.length, 7845); assert.equal(graph.edges.length, 11412)
  graph.nodes.forEach((n, i) => { assert.equal(n.id, snapshot.nodes[i].id); assert.equal(n.raw, snapshot.nodes[i]); assert.equal(n.sourceIndex, i) })
  graph.edges.forEach((e, i) => { assert.equal(e.raw, snapshot.edges[i]); assert.equal(e.sourceIndex, i); assert.equal(e.kind, snapshot.edges[i].type) })
  const direct = graph.edges.filter(e => e.source === 'skill:python' || e.target === 'skill:python')
  assert.equal(direct.length, 222)
  assert.notEqual(direct.length, snapshot.nodes.find(n => n.id === 'skill:python').job_count)
  assert.throws(() => adaptSnapshot({ ...snapshot, nodes: [...snapshot.nodes, snapshot.nodes[0]] }), /duplicate/i)
  assert.throws(() => adaptSnapshot({ ...snapshot, edges: [{ source:'missing', target:snapshot.nodes[0].id, type:'REQUIRES' }] }), /endpoint/i)
})
test('版本绑定兼容 LF/CRLF，输入或坐标产物身份不匹配则拒绝', async () => {
  const text = readFileSync(new URL('../../exchange/m3/graph.json', import.meta.url), 'utf8').replace(/\r\n/g, '\n')
  const bytes = new TextEncoder().encode(text)
  const hash = Buffer.from(await crypto.subtle.digest('SHA-256', bytes)).toString('hex')
  const graph = adaptSnapshot(snapshot)
  const artifact = { snapshot_sha256_lf:hash, nodes:graph.nodes.map(n => ({id:n.id, x:0, y:0, community:null, degree:0})), schema_version:'m3-p2-1-layout-v1' }
  await validateBinding(text.replace(/\n/g, '\r\n'), artifact, graph)
  await assert.rejects(validateBinding(text+' ', artifact, graph), /hash/i)
  await assert.rejects(validateBinding(text, {...artifact,nodes:artifact.nodes.slice(1)},graph), /identity/i)
})
test('层级只隐藏度一技能；选中、搜索和其全部直接邻接优先恢复', () => {
  const nodes = [{id:'leaf',kind:'skill'}, {id:'shared',kind:'skill'}, {id:'j',kind:'job'}] as any
  const meta = new Map([['leaf',{degree:1}],['shared',{degree:2}],['j',{degree:1}]])
  assert.deepEqual([...visibleKnowledgeIds(nodes, meta, .2, new Set())], ['shared','j'])
  assert.equal(visibleKnowledgeIds(nodes, meta, .2, new Set(['leaf'])).size,3)
  assert.equal(visibleKnowledgeIds(nodes, meta, 1.2, new Set()).size,3)
})
