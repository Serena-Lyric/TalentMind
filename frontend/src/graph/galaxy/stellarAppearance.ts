import type { Vector3 } from 'three'

export const STELLAR_VERSION='stellar-id-v1'
export const STELLAR_TYPES=['blue-white','red-giant','white-dwarf','pulsar'] as const
export type StellarType=typeof STELLAR_TYPES[number]
export const stellarNames:Record<StellarType,string>={'blue-white':'蓝白恒星','red-giant':'红橙巨星','white-dwarf':'白矮星',pulsar:'中子星 / 脉冲星'}
function hashId(id:string){let hash=2166136261;for(const c of id)hash=Math.imul(hash^c.charCodeAt(0),16777619);return hash>>>0}
// Appearance only: no kind, degree, JD count, community, or business score enters this mapping.
export function stellarProfile(id:string,preset?:StellarType) {
 const seed=hashId(id),index=preset?STELLAR_TYPES.indexOf(preset):seed%4
 return {type:STELLAR_TYPES[index],index,seed:seed/4294967296}
}
export function stellarSize(scale:number,selected:boolean,maxPointSize=Infinity,dpr=1) {
 const detail=1-Math.exp(-Math.max(0,scale)*.85)
 const hardwareRadius=Math.max(.1,(maxPointSize/dpr/2-4)/2.6)
 return {radius:Math.min(hardwareRadius,selected?5+23*detail:.7+6.3*detail),detail}
}
export function transitionDust(positions:Map<string,Vector3>) {
 const count=positions.size*12,position=new Float32Array(count*3),phase=new Float32Array(count)
 let i=0
 for(const [id,p] of positions){
  let state=hashId(id)
  const random=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return (state+.5)/4294967296}
  for(let j=0;j<12;j++,i++){
   const angle=random()*Math.PI*2,r=.6+Math.pow(random(),.65)*6,dy=(random()-.5)*2.4
   position.set([p.x+Math.cos(angle)*r,p.y+dy,p.z+Math.sin(angle)*r],i*3);phase[i]=random()
  }
 }
 return {count,position,phase}
}
