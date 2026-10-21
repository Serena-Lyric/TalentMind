// Read-only spatial diagnostics. Optional layout paths remain private; output has no identities/text.
import {readFileSync} from 'node:fs'
import {createHash} from 'node:crypto'
import {performance} from 'node:perf_hooks'
import {createGalaxySpatialFieldCache} from '../src/graph/galaxy/GalaxySpatialField.ts'
import {spatialPoint} from '../src/graph/galaxy/spatialLayout.ts'
import {generateParticles} from '../src/graph/galaxy/generate.js'

const paths=process.argv.slice(2)
if(!paths.length)paths.push('../exchange/m3/overlays/p2-1-layout.json')
const result=[]
for(const path of paths){
 const bytes=readFileSync(path),layout=JSON.parse(bytes.toString('utf8'))
 const positions=layout.nodes.map((n:any)=>({id:n.id,...spatialPoint({id:n.id,kind:'skill'},n)}))
 const cache=createGalaxySpatialFieldCache(),start=performance.now()
 const field=cache.get({positions,layoutVersion:layout.schema_version,snapshotHash:layout.snapshot_sha256_lf,seed:261018,viewSize:200})!
 const buildMs=performance.now()-start
 const bins=40,span=240,step=span/bins,nodeDensity=new Float64Array(bins*bins),empty=new Set<number>()
 for(let z=0;z<bins;z++)for(let x=0;x<bins;x++){
  const px=(x+.5)*step-span/2,pz=(z+.5)*step-span/2,index=z*bins+x
  let nearest=Infinity
  for(const p of positions){const d2=(px-p.x)**2+(pz-p.z)**2;nearest=Math.min(nearest,d2);nodeDensity[index]+=Math.exp(-d2/(2*11**2))}
  if(nearest>22**2)empty.add(index)
 }
 function summarize(data:Float32Array){
  const histogram=new Float64Array(bins*bins)
  let outside=0,emptyCount=0
  for(let i=0;i<data.length;i+=3){
   const x=Math.floor((data[i]+span/2)/step),z=Math.floor((data[i+2]+span/2)/step)
   if(x<0||x>=bins||z<0||z>=bins){outside++;continue}
   const index=z*bins+x;histogram[index]++;if(empty.has(index))emptyCount++
  }
  const mean=(a:Float64Array)=>a.reduce((s,n)=>s+n,0)/a.length,a=mean(histogram),b=mean(nodeDensity)
  let cross=0,aa=0,bb=0
  histogram.forEach((n,i)=>{cross+=(n-a)*(nodeDensity[i]-b);aa+=(n-a)**2;bb+=(nodeDensity[i]-b)**2})
  return {correlation:cross/Math.sqrt(aa*bb),emptyFraction:emptyCount/(data.length/3),outsideFraction:outside/(data.length/3)}
 }
 const versions=[]
 for(const [name,value] of [['legacy',null],['node-field-v1',field]] as const){
  const begin=performance.now(),parts=['dust','mist','core','stars'].map(kind=>generateParticles(kind,value))
  const elapsed=performance.now()-begin,all=new Float32Array(parts.reduce((n,p)=>n+p.position.length,0))
  let offset=0;for(const p of parts){all.set(p.position,offset);offset+=p.position.length}
  if(!all.every(Number.isFinite))throw new Error('Non-finite particle')
  versions.push({version:name,particles:all.length/3,generateMs:elapsed,positionSha256:createHash('sha256').update(new Uint8Array(all.buffer)).digest('hex'),dust:summarize(parts[0].position),all:summarize(all)})
 }
 const repeat=generateParticles('dust',createGalaxySpatialFieldCache().get({positions:[...positions].reverse(),layoutVersion:layout.schema_version,snapshotHash:layout.snapshot_sha256_lf,seed:261018,viewSize:200}))
 const first=generateParticles('dust',field)
 if(!Buffer.from(repeat.position.buffer).equals(Buffer.from(first.position.buffer)))throw new Error('Non-deterministic replay')
 result.push({nodeCount:positions.length,layoutSha256:createHash('sha256').update(bytes).digest('hex'),snapshotHash:layout.snapshot_sha256_lf,buildMs,bounds:field.bounds,cache:cache.stats(),replayIdentical:true,versions})
}
console.log(JSON.stringify({method:'40x40 XZ bins across [-120,120]; Pearson against node Gaussian KDE sigma=11; empty cell center farther than22 world units from every node; field sphere excluded; no semantic metric',datasets:result},null,2))
