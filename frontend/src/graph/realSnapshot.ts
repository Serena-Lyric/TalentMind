import { adaptSnapshot, sha256LF, validateBinding, type LayoutArtifact } from './historicalSnapshot.ts'

export interface SourceRecord {
  namespace:string; jd_id:string; fingerprint:string; payload:Record<string,any>; observation?:string|null
  eligible:boolean; screening:Record<string,any>; governance:Record<string,any>|null
}
export interface RealSources { records:SourceRecord[] }
export interface RealManifest { schema_version:string; data_version:string; artifacts:Record<string,string>; counts?:Record<string,any>; input_sha256?:string; m2_product?:{run_id:string;input_sha256:string;report_sha256:string;versions:Record<string,any>} }
const files = ['facts.json','sources.json','layout.json'] as const
const encoded=(value:string)=>encodeURIComponent(value).replace(/[!'()*]/g,char=>'%'+char.charCodeAt(0).toString(16).toUpperCase())
const jdIdentity=(record:SourceRecord)=>`jd:${encoded(record.namespace)}:${encoded(record.jd_id)}`
const same=(a:unknown,b:unknown)=>JSON.stringify(a)===JSON.stringify(b)

export async function validateRealBundle(manifest:RealManifest,texts:Record<string,string>) {
  if(manifest.schema_version!=='m3-real-bundle-1')throw new Error('Real bundle schema mismatch')
  for(const name of files)if(await sha256LF(texts[name])!==manifest.artifacts[name])throw new Error(`Real artifact hash mismatch: ${name}`)
  const raw=JSON.parse(texts['facts.json']), sources:RealSources=JSON.parse(texts['sources.json'])
  if(!Array.isArray(sources.records))throw new Error('Invalid source records')
  const validIndex=(index:number)=>Number.isInteger(index)&&index>=0&&index<sources.records.length
  const nodeMap=new Map<string,any>(raw.nodes.map((node:any)=>[node.id,node]))
  for(const node of raw.nodes){
    if(!Array.isArray(node.source_records)||!node.source_records.length||node.source_records.some((i:number)=>!validIndex(i)||!sources.records[i].eligible))throw new Error('Invalid node source reference')
    if(node.type==='job'&&(node.source_records.length!==1||node.id!==jdIdentity(sources.records[node.source_records[0]])))throw new Error('Invalid job source identity')
  }
  for(const edge of raw.edges){
    if(!validIndex(edge.source_record))throw new Error('Invalid edge source reference')
    const record=sources.records[edge.source_record], ev=edge.evidence
    const skill=record.governance?.skills?.find((s:any)=>s.id===edge.normalization?.id)
    const statement=record.governance?.original_semantics?.statements?.find((s:any)=>s.id===edge.statement_id)
    if(!record.eligible||!ev||ev.namespace!==record.namespace||ev.jd_id!==record.jd_id||ev.fingerprint!==record.fingerprint||typeof record.payload[ev.field]!=='string'
      ||!Number.isInteger(ev.start)||!Number.isInteger(ev.end)||ev.start<0||ev.end<=ev.start||Array.from(record.payload[ev.field]).slice(ev.start,ev.end).join('')!==ev.quote)throw new Error('Invalid source evidence')
    if(!skill||!statement||!skill.statement_ids.includes(edge.statement_id)||!same(skill.evidence,ev)||!same(statement,edge.statement)
      ||edge.source!==jdIdentity(record)||edge.target!==`skill:${encoded(skill.canonical)}`||!nodeMap.get(edge.target)?.source_records.includes(edge.source_record)
      ||edge.type!=='HAS_SKILL_STATEMENT'||['state','relation','degree','condition','requirement_object'].some(key=>!same(edge[key],statement[key]))
      ||edge.target_context!==statement.target)throw new Error('Invalid source statement binding')
  }
  const graph=adaptSnapshot(raw)
  const artifact:LayoutArtifact=JSON.parse(texts['layout.json'])
  await validateBinding(texts['facts.json'],artifact,graph)
  return {graph,artifact,sources,manifest}
}

export function validateM2GraphBinding(manifest:RealManifest,runId:string) {
  const binding=manifest.m2_product
  if(!binding||binding.run_id!==runId||binding.input_sha256!==manifest.input_sha256||!binding.report_sha256
    ||!binding.versions?.implementation||!binding.versions?.revision)throw new Error('M2 graph version binding mismatch')
}

export async function loadRealGraph(runId?:string|null,manifestSha?:string|null) {
  if(runId&&(!/^[a-f0-9]{32}$/.test(runId)||!manifestSha||!/^[a-f0-9]{64}$/.test(manifestSha)))throw new Error('Invalid M2 graph run or manifest binding')
  async function read(name:string){
    const response=await fetch(runId?`/api/m2/runs/${runId}/graph/${name}`:`/real-graph-artifacts/${name}`)
    if(!response.ok)throw new Error(`Real bundle unavailable: ${name}`)
    return response.text()
  }
  const manifestText=await read('manifest.json')
  const expected=runId?manifestSha:__REAL_GRAPH_MANIFEST_SHA256__
  if(!expected||await sha256LF(manifestText)!==expected)throw new Error('Real manifest hash mismatch or preview not enabled')
  const manifest=JSON.parse(manifestText)
  if(runId)validateM2GraphBinding(manifest,runId)
  const values=await Promise.all(files.map(read))
  return validateRealBundle(manifest,Object.fromEntries(files.map((name,i)=>[name,values[i]])))
}
