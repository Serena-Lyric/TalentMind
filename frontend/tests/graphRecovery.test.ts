import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate } from 'vue/compiler-sfc'
import * as vue from 'vue'
import ts from 'typescript'
import { graphComponent } from './helpers/graphComponent.ts'
import { adaptSnapshot } from '../src/graph/historicalSnapshot.ts'

const source = readFileSync(new URL('../src/components/GraphPanorama.vue', import.meta.url), 'utf8')
const template = compileTemplate({ source: parse(source).descriptor.template!.content, filename: 'GraphPanorama.vue', id: 'recovery-test' }).code
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
