import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {parse,compileScript} from 'vue/compiler-sfc'
import * as vue from 'vue'
import {renderToString} from 'vue/server-renderer'
import ts from 'typescript'

async function render(research:any){
  const file=new URL('../src/components/RoleResearch.vue',import.meta.url)
  const compiled=compileScript(parse(readFileSync(file,'utf8')).descriptor,{id:'research',inlineTemplate:true}).content
  const code=ts.transpileModule(compiled,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
  const module={exports:{} as any};new Function('require','module','exports',code)((id:string)=>{if(id==='vue')return vue;throw Error(id)},module,module.exports)
  return renderToString(vue.createSSRApp(module.exports.default,{research,claims:[{id:'d1',text:'开发订单接口',evidence:[]}]}))
}
test('真实岗位研究展示四轴候选、未检查分母、局部支持及未覆盖职责，不提升正式职业',async()=>{
  const axes=Object.fromEntries(['family','canonical_job','technology_tracks','seniority'].map(name=>[name,{status:'unresolved',candidates:[],selected_values:[],reason:'缺少适用证据'}]))
  axes.canonical_job={status:'research_candidates',candidates:[{value:'backend',claim_ids:['d1']}],selected_values:[],reason:'仅局部职责候选'} as any
  const html=await render({schema_version:'m2-role-research-1',status:'bounded_research_completed',axes,coverage:{pool_pairs:7,checked_pairs:2,unchecked_pairs:5,failed_pairs:0},local_supports:[{claim_id:'d1',role_id:'backend',reference_id:'r1',matched_aspects:[{action:'开发',object:'接口'}],source_evidence:[{quote:'开发订单接口'}]}],uncovered_work:[{claim_id:'d2',reason:'no_supported_task_aspect'}],knowledge_gaps:['岗位级别参照缺失'],limitations:['不证明整岗等价']})
  for(const text of ['职业大类','标准岗位','技术方向','岗位级别','backend','已检查','未检查','7','2','5','开发订单接口','d2','岗位级别参照缺失','不证明整岗等价'])assert.ok(html.includes(text),text)
  assert.ok(html.includes('未选定'));assert.ok(html.includes('局部职责支持'))
})
test('旧版本缺失研究保留原状态，不虚构新版已执行结果',async()=>{
  const html=await render({status:'unavailable',reason:'historical snapshot'})
  assert.ok(html.includes('本版本未保存新版岗位研究明细'));assert.ok(html.includes('historical snapshot'));assert.ok(!html.includes('局部职责支持'))
})
test('同一职责有局部支持时仍展示未覆盖原文片段',async()=>{
  const html=await render({schema_version:'m2-role-research-1',status:'bounded_research_completed',local_supports:[{claim_id:'d1',role_id:'backend',reference_id:'r1'}],uncovered_work:[{claim_id:'d1',reason:'partial_source_work_uncovered',source_gaps:[{quote:'主持部门会议'}]}]})
  assert.ok(html.includes('部分工作尚未覆盖'))
  assert.ok(html.includes('主持部门会议'))
})
