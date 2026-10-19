import { Box3, QuadraticBezierCurve3, Vector3, type Frustum } from 'three'
import type { GraphEdge, GraphNode } from '../../api/graph'

export function relationCurve(edge:GraphEdge,positions:Map<string,Vector3>) {
 const a=positions.get(edge.source)!,b=positions.get(edge.target)!,direction=b.clone().sub(a)
 const normal=direction.clone().cross(new Vector3(0,1,0)).normalize()
 const index=edge.sourceIndex??0,offset=((Math.imul(index+1,2654435761)>>>0)/4294967296-.5)*Math.min(7,direction.length()*.16)
 const control=a.clone().add(b).multiplyScalar(.5).addScaledVector(normal,offset)
 control.y+=Math.min(3,direction.length()*.04)*Math.sin(index*2.39996)
 return new QuadraticBezierCurve3(a,control,b)
}
export function spatialRelations(edges:GraphEdge[],byId:Map<string,GraphNode>,positions:Map<string,Vector3>,options:{visibleIds:Set<string>;activeKinds:Set<string>;selectedId?:string;scale:number;frustum?:Frustum;bounds?:Map<GraphEdge,Box3>;showUnselected?:boolean}) {
 const audit={scope:0,interactionHidden:0,invalidEndpoint:0,typeHidden:0,lodHidden:0,unplaced:0,viewportHidden:0,lengthHidden:0,budgetHidden:0,submitted:0}
 const groups=new Map<string,GraphEdge[]>()
 for(const edge of edges){
  if(options.selectedId&&edge.source!==options.selectedId&&edge.target!==options.selectedId)continue
  audit.scope++
  if(!options.selectedId&&!options.showUnselected){audit.interactionHidden++;continue}
  const a=byId.get(edge.source),b=byId.get(edge.target),p=positions.get(edge.source),q=positions.get(edge.target)
  if(!a||!b){audit.invalidEndpoint++;continue}
  if(!options.activeKinds.has(a.kind)||!options.activeKinds.has(b.kind)){audit.typeHidden++;continue}
  if(!options.visibleIds.has(a.id)||!options.visibleIds.has(b.id)){audit.lodHidden++;continue}
  if(!p||!q){audit.unplaced++;continue}
  if(!options.selectedId&&options.frustum){
   const box=options.bounds?.get(edge)||new Box3().setFromPoints([p,q,relationCurve(edge,positions).v1])
   if(!options.frustum.intersectsBox(box)){audit.viewportHidden++;continue}
  }
  if(!groups.has(edge.kind))groups.set(edge.kind,[])
  groups.get(edge.kind)!.push(edge)
 }
 const limit=options.selectedId?Infinity:options.scale<.35?120:options.scale<.9?300:900
 const output:GraphEdge[]=[],queues=[...groups.values()]
 // Stable spread across relation types and the full source array, rather than first N edges.
 for(const queue of queues)queue.sort((a,b)=>((Math.imul((a.sourceIndex??0)+1,2654435761)>>>0)-(Math.imul((b.sourceIndex??0)+1,2654435761)>>>0)))
 for(let i=0;queues.some(q=>i<q.length)&&output.length<limit;i++)for(const queue of queues)if(queue[i]&&output.length<limit)output.push(queue[i])
 audit.submitted=output.length;audit.budgetHidden=queues.reduce((n,q)=>n+q.length,0)-output.length
 return {edges:output,audit}
}
export function pickProjected(nodes:Iterable<{id:string;x:number;y:number;depth:number;visible:boolean;radius:number}>,x:number,y:number) {
 let best:{id:string;distance:number;depth:number}|null=null
 for(const node of nodes){
  if(!node.visible)continue
  const distance=Math.hypot(node.x-x,node.y-y)
  if(distance>node.radius+7)continue
  if(!best||distance<best.distance-1e-6||(Math.abs(distance-best.distance)<1e-6&&(node.depth<best.depth||(node.depth===best.depth&&node.id<best.id))))best={id:node.id,distance,depth:node.depth}
 }
 return best?.id??null
}
export function derivedSpatialEdges(edges:GraphEdge[],byId:Map<string,GraphNode>,visibleIds:Set<string>,activeKinds:Set<string>,focusIds?:Set<string>) {
 return edges.filter(e=>activeKinds.has(byId.get(e.source)!.kind)&&activeKinds.has(byId.get(e.target)!.kind)&&visibleIds.has(e.source)&&visibleIds.has(e.target)&&(!focusIds||(focusIds.has(e.source)&&focusIds.has(e.target)))).slice(0,160)
}
