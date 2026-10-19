import { test } from 'node:test'
import assert from 'node:assert/strict'
import { Vector3 } from 'three'
import { graphComponent } from './helpers/graphComponent.ts'
import { spatialRelations } from '../src/graph/galaxy/spatialKnowledge.ts'
import { createGalaxyCamera } from '../src/graph/galaxy/camera.ts'
import { fileURLToPath } from 'node:url'
globalThis.DOMRect ??= class {x=0;y=0;width=0;height=0} as typeof DOMRect

const nodes=['a','b','c'].map((id,i)=>({id,label:id,kind:'job',point:{x:i*40,y:0}})) as any[]
const edges=[{source:'a',target:'b',kind:'RELATED_TO',sourceIndex:0},{source:'b',target:'c',kind:'RELATED_TO',sourceIndex:1}]
test('P2.4 默认历史关系提交为0，按交互隐藏数与总量守恒',()=>{
 const plan=spatialRelations(edges,new Map(nodes.map(n=>[n.id,n])),new Map(nodes.map(n=>[n.id,new Vector3(n.point.x,0,0)])),{visibleIds:new Set(nodes.map(n=>n.id)),activeKinds:new Set(['job']),scale:1})
 assert.equal(plan.edges.length,0)
 assert.equal(plan.audit.interactionHidden,2)
 assert.equal(plan.audit.scope,2)
})
test('P2.4 固定与三维共享状态：非邻居保持可见可选，改选与清除立即更新关系',async t=>{
 const app=graphComponent();t.after(app.stop);app.setGraph(nodes,edges)
 const s=app.state;s.draw();assert.equal(app.debug().submitted,0)
 s.highlightNode(nodes[0]);s.draw()
 assert.equal(s.visibleNode(nodes[2]),true)
 assert.equal(s.nodeAt(680,400).id,'c')
 assert.equal(app.debug().visibleNodes,3);assert.deepEqual(app.debug().drawnSourceIndices,[0])
 s.highlightNode(nodes[2]);s.draw();assert.deepEqual(app.debug().drawnSourceIndices,[1])
 const before={...s.transform};await s.clearSelection();assert.deepEqual(s.transform,before)
 assert.equal(app.debug().submitted,0);assert.equal(app.debug().visibleNodes,3)
})
test('P2.4 镜头只拟合直接邻域，完整返回后取消不移动镜头',async t=>{
 const app=graphComponent();t.after(app.stop);app.setGraph(nodes,edges)
 const s=app.state;s.highlightNode(nodes[0]);s.draw()
 const before={...s.transform};await s.viewAllConnections()
 assert.equal(app.debug().lastFit.points,2)
 s.returnToView();assert.deepEqual({...s.transform},before)
 await s.clearSelection();assert.deepEqual({...s.transform},before)
})
test('P2.4 实际批量材质保留非关联点、派生层独立，清除选中清空GPU原边',t=>{
 const app=graphComponent();t.after(app.stop)
 const rig=createGalaxyCamera();t.after(rig.dispose);rig.resize(1200,800)
 const {createSpatialKnowledge}=app.load(fileURLToPath(new URL('../src/graph/galaxy/knowledge.ts',import.meta.url)))
 const layer=createSpatialKnowledge(rig);t.after(()=>layer.dispose())
 const input=nodes.map(n=>({...n,point:undefined})),layout=nodes.map(n=>({id:n.id,x:n.point.x,y:0,degree:2}))
 layer.setData(input,edges,layout)
 const state={activeKinds:new Set(['job']),focusIds:new Set(['a','b']),priority:new Set(['a','b']),matches:new Set(),hoveredId:null,panels:[],showDerived:false,derived:[],selectedId:'a'}
 globalThis.window={devicePixelRatio:1} as any;t.after(()=>{delete (globalThis as any).window})
 const before=rig.capture(),selected=layer.update(app.state.canvasRef.value,state)
 assert.equal(selected.visibleNodes,3);assert.equal(selected.submitted,1);assert.equal(selected.transitionParticles,36)
 const points=layer.group.children.filter((c:any)=>c.geometry?.getAttribute('stellarType'))
 assert.equal(points[0].geometry.getAttribute('radius').getX(2)>0,true)
 const derived=layer.update(app.state.canvasRef.value,{...state,showDerived:true,derived:[{source:'b',target:'c',kind:'candidate_similarity'}]})
 assert.equal(derived.submitted,1);assert.equal(derived.derivedSubmitted,1)
 const empty=layer.update(app.state.canvasRef.value,{...state,selectedId:undefined,priority:new Set()})
 assert.equal(empty.submitted,0);assert.equal(empty.visibleNodes,3)
 assert.deepEqual(rig.capture(),before)
 const lines=layer.group.children.find((c:any)=>c.isLineSegments)
 assert.equal(lines.geometry.drawRange.count,0)
})
