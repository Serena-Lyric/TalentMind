import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { graphComponent } from './helpers/graphComponent.ts'
import { adaptSnapshot } from '../src/graph/historicalSnapshot.ts'

test('隐藏类型的关联不静默跳到不可见节点；显式显示后选中且保留相机',async t=>{
 const app=graphComponent();t.after(app.stop);const s=app.state
 const nodes=[{id:'j',label:'Job',kind:'job',point:{x:0,y:0}},{id:'s',label:'Skill',kind:'skill',point:{x:100,y:0}}]
 const edge={source:'j',target:'s',kind:'REQUIRES',sourceIndex:0}
 app.setGraph(nodes,[edge]);s.highlightNode(nodes[0]);s.filters.find((f:any)=>f.kind==='skill').active=false
 const before={...s.transform};s.selectConnection(edge)
 assert.equal(s.selectedNode.value.id,'j')
 assert.equal(s.connectionHidden(edge),true)
 await s.showConnection(edge)
 assert.equal(s.selectedNode.value.id,'s');assert.deepEqual({...s.transform},before)
})

test('真实7845/11412渲染管线守恒；Python222条原边在过滤和高亮后身份不变',t=>{
 const raw=JSON.parse(readFileSync(new URL('../../exchange/m3/graph.json',import.meta.url),'utf8'))
 const artifact=JSON.parse(readFileSync(new URL('../../exchange/m3/overlays/p2-1-layout.json',import.meta.url),'utf8'))
 const graph=adaptSnapshot(raw),points=new Map(artifact.nodes.map((n:any)=>[n.id,{x:n.x,y:n.y}]))
 const nodes=graph.nodes.map(n=>({...n,point:points.get(n.id)})),before=JSON.stringify(raw)
 const app=graphComponent();t.after(app.stop);const s=app.state
 app.setGraph(nodes,graph.edges);s.artifact.value=artifact;s.transform.scale=.2;s.draw()
 const audit=app.debug().relationshipAudit
 assert.equal(audit.scope,11412);assert.equal(audit.interactionHidden,11412)
 assert.equal(Object.entries(audit).filter(([k])=>k!=='scope').reduce((sum,[,n])=>sum+Number(n),0),11412)
 const python=nodes.find(n=>n.id==='skill:python')!;s.highlightNode(python);s.draw()
 const sourceIndices=graph.edges.filter(e=>e.source===python.id||e.target===python.id).map(e=>e.sourceIndex).sort((a,b)=>a-b)
 assert.equal(sourceIndices.length,222)
 assert.deepEqual(app.debug().drawnSourceIndices.sort((a:number,b:number)=>a-b),sourceIndices)
 const transform={...s.transform};s.focusRelation(sourceIndices[0])
 assert.equal(s.selectedNode.value.id,python.id);assert.deepEqual({...s.transform},transform)
 assert.equal(app.debug().submitted,222);assert.equal(app.debug().focusedEdgeIndex,sourceIndices[0])
 s.filters.find((f:any)=>f.kind==='job').active=false;s.draw()
 assert.equal(app.debug().relationshipAudit.typeHidden,222);assert.equal(app.debug().relationshipAudit.submitted,0)
 assert.equal(s.directEdges.value.length,222)
 assert.equal(JSON.stringify(raw),before)
 nodes.forEach((n,i)=>{assert.equal(n.raw,raw.nodes[i]);assert.equal(n.sourceIndex,i)})
 graph.edges.forEach((e,i)=>{assert.equal(e.raw,raw.edges[i]);assert.equal(e.sourceIndex,i)})
})
