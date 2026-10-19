import type { GraphNode } from '../api/graph'
import type { Bounds } from './nebulaEdges'
import type { LabelCandidate } from './nebulaPresentation'

export function starAppearance(kind:GraphNode['kind'],scale:number,selected=false,matched=false,hovered=false) {
 const base={job:4,skill:2.7,industry:2},cap={job:5,skill:3.6,industry:2.8},minimum={job:.9,skill:.55,industry:.45}
 const radius=Math.min(cap[kind],Math.max(selected||hovered?2.8:matched?1.4:minimum[kind],base[kind]*scale))
 return {radius,haloRadius:radius*({job:2.7,skill:2.4,industry:2.2}[kind]),label:selected||hovered||scale>=1.25||(scale>=.65&&(kind==='job'||matched)),outline:selected||hovered||matched,shadow:0}
}
export function starIntensity(r:number) {
 if(r>=1)return 0
 return Math.exp(-r*r*180)*.82+Math.exp(-r*r*14)*.15+Math.exp(-r*r*5)*.03
}
export function createStarSprites(colors:Record<string,string>) {
 const sprites=new Map<string,{canvas:HTMLCanvasElement;size:number}>()
 return {clear:()=>sprites.clear(),get(kind:GraphNode['kind'],radius:number) {
  const dpr=Math.min(2,devicePixelRatio||1),key=`${kind}:${radius.toFixed(3)}:${dpr}`
  if(sprites.has(key))return sprites.get(key)
  const halo=radius*({job:2.7,skill:2.4,industry:2.2}[kind]),pixels=Math.ceil((2*halo+2)*dpr)
  const canvas=document.createElement('canvas');canvas.width=canvas.height=pixels
  const ctx=canvas.getContext('2d');if(!ctx)return undefined
  ctx.scale(dpr,dpr)
  const size=pixels/dpr,center=size/2,color=colors[kind],rgb=[1,3,5].map(i=>parseInt(color.slice(i,i+2),16)).join(',')
  const gradient=ctx.createRadialGradient(center,center,0,center,center,halo)
  gradient.addColorStop(0,'rgba(255,255,255,.95)')
  for(const radius of [.07,.18,.4,.7,1])gradient.addColorStop(radius,`rgba(${rgb},${starIntensity(radius)})`)
  ctx.fillStyle=gradient;ctx.fillRect(0,0,size,size)
  ctx.fillStyle=color;ctx.beginPath();ctx.arc(center,center,Math.max(.35,radius*.52),0,Math.PI*2);ctx.fill()
  ctx.fillStyle='#f2f6ff';ctx.beginPath();ctx.arc(center,center,Math.max(.25,radius*.23),0,Math.PI*2);ctx.fill()
  if(sprites.size>=96)sprites.delete(sprites.keys().next().value!)
  const sprite={canvas,size};sprites.set(key,sprite);return sprite
 }}
}
export function paintStar(ctx:CanvasRenderingContext2D,x:number,y:number,appearance:ReturnType<typeof starAppearance>,color:string,sprite?:{canvas:HTMLCanvasElement;size:number}) {
 const r=appearance.radius
 if(sprite)ctx.drawImage(sprite.canvas,x-sprite.size/2,y-sprite.size/2,sprite.size,sprite.size)
 else {
  ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,Math.max(.35,r*.52),0,Math.PI*2);ctx.fill()
  ctx.fillStyle='#f2f6ff';ctx.beginPath();ctx.arc(x,y,Math.max(.25,r*.23),0,Math.PI*2);ctx.fill()
 }
 if(appearance.outline){ctx.strokeStyle='rgba(225,239,255,.85)';ctx.lineWidth=.8;ctx.beginPath();ctx.arc(x,y,r+2,0,Math.PI*2);ctx.stroke()}
}

export interface StarLabel extends LabelCandidate { alternatives?:Bounds[] }
export function placeStarLabels(labels:StarLabel[],viewport:Bounds,panels:Bounds[],nodes:{id:string;bounds:Bounds}[],limit:number) {
 const overlaps=(a:Bounds,b:Bounds)=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top
 const grid=new Map<string,{id:string;bounds:Bounds}[]>(),occupied:Bounds[]=[],result=new Map<string,Bounds>()
 const cells=(box:Bounds)=>{const keys:string[]=[];for(let x=Math.floor(box.left/64);x<=Math.floor(box.right/64);x++)for(let y=Math.floor(box.top/64);y<=Math.floor(box.bottom/64);y++)keys.push(`${x}:${y}`);return keys}
 for(const node of nodes)for(const key of cells(node.bounds)){if(!grid.has(key))grid.set(key,[]);grid.get(key)!.push(node)}
 for(const label of [...labels].sort((a,b)=>b.priority-a.priority||a.id.localeCompare(b.id))) {
  if(result.size>=limit&&label.priority<3)continue
  for(const box of [label.bounds,...(label.alternatives||[])]) {
   if(box.left<viewport.left||box.right>viewport.right||box.top<viewport.top||box.bottom>viewport.bottom||panels.some(p=>overlaps(box,p))||occupied.some(p=>overlaps(box,p)))continue
   if(cells(box).some(key=>grid.get(key)?.some(n=>n.id!==label.id&&overlaps(box,n.bounds))))continue
   result.set(label.id,box);occupied.push(box);break
  }
 }
 return result
}
