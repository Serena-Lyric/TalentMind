import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {sha256LF} from '../src/graph/historicalSnapshot.ts'
import {validateDeliveryBundle} from '../src/graph/deliverySnapshot.ts'
async function bundle(){
 const analysis=JSON.parse(readFileSync(new URL('../../backend/app/job_analysis/baseline/examples/analysis.json',import.meta.url),'utf8'))
 const claim=analysis.claims[1],jid='jd:p0-synthetic:synthetic-1',sid='skill:Java'
 const record={namespace:analysis.namespace,jd_id:analysis.jd_id,fingerprint:analysis.input_sha256,payload:analysis.input_row,analysis,eligible:true}
 const graph={nodes:[{id:jid,type:'job',source_records:[0]},{id:sid,type:'skill',source_records:[0]}],edges:[{id:'edge',type:'HAS_SKILL_STATEMENT',source:jid,target:sid,source_record:0,member:'Java',statement_id:claim.id,statement:claim,requirement:claim.requirement,evidence:claim.evidence[0],state:'required',relation:'any_of',condition:null,degree:null,independent_requirement:false}]}
 const facts=JSON.stringify(graph),layout={schema_version:'m3-p2-1-layout-v1',snapshot_sha256_lf:await sha256LF(facts),nodes:[{id:jid,x:0,y:0},{id:sid,x:1,y:1}],derived_edges:[]}
 const texts={'facts.json':facts,'sources.json':JSON.stringify({records:[record],work:{}}),'layout.json':JSON.stringify(layout)}
 const manifest={schema_version:'m3-delivery-bundle-1',data_version:'d'.repeat(64),delivery:{run_id:'run',request_sha256:'a'.repeat(64),result_sha256:'b'.repeat(64),knowledge_sha256:'c'.repeat(64)},artifacts:Object.fromEntries(await Promise.all(Object.entries(texts).map(async([k,v])=>[k,await sha256LF(v)])))}
 return {manifest,texts,graph}
}
test('新图保留完整任选陈述且校验原文 Unicode 偏移',async()=>{
 const {manifest,texts}=await bundle();const result=await validateDeliveryBundle(manifest,texts,'run')
 assert.equal(result.graph.edges[0].raw.requirement.combination,'any_of')
 assert.deepEqual(result.graph.edges[0].raw.requirement.members,['Java','Python','其他语言'])
 await assert.rejects(validateDeliveryBundle(manifest,texts,'other'),/binding/)
})
test('即使重新生成 artifact SHA，篡改组合或原文证据仍拒绝',async()=>{
 const {manifest,texts,graph}=await bundle();graph.edges[0].requirement={...graph.edges[0].requirement,combination:'single'}
 texts['facts.json']=JSON.stringify(graph);manifest.artifacts['facts.json']=await sha256LF(texts['facts.json'])
 await assert.rejects(validateDeliveryBundle(manifest,texts,'run'),/statement/)
})

test('缺失或变化的所选图谱必须报错，绝不请求历史数据',async()=>{
 const {loadDeliveryGraph}=await import('../src/graph/deliverySnapshot.ts')
 const original=globalThis.fetch,urls:string[]=[]
 globalThis.fetch=async(input:any)=>{urls.push(String(input));return {ok:false,status:404} as Response}
 try {await assert.rejects(loadDeliveryGraph('run','f'.repeat(64)),/unavailable/);assert.deepEqual(urls,[`/api/m2/delivery/runs/run/graph/manifest.json?snapshot=${'f'.repeat(64)}`])} finally {globalThis.fetch=original}
})
