import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'

export function m2Component(overrides: Record<string, any> = {}) {
  const navigations:string[] = []
  const downloads:any[] = []
  const mounted: (() => any)[] = [], unmounted: (() => any)[] = [], intervals: (() => any)[] = [], calls: any[] = [], cleared: any[] = []
  const defaults: Record<string, any> = { getDeliveryInputs:{items:[],total:0}, getDeliveryRuns:[], getM2Runs:[] }
  const api = new Proxy({}, { get: (_, method: string) => async (...args: any[]) => {
    calls.push({ method, args }); const value = method in overrides ? overrides[method] : defaults[method]
    if (value instanceof Error) throw value
    return typeof value === 'function' ? value(...args) : value
  } })
  const filename = resolve(import.meta.dirname, '../../src/views/M2.vue')
  const descriptor = parse(readFileSync(filename, 'utf8')).descriptor
  const compiled = compileScript(descriptor, { id: 'm2-test' }).content
  const code = ts.transpileModule(compiled, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const module = { exports: {} as any }
  const require = (id: string) => {
    if (id === 'vue') return { ...vue, onMounted: (fn: () => any) => mounted.push(fn), onUnmounted: (fn: () => any) => unmounted.push(fn), resolveComponent:(name:string)=>({name}),resolveDirective:()=>({}),withDirectives:(node:any)=>node }
    if (id === '../api/m2') return api
    if (id === 'vue-router') return {useRoute:()=>({query:{}})}
    throw new Error('Unexpected module ' + id)
  }
  const document = {createElement: () => ({href:'',download:'',click(){downloads.push(this)}})}
  const url = {createObjectURL:()=> 'blob:fixture', revokeObjectURL:()=> undefined}
  new Function('require', 'module', 'exports', 'setInterval', 'clearInterval', 'window', 'document', 'URL', code)(require, module, module.exports, (fn: () => any) => intervals.push(fn), (id: any) => cleared.push(id), {location:{assign:(url:string)=>navigations.push(url)}}, document, url)
  const scope = vue.effectScope()
  const state = scope.run(() => module.exports.default.setup({}, { expose() {} }))
  const template = compileTemplate({source:descriptor.template!.content,filename,id:'m2-test',transformAssetUrls:false}).code
  const renderModule={exports:{} as any}
  new Function('require','module','exports',ts.transpileModule(template,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(require,renderModule,renderModule.exports)
  const elements=(name:string)=>{const found:any[]=[];const visit=(node:any)=>{if(!node||typeof node!=='object')return;if(Array.isArray(node)){node.forEach(visit);return}if((node.type?.name||node.type)===name)found.push(node);if(node.type?.name==='el-table')return;visit(typeof node.children?.default==='function'?node.children.default():node.children)};visit(renderModule.exports.render(vue.proxyRefs(state),[]));return found}
  return { state, elements, calls, intervals, cleared, navigations, downloads, mounted: async () => { for (const fn of mounted) await fn() }, stop: () => { for (const fn of unmounted) fn(); scope.stop() } }
}
