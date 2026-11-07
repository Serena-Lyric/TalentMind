import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate } from 'vue/compiler-sfc'
import * as vue from 'vue'
import ts from 'typescript'
import { graphComponent } from './helpers/graphComponent.ts'
import { adaptSnapshot } from '../src/graph/historicalSnapshot.ts'

const source = readFileSync(new URL('../src/components/GraphPanorama.vue', import.meta.url), 'utf8')
const template = compileTemplate({ source: parse(source).descriptor.template!.content, filename: 'GraphPanorama.vue', id: 'recovery-test', compilerOptions: { hoistStatic: false } }).code
const module = { exports: {} as any }
new Function('require', 'module', 'exports', ts.transpileModule(template, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText)(() => ({ ...vue, resolveComponent: (name: string) => ({ name }), resolveDirective: () => ({}), withDirectives: (node: any) => node }), module, module.exports)
function elements(state: any) {
  const found: any[] = []
  function visit(node: any) {
    if (!node || typeof node !== 'object') return
    if (Array.isArray(node)) { node.forEach(visit); return }
    found.push(node)
    visit(typeof node.children?.default === 'function' ? node.children.default() : node.children)
  }
  visit(module.exports.render(vue.proxyRefs(state), []))
  return found
}
const text = (node: any): string => typeof node === 'string' ? node : Array.isArray(node) ? node.map(text).join('') : text(node?.children || '')

for (const [dataset, identity] of [
  ['delivery', `graphDataset=delivery&m2DeliveryRun=run%2Fwith%20space&m2Graph=${'a'.repeat(64)}`],
  ['real', `graphDataset=real&m2Run=legacy%2Frun&m2Graph=${'b'.repeat(64)}`],
  ['legacy', 'graphDataset=legacy'],
  ['default historical', ''],
] as const) {
  test(`五个视觉对照链接保留 ${dataset} 图谱身份、路径、hash 及无关查询参数`, t => {
    const search = `?${identity}&nebulaDebug=1&filter=A%26B&filter=%E4%B8%AD%E6%96%87&graphCamera=orbit&graphVisual=p1a2&graphStars=p25&graphSpace=node-field-v1&graphCompare=near`
    const current = new URL(`https://example.test/talentmind/app/${search}#/graph?selection=job%2F42`)
    const app = graphComponent(undefined, current.search, current.hash); t.after(app.stop)
    const links = elements(app.state).filter(node => node.type === 'a')
    const cases: [string, Record<string, string>][] = [
      ['P2.1视觉回退', { graphCamera: 'fixed', graphVisual: 'p21' }],
      ['P2.2固定投影', { graphCamera: 'fixed', graphVisual: 'p22' }],
      ['P2.3星点外观', { graphStars: 'p23' }],
      ['P2.4恒星外观', { graphStars: 'p24' }],
      ['P2.5知识星体', { graphSpace: 'legacy' }],
    ]
    for (const [label, changes] of cases) {
      const link = links.find(node => text(node) === label)
      assert.ok(link, label)
      const target = new URL(link.props.href, current)
      assert.equal(target.pathname, current.pathname, label)
      for (const key of new Set(current.searchParams.keys())) {
        assert.deepEqual(target.searchParams.getAll(key), key in changes ? [changes[key]] : current.searchParams.getAll(key), `${label}: ${key}`)
      }
      assert.equal(target.hash, current.hash, label)
      for (const [key, value] of Object.entries(changes)) assert.equal(target.searchParams.get(key), value, `${label}: ${key}`)
      assert.equal(target.searchParams.has('graphRenderer'), false, label)
    }
    assert.equal(app.location.search, current.search)
  })
}

test('新版研究边与历史关联沿用各自真实身份显示，不由当前页面模式改写', t => {
  const app = graphComponent(); t.after(app.stop)
  const graph = adaptSnapshot({ nodes: [{ id: 'research', type: 'job' }, { id: 'jd', type: 'job' }, { id: 'historical', type: 'job' }], edges: [
    { source: 'research', target: 'jd', type: 'RELATED_TO', relation: 'research_hypothesis', research_relation: { id: 'research-r1', state: 'proposed' } },
    { source: 'jd', target: 'historical', type: 'RELATED_TO' },
  ] })
  app.setGraph(graph.nodes.map(node => ({ ...node, point: { x: 0, y: 0 } })), graph.edges)
  app.state.selectedNode.value = graph.nodes[1]
  const labels = elements(app.state).filter(node => node.type === 'small').map(text)
  assert.ok(labels.some(label => label.startsWith('研究关联（假设，未人工审核）')))
  assert.ok(labels.some(label => label.startsWith('历史岗位关联')))
})

test('错误页重试保持原运行和摘要，渲染错误重载同一地址且无旧 Canvas 入口', async t => {
  const search = `?graphDataset=delivery&m2DeliveryRun=run&m2Graph=${'f'.repeat(64)}`
  const app = graphComponent(undefined, search); t.after(app.stop)
  app.state.loadError.value = '暂时不可用'
  const urls: string[] = []
  t.mock.method(globalThis, 'fetch', async (url: any) => { urls.push(String(url)); return { ok: false, status: 503 } as Response })
  let nodes = elements(app.state)
  assert.ok(!nodes.some(node => node.type === 'a' && String(node.props?.href).includes('graphRenderer=legacy')))
  const retry = nodes.find(node => node.type === 'button' && text(node) === '重试当前图谱')
  assert.ok(retry)
  await retry.props.onClick()
  assert.deepEqual(urls, [`/api/m2/delivery/runs/run/graph/manifest.json?snapshot=${'f'.repeat(64)}`])
  assert.ok(app.state.loadError.value)
  app.state.webglError.value = true
  nodes = elements(app.state)
  const reload = nodes.find(node => node.type === 'button' && text(node) === '重新加载当前页面')
  assert.ok(reload)
  reload.props.onClick()
  assert.equal(app.location.reloadCount, 1)
  assert.equal(app.location.search, search)
})
