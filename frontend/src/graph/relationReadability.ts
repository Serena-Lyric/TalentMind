import type { GraphNode, GraphEdge } from '../api/graph'
import type { Point } from './nebulaViewport'
import { selectEdgePlan, segmentInBounds, type EdgeOptions, type Bounds } from './nebulaEdges.ts'

export function planRelations(edges:GraphEdge[],nodes:GraphNode[],positions:Map<string,Point>,options:EdgeOptions&{visibleIds:Set<string>}) {
 const byId=new Map(nodes.map(n=>[n.id,n])), scope=options.selectedId?edges.filter(e=>e.source===options.selectedId||e.target===options.selectedId):edges
 const audit={scope:scope.length,invalidEndpoint:0,typeHidden:0,lodHidden:0,unplaced:0,viewportHidden:0,lengthHidden:0,budgetHidden:0,submitted:0}
 const eligible:GraphEdge[]=[]
 for(const edge of scope) {
  const a=byId.get(edge.source),b=byId.get(edge.target),p=positions.get(edge.source),q=positions.get(edge.target)
  if(!a||!b){audit.invalidEndpoint++;continue}
  if(!options.activeKinds.has(a.kind)||!options.activeKinds.has(b.kind)){audit.typeHidden++;continue}
  if(!options.visibleIds.has(a.id)||!options.visibleIds.has(b.id)){audit.lodHidden++;continue}
  if(!p||!q||![p.x,p.y,q.x,q.y].every(Number.isFinite)){audit.unplaced++;continue}
  if(!options.selectedId&&!segmentInBounds(p,q,options.viewport)){audit.viewportHidden++;continue}
  eligible.push(edge)
 }
 const plan=selectEdgePlan(eligible,nodes,positions,options)
 audit.lengthHidden=plan.lengthHidden;audit.budgetHidden=plan.eligibleCount-plan.edges.length;audit.submitted=plan.edges.length
 const accounted=Object.entries(audit).filter(([key])=>key!=='scope').reduce((sum,[,count])=>sum+count,0)
 if(accounted!==audit.scope)throw new Error('Relationship visibility accounting mismatch')
 return {...plan,audit,dataDegree:scope.length,typeFilteredDirect:scope.filter(e=>byId.has(e.source)&&byId.has(e.target)&&options.activeKinds.has(byId.get(e.source)!.kind)&&options.activeKinds.has(byId.get(e.target)!.kind)).length}
}

// Screen-space fanning changes each curve only; every original edge remains separate.
export function fanControls(edges:GraphEdge[],positions:Map<string,Point>,selectedId:string) {
 const center=positions.get(selectedId), result=new Map<GraphEdge,Point>()
 if(!center)return result
 const groups=new Map<number,GraphEdge[]>()
 for(const edge of edges) {
  const other=positions.get(edge.source===selectedId?edge.target:edge.source)
  if(!other)continue
  const bin=Math.floor((Math.atan2(other.y-center.y,other.x-center.x)+Math.PI)/.18)
  if(!groups.has(bin))groups.set(bin,[])
  groups.get(bin)!.push(edge)
 }
 for(const group of groups.values()) {
  group.sort((a,b)=>(a.sourceIndex??0)-(b.sourceIndex??0)||a.source.localeCompare(b.source)||a.target.localeCompare(b.target))
  group.forEach((edge,i)=>{
   const a=positions.get(edge.source)!,b=positions.get(edge.target)!,other=edge.source===selectedId?b:a
   const dx=other.x-center.x,dy=other.y-center.y,length=Math.hypot(dx,dy)||1
   const offset=edges.length>16?(i-(group.length-1)/2)*Math.min(3,72/Math.max(1,group.length-1)):0
   result.set(edge,{x:(a.x+b.x)/2-dy/length*offset,y:(a.y+b.y)/2+dx/length*offset})
  })
 }
 return result
}
export function curveIntersects(a:Point,c:Point,b:Point,bounds:Bounds) {
 const times=[0,1]
 const roots=(start:number,control:number,end:number,bound:number)=>{
  const aa=start-2*control+end,bb=2*(control-start),cc=start-bound
  if(Math.abs(aa)<1e-12){if(Math.abs(bb)>1e-12)times.push(-cc/bb);return}
  const discriminant=bb*bb-4*aa*cc
  if(discriminant>=0){const root=Math.sqrt(discriminant);times.push((-bb-root)/(2*aa),(-bb+root)/(2*aa))}
 }
 roots(a.x,c.x,b.x,bounds.left);roots(a.x,c.x,b.x,bounds.right)
 roots(a.y,c.y,b.y,bounds.top);roots(a.y,c.y,b.y,bounds.bottom)
 return times.some(t=>{
  if(t<0||t>1)return false
  const u=1-t,x=u*u*a.x+2*u*t*c.x+t*t*b.x,y=u*u*a.y+2*u*t*c.y+t*t*b.y,epsilon=1e-7
  return x>=bounds.left-epsilon&&x<=bounds.right+epsilon&&y>=bounds.top-epsilon&&y<=bounds.bottom+epsilon
 })
}
