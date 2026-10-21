import { test } from 'node:test'
import assert from 'node:assert/strict'
import { sha256LF } from '../src/graph/historicalSnapshot.ts'
import { validateRealBundle, validateM2GraphBinding } from '../src/graph/realSnapshot.ts'
import { graphComponent } from './helpers/graphComponent.ts'

test('M2候选图拒绝其他运行与缺失分析版本，输入版本必须一致', () => {
  const id = 'a'.repeat(32)
  const manifest = { schema_version:'m3-real-bundle-1', data_version:'v', artifacts:{}, input_sha256:'input',
    m2_product:{run_id:id,input_sha256:'input',report_sha256:'report',versions:{implementation:'code',revision:'v1'}} }
  validateM2GraphBinding(manifest,id)
  assert.throws(() => validateM2GraphBinding(manifest,'b'.repeat(32)), /binding/i)
  assert.throws(() => validateM2GraphBinding({...manifest,input_sha256:'other'},id), /binding/i)
  assert.throws(() => validateM2GraphBinding({...manifest,m2_product:{...manifest.m2_product,versions:{}}},id), /binding/i)
})

test('真实产物绑定哈希并保留五态与原始来源；错误摘要及越界来源拒绝', async () => {
  const payload = {source:'synthetic',job_title:'软件工程师',raw_text:'必须掌握Python'}
  const fingerprint=await sha256LF(JSON.stringify(payload))
  const evidence={namespace:'test',jd_id:'1',fingerprint,field:'raw_text',start:4,end:10,quote:'Python'}
  const statement={id:'s1',state:'uncertain',relation:null,condition:null,degree:null,requirement_object:'unresolved',target:'candidate'}
  const skill={id:'k1',canonical:'python',statement_ids:['s1'],evidence}
  const sources = {records:[{namespace:'test',jd_id:'1',payload,fingerprint,eligible:true,identity_status:'pending',content_eligible:true,identity_evidence:{binding_policy:'zhaopin-dom-panel-v1'},governance:{skills:[skill],original_semantics:{statements:[statement]}}}]}
  const graph = {nodes:[{id:'jd:test:1',type:'job',name:'软件工程师',source_records:[0],identity_status:'pending',content_eligible:true,formal_statistics_eligible:false}, {id:'skill:python',type:'skill',name:'python',source_records:[0]}],edges:[{id:'e',source:'jd:test:1',target:'skill:python',type:'HAS_SKILL_STATEMENT',state:'uncertain',conflict:true,source_record:0,evidence,statement_id:'s1',statement,normalization:{id:'k1'},relation:null,condition:null,degree:null,requirement_object:'unresolved',target_context:'candidate'}]}
  const facts = JSON.stringify(graph), sourceText = JSON.stringify(sources)
  const layout = {schema_version:'m3-p2-1-layout-v1',snapshot_sha256_lf:await sha256LF(facts),nodes:graph.nodes.map(n=>({id:n.id,x:0,y:0,degree:1,community:null})),derived_edges:[]}
  const texts = {'facts.json':facts,'sources.json':sourceText,'layout.json':JSON.stringify(layout)}
  const manifest = {schema_version:'m3-real-bundle-1',data_version:'test',artifacts:Object.fromEntries(await Promise.all(Object.entries(texts).map(async([k,v])=>[k,await sha256LF(v)])))}
  const result = await validateRealBundle(manifest,texts)
  assert.equal(result.graph.edges[0].raw?.state,'uncertain')
  assert.equal(result.graph.edges[0].raw?.conflict,true)
  assert.equal(result.sources.records[0].jd_id,'1')
  assert.equal(result.sources.records[0].identity_status,'pending')
  assert.equal(result.graph.nodes[0].raw?.identity_status,'pending')
  await assert.rejects(validateRealBundle({...manifest,artifacts:{...manifest.artifacts,'sources.json':'bad'}},texts),/hash/i)
  const bad = JSON.stringify({...graph,edges:[{...graph.edges[0],source_record:2}]})
  await assert.rejects(validateRealBundle({...manifest,artifacts:{...manifest.artifacts,'facts.json':await sha256LF(bad)}},{...texts,'facts.json':bad}),/source/i)
  const foreign=JSON.stringify({...graph,edges:[{...graph.edges[0],evidence:{...evidence,jd_id:'other'}}]})
  const foreignLayout=JSON.stringify({...layout,snapshot_sha256_lf:await sha256LF(foreign)})
  await assert.rejects(validateRealBundle({...manifest,artifacts:{...manifest.artifacts,'facts.json':await sha256LF(foreign),'layout.json':await sha256LF(foreignLayout)}},{...texts,'facts.json':foreign,'layout.json':foreignLayout}),/source/i)
  const identityMismatch=JSON.stringify({...graph,nodes:[{...graph.nodes[0],identity_status:'verified'},graph.nodes[1]]})
  const identityMismatchLayout=JSON.stringify({...layout,snapshot_sha256_lf:await sha256LF(identityMismatch)})
  await assert.rejects(validateRealBundle({...manifest,artifacts:{...manifest.artifacts,'facts.json':await sha256LF(identityMismatch),'layout.json':await sha256LF(identityMismatchLayout)}},{...texts,'facts.json':identityMismatch,'layout.json':identityMismatchLayout}),/identity/i)
  // Python offsets are Unicode code points; an emoji before the quote must remain valid.
  payload.raw_text='😀必须掌握Python';evidence.start=5;evidence.end=11
  const unicodeTexts={'facts.json':JSON.stringify(graph),'sources.json':JSON.stringify(sources),'layout.json':JSON.stringify({...layout,snapshot_sha256_lf:await sha256LF(JSON.stringify(graph))})}
  const unicodeManifest={...manifest,artifacts:Object.fromEntries(await Promise.all(Object.entries(unicodeTexts).map(async([k,v])=>[k,await sha256LF(v)])))}
  await validateRealBundle(unicodeManifest,unicodeTexts)
})

test('M3 pending identity有独立中文标签', () => {
  const page = graphComponent()
  try {
    assert.equal(page.state.identityText('pending'), '身份待审')
    assert.equal(page.state.identityText('verified'), '身份已验证')
    assert.equal(page.state.identityText('unknown'), '身份未知')
  } finally {
    page.stop()
  }
})
