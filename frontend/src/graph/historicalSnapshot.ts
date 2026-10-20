import type { GraphData, GraphNode, GraphEdge } from '../api/graph'

export interface SnapshotNode extends GraphNode { raw: Record<string, any>; sourceIndex: number }
export interface SnapshotEdge extends GraphEdge { raw: Record<string, any>; sourceIndex: number }
export interface LayoutNode { id:string; x:number; y:number; degree:number; community:string|null; adjacent_jobs?:string[]; communities?:string[] }
export interface LayoutArtifact {
  schema_version:string; snapshot_sha256_lf:string; nodes:LayoutNode[]
  parameters?:Record<string,unknown>; algorithm_source?:string; partition_sha256?:string
  communities?:{id:string|null;members:string[];isolate:boolean}[]
  derived_edges?:{source:string;target:string;score:number;shared:string[]}[]
}
export interface HistoricalGraph extends GraphData { nodes:SnapshotNode[]; edges:SnapshotEdge[] }

export async function sha256LF(text:string,subtle:SubtleCrypto|null=globalThis.crypto?.subtle ?? null) {
  if(!subtle)throw new Error('摘要验证需要 localhost 或 HTTPS，普通局域网 HTTP 暂不支持')
  const bytes=new TextEncoder().encode(text.replace(/\r\n/g,'\n'))
  return Array.from(new Uint8Array(await subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('')
}

export function adaptSnapshot(input:any):HistoricalGraph {
  if (!Array.isArray(input?.nodes) || !Array.isArray(input?.edges)) throw new Error('Invalid snapshot arrays')
  const ids = new Set<string>()
  const nodes = input.nodes.map((raw:any,sourceIndex:number):SnapshotNode => {
    if (typeof raw.id !== 'string' || !raw.id || ids.has(raw.id)) throw new Error('Invalid/duplicate identity')
    if (!['job','skill','industry'].includes(raw.type) || (raw.kind && raw.kind !== raw.type)) throw new Error('Invalid node kind')
    ids.add(raw.id)
    return { ...raw,id:raw.id,kind:raw.type,label:raw.name_zh || raw.display_name || raw.name || raw.id,
      size:raw.type==='job'?14:8,color:'',platform_label:Array.isArray(raw.source)?raw.source.join('、'):'',raw,sourceIndex }
  })
  const edges = input.edges.map((raw:any,sourceIndex:number):SnapshotEdge => {
    if (!ids.has(raw.source) || !ids.has(raw.target)) throw new Error('Invalid endpoint')
    if (!['REQUIRES','APPLIES_TO','RELATED_TO','HAS_SKILL_STATEMENT'].includes(raw.type)) throw new Error('Invalid relation')
    return {source:raw.source,target:raw.target,kind:raw.type,raw,sourceIndex}
  })
  return {nodes,edges,stats:{totalNodes:nodes.length,totalEdges:edges.length,added:0,removed:0,changed:0}}
}
export async function validateBinding(text:string, artifact:LayoutArtifact, graph:HistoricalGraph) {
  const hash = await sha256LF(text)
  if (artifact.snapshot_sha256_lf !== hash) throw new Error('Snapshot hash mismatch')
  const ids = new Set(graph.nodes.map(n=>n.id)), layoutIds = new Set(artifact.nodes.map(n=>n.id))
  if (artifact.schema_version !== 'm3-p2-1-layout-v1' || artifact.nodes.length !== ids.size || layoutIds.size !== ids.size || artifact.nodes.some(n=>!ids.has(n.id)||!Number.isFinite(n.x)||!Number.isFinite(n.y))) throw new Error('Layout identity mismatch')
  if (artifact.derived_edges?.some(e=>!ids.has(e.source)||!ids.has(e.target)||!Number.isFinite(e.score)||e.shared.some(id=>!ids.has(id)))) throw new Error('Derived endpoint mismatch')
}
export function visibleKnowledgeIds(nodes:Pick<GraphNode,'id'|'kind'>[],meta:Map<string,{degree:number}>,scale:number,priority:Set<string>) {
  return new Set(nodes.filter(n=> n.kind!=='skill' || meta.get(n.id)?.degree!==1 || scale>=.9 || priority.has(n.id)).map(n=>n.id))
}
export async function loadHistoricalSnapshot() {
  const response=await fetch('/graph-artifacts/historical.json')
  if(!response.ok) throw new Error('Historical snapshot unavailable')
  const text=await response.text()
  const hash=await sha256LF(text)
  if(hash!=='e8e3fe6aab4ffd359a16c8c62ee8edd4684504266fafe1534d36599cd7af742f')throw new Error('Historical snapshot hash mismatch')
  const graph = adaptSnapshot(JSON.parse(text))
  if (graph.nodes.length !== 7845 || graph.edges.length !== 11412) throw new Error('Unexpected historical snapshot count')
  return {text,graph}
}
export async function loadHistoricalGraph() {
  const {text,graph}=await loadHistoricalSnapshot()
  const response=await fetch('/graph-artifacts/layout.json')
  if(!response.ok)throw new Error('Candidate layout unavailable')
  const layoutText=await response.text()
  const hash=await sha256LF(layoutText)
  if(hash!==__GRAPH_LAYOUT_SHA256_LF__)throw new Error('Candidate artifact hash mismatch')
  const artifact=JSON.parse(layoutText)
  await validateBinding(text,artifact,graph)
  return {graph,artifact:artifact as LayoutArtifact}
}
