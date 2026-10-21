import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createGalaxySpatialFieldCache } from '../src/graph/galaxy/GalaxySpatialField.ts'
import { spatialPoint } from '../src/graph/galaxy/spatialLayout.ts'
import { generateParticles } from '../src/graph/galaxy/generate.js'
import { createDust } from '../src/graph/galaxy/particles.js'
import { Group, Points } from 'three'

const input=(x=60)=>({layoutVersion:'layout-test',snapshotHash:'snapshot-test',seed:261018,viewSize:200,
 positions:Array.from({length:71},(_,i)=>({id:`n${i}`,x:x+i%7,y:4,z:-20+Math.floor(i/7)}))})

test('full background distribution follows moved nodes, retains an extended spiral and fixed particle budget',()=>{
 const cache=createGalaxySpatialFieldCache(),a=generateParticles('dust',cache.get(input(60))),b=generateParticles('dust',cache.get(input(-60)))
 const mean=(array:Float32Array)=>array.reduce((s,v,i)=>s+(i%3===0?v:0),0)/(array.length/3)
 assert.ok(mean(a.position)>25);assert.ok(mean(b.position)<-25)
 assert.equal(a.count,110000);assert.equal(b.count,a.count)
 const extended=Array.from(a.position).filter((_,i)=>i%3===0).filter(x=>x<0).length
 assert.ok(extended>10000,'base arms must survive a sparse off-center graph')
 assert.deepEqual(generateParticles('field',cache.get(input(60))),generateParticles('field'))
})

test('deterministic field and particles ignore input order; exact cache invalidates every spatial contract input',()=>{
 const cache=createGalaxySpatialFieldCache(),source=input(),before=JSON.stringify(source),a=cache.get(source)
 assert.equal(cache.get({...source,positions:[...source.positions].reverse()}),a)
 assert.deepEqual(generateParticles('stars',a),generateParticles('stars',createGalaxySpatialFieldCache().get(source)))
 assert.notDeepEqual(generateParticles('stars',a).position,generateParticles('stars',cache.get({...source,seed:8})).position)
 for(const change of [{seed:8},{layoutVersion:'next'},{snapshotHash:'next'},{viewSize:240},{positions:input(20).positions}])assert.notEqual(cache.get({...source,...change}),a)
 assert.equal(JSON.stringify(source),before)
 cache.clear();assert.equal(cache.stats().entries,0)
})

test('empty input replays legacy exactly; invalid or duplicate coordinates fail before rendering',()=>{
 const cache=createGalaxySpatialFieldCache()
 assert.deepEqual(generateParticles('mist',cache.get({...input(),positions:[]})),generateParticles('mist'))
 assert.throws(()=>cache.get({...input(),positions:[{id:'bad',x:NaN,y:0,z:0}]}))
 assert.throws(()=>cache.get({...input(),positions:[input().positions[0],input().positions[0]]}))
})

test('historical 7845 coordinates use spatialPoint unchanged and finite field sampling covers the outer nodes',()=>{
 const layout=JSON.parse(readFileSync(new URL('../../exchange/m3/overlays/p2-1-layout.json',import.meta.url),'utf8'))
 const positions=layout.nodes.map((n:any)=>({id:n.id,...spatialPoint({id:n.id,kind:'skill'},n)}))
 const source={...input(),positions,layoutVersion:layout.schema_version,snapshotHash:layout.snapshot_sha256_lf}
 const field=createGalaxySpatialFieldCache().get(source)!,data=generateParticles('stars',field)
 assert.equal(field.nodeCount,7845);assert.ok(data.position.every(Number.isFinite))
 assert.ok(field.bounds.minX<Math.min(...positions.map((p:any)=>p.x)))
 assert.ok(field.bounds.maxX>Math.max(...positions.map((p:any)=>p.x)))
})

test('rendered dust replaces its distribution once per field, camera/resize keep buffers, legacy restores exact bytes',()=>{
 const scene=new Group(),dust=createDust(scene,true),layer=scene.children[0] as Points
 const original=layer.geometry.getAttribute('position'),material=layer.material
 const field=createGalaxySpatialFieldCache().get(input())
 dust.setField(field)
 const guided=layer.geometry.getAttribute('position')
 assert.notDeepEqual(guided.array,original.array)
 dust.setField(field);dust.resize(900,1.5);dust.update(12)
 assert.equal(layer.geometry.getAttribute('position'),guided);assert.equal(layer.material,material)
 dust.setField(null);assert.deepEqual(layer.geometry.getAttribute('position').array,original.array)
 for(const item of scene.children as Points[]){item.geometry.dispose();(item.material as any).dispose()}
})
