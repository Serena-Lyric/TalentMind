import { DEPTH_VERSION } from './spatialLayout.ts'

export const GALAXY_FIELD_VERSION='node-field-v1'
export interface FieldInput {
 layoutVersion:string;snapshotHash:string;seed:number;viewSize:number
 positions:ReadonlyArray<{id:string;x:number;y:number;z:number}>
}
export interface GalaxySpatialField {
 version:string;seed:number;nodeCount:number;bounds:{minX:number;maxX:number;minZ:number;maxZ:number}
 sample:(base:number[],random:()=>number,kind:string)=>number[]
}
const SIZE=128,SIGMA=11

function build(input:FieldInput):GalaxySpatialField {
 const points=input.positions,extent=input.viewSize/2
 const bounds={minX:-extent,maxX:extent,minZ:-extent,maxZ:extent}
 for(const p of points){bounds.minX=Math.min(bounds.minX,p.x-4*SIGMA);bounds.maxX=Math.max(bounds.maxX,p.x+4*SIGMA);bounds.minZ=Math.min(bounds.minZ,p.z-4*SIGMA);bounds.maxZ=Math.max(bounds.maxZ,p.z+4*SIGMA)}
 const dx=(bounds.maxX-bounds.minX)/SIZE,dz=(bounds.maxZ-bounds.minZ)/SIZE
 const mass=new Float64Array(SIZE*SIZE),height=new Float64Array(SIZE*SIZE)
 for(const p of points){
  const x=(p.x-bounds.minX)/dx-.5,z=(p.z-bounds.minZ)/dz-.5,ix=Math.floor(x),iz=Math.floor(z)
  for(let a=0;a<2;a++)for(let b=0;b<2;b++){
   const index=(iz+b)*SIZE+ix+a,w=(a?x-ix:1-x+ix)*(b?z-iz:1-z+iz)
   mass[index]+=w;height[index]+=w*p.y
  }
 }
 function blur(data:Float64Array,step:number,axis:'x'|'z') {
  const radius=Math.ceil(4*SIGMA/step),kernel=Array.from({length:2*radius+1},(_,i)=>Math.exp(-.5*((i-radius)*step/SIGMA)**2)),sum=kernel.reduce((a,b)=>a+b,0)
  const result=new Float64Array(data.length)
  for(let z=0;z<SIZE;z++)for(let x=0;x<SIZE;x++)for(let k=-radius;k<=radius;k++){
   const a=axis==='x'?x+k:x,b=axis==='z'?z+k:z
   if(a>=0&&a<SIZE&&b>=0&&b<SIZE)result[z*SIZE+x]+=data[b*SIZE+a]*kernel[k+radius]/sum
  }
  return result
 }
 const density=blur(blur(mass,dx,'x'),dz,'z'),elevation=blur(blur(height,dx,'x'),dz,'z'),cdf=new Float64Array(density.length)
 let total=0
 for(let i=0;i<cdf.length;i++){total+=density[i];cdf[i]=total}
 return {version:GALAXY_FIELD_VERSION,seed:input.seed,nodeCount:points.length,bounds,
  sample(base,random,kind){
   // Display density only. The untouched base component keeps sparse graphs continuous.
   if(!points.length||kind==='field'||random()>=(kind==='core'?.25:.55))return base
   const target=random()*total
   let lo=0,hi=cdf.length-1
   while(lo<hi){const mid=(lo+hi)>>>1;if(cdf[mid]<target)lo=mid+1;else hi=mid}
   return [bounds.minX+(lo%SIZE+random())*dx,elevation[lo]/density[lo]+(random()-.5)*6,bounds.minZ+(Math.floor(lo/SIZE)+random())*dz]
  },
 }
}

// One exact-key entry per renderer; no hash collision can reuse a different layout.
export function createGalaxySpatialFieldCache() {
 let key='',field:GalaxySpatialField|null=null,builds=0,hits=0
 return {
  get(input:FieldInput){
   if(!Number.isFinite(input.seed)||!Number.isFinite(input.viewSize)||input.viewSize<=0)throw new Error('Invalid field parameters')
   const positions=[...input.positions].sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0)
   for(let i=0;i<positions.length;i++){const p=positions[i];if(!p.id||![p.x,p.y,p.z].every(Number.isFinite)||positions[i-1]?.id===p.id)throw new Error('Invalid field coordinate/identity')}
   const next=JSON.stringify([GALAXY_FIELD_VERSION,DEPTH_VERSION,input.layoutVersion,input.snapshotHash,input.seed,input.viewSize,positions.map(p=>[p.id,p.x,p.y,p.z])])
   if(next===key){hits++;return field}
   field=build({...input,positions});key=next;builds++;return field
  },
  clear(){key='';field=null},
  stats:()=>({version:GALAXY_FIELD_VERSION,entries:field?1:0,builds,hits,nodeCount:field?.nodeCount??0,grid:SIZE,sigma:SIGMA,baseWeight:.45,nodeWeight:.55,coreNodeWeight:.25}),
 }
}
