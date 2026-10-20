import type { GraphNode } from '../../api/graph'
import { stellarProfile } from './stellarAppearance'

export const KNOWLEDGE_STELLAR_VERSION='knowledge-body-v1'
export const knowledgeColors={job:'#7caff1',skill:'#74cbb8',industry:'#b199d9'}
const bodies={job:'蓝色恒星',skill:'青绿紧凑星',industry:'紫色环状星'}
export function knowledgeProfile(kind:GraphNode['kind'],id:string) {
 return {type:bodies[kind],color:knowledgeColors[kind],seed:stellarProfile(id).seed}
}

// Bilinear splat + sample: a continuous screen-space field, with constant work per node
// even when all 7,845 nodes overlap. CSS pixels keep the response independent of DPR.
export function screenDensity(points:Iterable<{id:string;x:number;y:number}>) {
 const input=[...points],grid=new Map<string,number>(),size=32
 const weights=(x:number,y:number,visit:(key:string,weight:number)=>void)=>{
  const gx=x/size,gy=y/size,ix=Math.floor(gx),iy=Math.floor(gy),fx=gx-ix,fy=gy-iy
  for(let dx=0;dx<2;dx++)for(let dy=0;dy<2;dy++)visit(`${ix+dx},${iy+dy}`,(dx?fx:1-fx)*(dy?fy:1-fy))
 }
 for(const p of input)weights(p.x,p.y,(key,w)=>grid.set(key,(grid.get(key)||0)+w))
 const result=new Map<string,number>()
 for(const p of input){let density=0;weights(p.x,p.y,(key,w)=>{density+=(grid.get(key)||0)*w});result.set(p.id,density)}
 return result
}
export function densityAppearance(density:number,protectedStar:boolean) {
 const clarity=1/(1+.22*Math.max(0,density-1))
 return protectedStar?{radius:1,halo:.85,opacity:1}:{radius:.72+.28*clarity,halo:.14+.86*clarity,opacity:.68+.32*clarity}
}
