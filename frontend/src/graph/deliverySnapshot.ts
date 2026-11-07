import { adaptSnapshot, sha256LF, validateBinding, type LayoutArtifact } from './historicalSnapshot.ts'
import type { RealManifest, RealSources } from './realSnapshot.ts'
const files=['facts.json','sources.json','layout.json'] as const
const encoded=(value:string)=>encodeURIComponent(value).replace(/[!'()*]/g,c=>'%'+c.charCodeAt(0).toString(16).toUpperCase())
function same(a:any,b:any):boolean {
 if(a===b)return true
 if(!a||!b||typeof a!=='object'||typeof b!=='object')return false
 const left=Object.keys(a).sort(),right=Object.keys(b).sort()
 return left.length===right.length&&left.every((k,i)=>k===right[i]&&same(a[k],b[k]))
}
export async function validateDeliveryBundle(manifest:RealManifest,texts:Record<string,string>,runId:string){
 const binding=manifest.delivery
 if(manifest.schema_version!=='m3-delivery-bundle-1'||!binding||binding.run_id!==runId||![binding.request_sha256,binding.result_sha256,binding.knowledge_sha256].every(s=>typeof s==='string'&&/^[a-f0-9]{64}$/.test(s)))throw Error('Delivery graph version binding mismatch')
 for(const name of files)if(await sha256LF(texts[name])!==manifest.artifacts[name])throw Error(`Delivery artifact hash mismatch: ${name}`)
 const raw=JSON.parse(texts['facts.json']),sources=JSON.parse(texts['sources.json']) as RealSources
 if(!Array.isArray(sources.records))throw Error('Invalid delivery source records')
 const valid=(i:number)=>Number.isInteger(i)&&i>=0&&i<sources.records.length
 const jid=(i:number)=>`jd:${encoded(sources.records[i].namespace)}:${encoded(sources.records[i].jd_id)}`
 const nodes=new Map<string,any>(raw.nodes.map((n:any)=>[n.id,n]))
 for(const node of raw.nodes){
  if(!Array.isArray(node.source_records)||node.source_records.some((i:number)=>!valid(i)||!sources.records[i].analysis))throw Error('Invalid delivery node source')
  if(node.type==='job'&&!node.id.startsWith('work:')&&(node.source_records.length!==1||node.id!==jid(node.source_records[0])))throw Error('Invalid delivery JD identity')
  if(node.id.startsWith('work:')&&!same(node.candidate,sources.work?.candidates?.[decodeURIComponent(node.id.slice(5))]))throw Error('Invalid research candidate binding')
 }
 for(const edge of raw.edges){
  if(!valid(edge.source_record))throw Error('Invalid delivery source reference')
  const record=sources.records[edge.source_record],analysis=record.analysis,ev=edge.evidence
  if(!analysis||!ev||ev.namespace!==record.namespace||ev.jd_id!==record.jd_id||ev.fingerprint!==record.fingerprint||typeof record.payload[ev.field]!=='string'||!Number.isInteger(ev.start)||!Number.isInteger(ev.end)||ev.start<0||ev.end<=ev.start||Array.from(record.payload[ev.field] as string).slice(ev.start,ev.end).join('')!==ev.quote)throw Error('Invalid delivery source evidence')
  if(edge.type==='HAS_SKILL_STATEMENT'){
   const claim=analysis.claims.find((c:any)=>c.id===edge.statement_id),req=claim?.requirement
   if(!claim||!req||!same(claim,edge.statement)||!same(req,edge.requirement)||!req.members.includes(edge.member)||!claim.evidence.some((e:any)=>same(e,ev))||edge.source!==jid(edge.source_record)||edge.target!==`skill:${encoded(edge.member)}`||!nodes.get(edge.target)?.source_records.includes(edge.source_record)||edge.state!==req.state||edge.relation!==req.combination||edge.condition!==req.condition||edge.degree!==req.degree||edge.independent_requirement!==(req.combination==='single'&&!req.condition&&!req.open_set))throw Error('Invalid delivery statement binding')
  }else if(edge.type==='RELATED_TO'){
   const relation=sources.work?.relations?.[edge.research_relation?.id]
   if(!relation||!same(relation,edge.research_relation)||['withdrawn','rejected_proposal'].includes(relation.state)||relation.analysis_sha256!==record.analysis_sha256||edge.source!==`work:${encoded(relation.candidate_id)}`||edge.target!==jid(edge.source_record)||!analysis.claims.some((c:any)=>relation.work_ids.includes(c.id)&&c.evidence.some((e:any)=>same(e,ev))))throw Error('Invalid delivery research relation binding')
  }else throw Error('Unexpected delivery relation')
 }
 const graph=adaptSnapshot(raw),artifact:LayoutArtifact=JSON.parse(texts['layout.json'])
 await validateBinding(texts['facts.json'],artifact,graph)
 return {graph,artifact,sources,manifest}
}
export async function loadDeliveryGraph(runId:string|null,manifestSha:string|null){
 if(!runId||! /^[A-Za-z0-9_-]{1,128}$/.test(runId)||!manifestSha||!/^[a-f0-9]{64}$/.test(manifestSha))throw Error('Invalid delivery graph run or manifest binding')
 async function read(name:string){const response=await fetch(`/api/m2/delivery/runs/${encodeURIComponent(runId!)}/graph/${name}?snapshot=${encodeURIComponent(manifestSha!)}`);if(!response.ok)throw Error(`Delivery graph unavailable: ${name} (${response.status})`);return response.text()}
 const text=await read('manifest.json')
 if(await sha256LF(text)!==manifestSha)throw Error('Delivery manifest changed; return to the selected run and reopen its current graph')
 const values=await Promise.all(files.map(read))
 return validateDeliveryBundle(JSON.parse(text),Object.fromEntries(files.map((n,i)=>[n,values[i]])),runId)
}
