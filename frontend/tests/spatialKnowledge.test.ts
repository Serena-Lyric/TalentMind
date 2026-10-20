import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { Vector3, Frustum, Matrix4, PerspectiveCamera } from 'three'
import { adaptSnapshot } from '../src/graph/historicalSnapshot.ts'
import { spatialPoint } from '../src/graph/galaxy/spatialLayout.ts'
import { spatialRelations, relationCurve, pickProjected, derivedSpatialEdges } from '../src/graph/galaxy/spatialKnowledge.ts'

const graph=adaptSnapshot(JSON.parse(readFileSync(new URL('../../exchange/m3/graph.json',import.meta.url),'utf8')))
const layout=JSON.parse(readFileSync(new URL('../../exchange/m3/overlays/p2-1-layout.json',import.meta.url),'utf8'))
const points=new Map<string,Vector3>(layout.nodes.map((n:any)=>[n.id,spatialPoint(graph.nodes.find(g=>g.id===n.id)!,n)]))
const kinds=new Set(['job','skill','industry']),visible=new Set(graph.nodes.map(n=>n.id))
test('every Python original edge retains its index and exact 3D endpoints through planning',()=>{
 const result=spatialRelations(graph.edges,new Map(graph.nodes.map(n=>[n.id,n])),points,{visibleIds:visible,activeKinds:kinds,selectedId:'skill:python',scale:.1})
 assert.equal(result.edges.length,222);assert.equal(result.audit.submitted,222)
 assert.equal(new Set(result.edges.map(e=>e.sourceIndex)).size,222)
 for(const edge of result.edges){assert.equal(graph.edges[edge.sourceIndex!],edge);const c=relationCurve(edge,points);assert.deepEqual(c.getPoint(0),points.get(edge.source));assert.deepEqual(c.getPoint(1),points.get(edge.target))}
 const hidden=spatialRelations(graph.edges,new Map(graph.nodes.map(n=>[n.id,n])),points,{visibleIds:visible,activeKinds:new Set(['skill']),selectedId:'skill:python',scale:2})
 assert.equal(hidden.edges.length,0);assert.equal(hidden.audit.typeHidden,222)
})
test('all original edges are accounted for under orbit frustum and budget filtering',()=>{
 const camera=new PerspectiveCamera(43,1.5,.1,2000);camera.position.set(-180,60,-170);camera.lookAt(0,0,0);camera.updateMatrixWorld()
 const frustum=new Frustum().setFromProjectionMatrix(new Matrix4().multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse))
 const result=spatialRelations(graph.edges,new Map(graph.nodes.map(n=>[n.id,n])),points,{visibleIds:visible,activeKinds:kinds,scale:.2,frustum})
 assert.ok(result.edges.length<=120)
 assert.equal(Object.entries(result.audit).filter(([k])=>k!=='scope').reduce((n,[,v])=>n+v,0),11412)
})
test('overlap picking uses screen proximity then depth and never hits clipped or hidden nodes',()=>{
 const candidates=[{id:'back',x:40,y:50,depth:90,visible:true,radius:3},{id:'front',x:40,y:50,depth:10,visible:true,radius:3},{id:'clip',x:40,y:50,depth:-4,visible:false,radius:8}]
 assert.equal(pickProjected(candidates,40,50),'front')
 assert.equal(pickProjected(candidates,100,100),null)
 assert.equal(pickProjected(candidates.filter(n=>n.id!=='front'),40,50),'back')
})
test('derived overlay never draws an endpoint hidden by the selected original neighborhood',()=>{
 const byId=new Map(graph.nodes.map(n=>[n.id,n])),edge={source:'job:j-008bb9a49f5eb12b',target:'job:j-1ca0cc79a7f39631',kind:'candidate_similarity'}
 assert.equal(derivedSpatialEdges([edge],byId,visible,kinds,new Set([edge.source])).length,0)
 assert.equal(derivedSpatialEdges([edge],byId,visible,kinds,new Set([edge.source,edge.target])).length,1)
 assert.equal(derivedSpatialEdges([edge],byId,visible,new Set(['skill'])).length,0)
})
