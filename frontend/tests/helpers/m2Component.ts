import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parse, compileScript } from 'vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'

export function m2Component(overrides: Record<string, any> = {}) {
  const mounted: (() => any)[] = [], unmounted: (() => any)[] = [], intervals: (() => any)[] = [], calls: any[] = [], cleared: any[] = []
  const defaults: Record<string, any> = { getM2Sources: { sources: [{ source: 'boss', total: 10 }], total: 10, cohorts: [] }, getM2Runs: [] }
  const api = new Proxy({}, { get: (_, method: string) => async (...args: any[]) => {
    calls.push({ method, args }); const value = method in overrides ? overrides[method] : defaults[method]
    if (value instanceof Error) throw value
    return typeof value === 'function' ? value(...args) : value
  } })
  const filename = resolve(import.meta.dirname, '../../src/views/M2.vue')
  const compiled = compileScript(parse(readFileSync(filename, 'utf8')).descriptor, { id: 'm2-test' }).content
  const code = ts.transpileModule(compiled, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const module = { exports: {} as any }
  const require = (id: string) => {
    if (id === 'vue') return { ...vue, onMounted: (fn: () => any) => mounted.push(fn), onUnmounted: (fn: () => any) => unmounted.push(fn) }
    if (id === '../api/m2') return api
    throw new Error('Unexpected module ' + id)
  }
  new Function('require', 'module', 'exports', 'setInterval', 'clearInterval', code)(require, module, module.exports, (fn: () => any) => intervals.push(fn), (id: any) => cleared.push(id))
  const scope = vue.effectScope()
  const state = scope.run(() => module.exports.default.setup({}, { expose() {} }))
  return { state, calls, intervals, cleared, mounted: async () => { for (const fn of mounted) await fn() }, stop: () => { for (const fn of unmounted) fn(); scope.stop() } }
}
