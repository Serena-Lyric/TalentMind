import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { parse, compileScript } from 'vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'

// 执行真实 SFC setup；只隔离网络、挂载和 Canvas 端口，无 DOM 测试框架依赖。
export function graphComponent(experimental = true) {
  const filename = resolve(import.meta.dirname, '../../src/components/GraphPanorama.vue')
  const modules = new Map<string, any>()
  const load = (path: string, source?: string): any => {
    if (modules.has(path)) return modules.get(path).exports
    const module = { exports: {} as any }
    modules.set(path, module)
    const code = ts.transpileModule(source ?? readFileSync(path, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
    }).outputText
    const require = (id: string): any => {
      if (id === 'vue') return { ...vue, onMounted() {}, onUnmounted() {} }
      if (id === '@element-plus/icons-vue') return {}
      if (id === 'element-plus') return { ElMessage: { info() {}, warning() {}, error() {} } }
      if (id === '../api/graph') return { getGraphData: async () => { throw new Error('Network disabled in component test') } }
      if (id.startsWith('.')) return load(resolve(dirname(path), id + '.ts'))
      return createRequire(path)(id)
    }
    new Function('require', 'module', 'exports', 'window', code)(require, module, module.exports, {
      location: { search: experimental ? '?nebula=experimental&nebulaDebug=1' : '?nebulaDebug=1' }, devicePixelRatio: 1,
    })
    return module.exports
  }
  const descriptor = parse(readFileSync(filename, 'utf8')).descriptor
  const component = load(filename, compileScript(descriptor, { id: 'graph-test' }).content).default
  const scope = vue.effectScope()
  const state = scope.run(() => component.setup({}, { expose() {} }))
  const labels: string[] = []
  const context = new Proxy({ measureText: (value: string) => ({ width: value.length * 10 }), fillText: (value: string) => labels.push(value) }, {
    get: (target: any, key) => key in target ? target[key] : () => {},
  })
  state.canvasRef.value = {
    clientWidth: 1200, clientHeight: 800, style: {}, getContext: () => context,
    getBoundingClientRect: () => ({ left: 0, top: 0 }),
  }
  state.canvasWrapRef.value = { clientWidth: 1200, clientHeight: 800 }
  state.rootRef.value = { dataset: {}, querySelectorAll: () => [] }
  const setGraph = (nodes: any[], edges: any[]) => {
    state.graphData.value = { nodes, edges, stats: { totalNodes: nodes.length, totalEdges: edges.length, added: 0, removed: 0, changed: 0 } }
    state.drawNodes.value = nodes
    state.nodeById.clear()
    nodes.forEach(node => state.nodeById.set(node.id, node))
  }
  return { state, setGraph, labels, stop: () => scope.stop(), debug: () => JSON.parse(state.rootRef.value.dataset.nebula) }
}
