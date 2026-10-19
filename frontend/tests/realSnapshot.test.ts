import { test } from 'node:test'
import assert from 'node:assert/strict'
import { sha256LF } from '../src/graph/historicalSnapshot.ts'
import { validateRealBundle } from '../src/graph/realSnapshot.ts'

test('真实产物绑定哈希并保留五态与原始来源；错误摘要及越界来源拒绝', async () => {
  const payload = {source:'synthetic',job_title:'软件工程师',raw_text:'必须掌握Python'}
  const fingerprint=await sha256LF(JSON.stringify(payload))
  const evidence={namespace:'test',jd_id:'1',fingerprint,field:'raw_text',start:4,end:10,quote:'Python'}
  const statement={id:'s1',state:'uncertain',relation:null,condition:null,degree:null,requirement_object:'unresolved',target:'candidate'}
  const skill={id:'k1',canonical:'python',statement_ids:['s1'],evidence}
  const sources = {records:[{namespace:'test',jd_id:'1',payload,fingerprint,eligible:true,governance:{skills:[skill],original_semantics:{statements:[statement]}}}]}
  const graph = {nodes:[{id:'jd:test:1',type:'job',name:'软件工程师',source_records:[0]}, {id:'skill:python',type:'skill',name:'python',source_records:[0]}],edges:[{id:'e',source:'jd:test:1',target:'skill:python',type:'HAS_SKILL_STATEMENT',state:'uncertain',conflict:true,source_record:0,evidence,statement_id:'s1',statement,normalization:{id:'k1'},relation:null,condition:null,degree:null,requirement_object:'unresolved',target_context:'candidate'}]}
  const facts = JSON.stringify(graph), sourceText = JSON.stringify(sources)
  const layout = {schema_version:'m3-p2-1-layout-v1',snapshot_sha256_lf:await sha256LF(facts),nodes:graph.nodes.map(n=>({id:n.id,x:0,y:0,degree:1,community:null})),derived_edges:[]}
  const texts = {'facts.json':facts,'sources.json':sourceText,'layout.json':JSON.stringify(layout)}
  const manifest = {schema_version:'m3-real-bundle-1',data_version:'test',artifacts:Object.fromEntries(await Promise.all(Object.entries(texts).map(async([k,v])=>[k,await sha256LF(v)])))}
  const result = await validateRealBundle(manifest,texts)
  assert.equal(result.graph.edges[0].raw?.state,'uncertain')
  assert.equal(result.graph.edges[0].raw?.conflict,true)
  assert.equal(result.sources.records[0].jd_id,'1')
  await assert.rejects(validateRealBundle({...manifest,artifacts:{...manifest.artifacts,'sources.json':'bad'}},texts),/hash/i)
  const bad = JSON.stringify({...graph,edges:[{...graph.edges[0],source_record:2}]})
  await assert.rejects(validateRealBundle({...manifest,artifacts:{...manifest.artifacts,'facts.json':await sha256LF(bad)}},{...texts,'facts.json':bad}),/source/i)
  const foreign=JSON.stringify({...graph,edges:[{...graph.edges[0],evidence:{...evidence,jd_id:'other'}}]})
  const foreignLayout=JSON.stringify({...layout,snapshot_sha256_lf:await sha256LF(foreign)})
  await assert.rejects(validateRealBundle({...manifest,artifacts:{...manifest.artifacts,'facts.json':await sha256LF(foreign),'layout.json':await sha256LF(foreignLayout)}},{...texts,'facts.json':foreign,'layout.json':foreignLayout}),/source/i)
  // Python offsets are Unicode code points; an emoji before the quote must remain valid.
  payload.raw_text='😀必须掌握Python';evidence.start=5;evidence.end=11
  const unicodeTexts={'facts.json':JSON.stringify(graph),'sources.json':JSON.stringify(sources),'layout.json':JSON.stringify({...layout,snapshot_sha256_lf:await sha256LF(JSON.stringify(graph))})}
  const unicodeManifest={...manifest,artifacts:Object.fromEntries(await Promise.all(Object.entries(unicodeTexts).map(async([k,v])=>[k,await sha256LF(v)])))}
  await validateRealBundle(unicodeManifest,unicodeTexts)
})
