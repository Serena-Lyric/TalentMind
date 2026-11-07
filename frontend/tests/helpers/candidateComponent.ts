import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'

export function candidateComponent(overrides: Record<string, any> = {}) {
  const calls: {method:string;args:any[]}[] = [], unmounted: (()=>void)[] = []
  const api = new Proxy({}, {get: (_, method:string) => async (...args:any[]) => {
    calls.push({method,args}); const value=overrides[method]
    if(value instanceof Error) throw value
    return typeof value==='function'?value(...args):value
  }})
  const filename=resolve(import.meta.dirname,'../../src/components/CandidateMaintenance.vue')
  const descriptor=parse(readFileSync(filename,'utf8')).descriptor
  const compiled=compileScript(descriptor,{id:'candidate-test'}).content
  const code=ts.transpileModule(compiled,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
  const module={exports:{} as any}
  const require=(id:string)=>{
    if(id==='vue') return {...vue,onUnmounted:(fn:()=>void)=>unmounted.push(fn)}
    if(id==='../api/candidates') return api
    throw Error('Unexpected module '+id)
  }
  let nextId=0
  new Function('require','module','exports','crypto',code)(require,module,module.exports,{randomUUID:()=>`00000000-0000-4000-8000-${String(++nextId).padStart(12,'0')}`})
  const scope=vue.effectScope()
  const state=scope.run(()=>module.exports.default.setup({}, {expose(){}}))
  const template=compileTemplate({source:descriptor.template!.content,filename,id:'candidate-test',compilerOptions:{hoistStatic:false}}).code
  const rendered={exports:{} as any}
  new Function('require','module','exports',ts.transpileModule(template,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(()=>({...vue,resolveComponent:(name:string)=>({name}),resolveDirective:()=>({}),withDirectives:(node:any)=>node}),rendered,rendered.exports)
  function elements(){const nodes:any[]=[];function visit(node:any){if(!node||typeof node!=='object')return;if(Array.isArray(node)){node.forEach(visit);return}nodes.push(node);visit(typeof node.children?.default==='function'?node.children.default():node.children)}visit(rendered.exports.render(vue.proxyRefs(state),[]));return nodes}
  return {state,calls,elements,stop(){unmounted.forEach(fn=>fn());scope.stop()}}
}
