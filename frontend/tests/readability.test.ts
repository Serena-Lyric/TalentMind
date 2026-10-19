import { test } from 'node:test'
import assert from 'node:assert/strict'
import { planRelations, fanControls, curveIntersects } from '../src/graph/relationReadability.ts'
import { starAppearance, starIntensity, placeStarLabels } from '../src/graph/starPresentation.ts'
import { comparisonSettings } from '../src/graph/comparisonView.ts'
import { readFileSync } from 'node:fs'

test('三方对照复用同一相机，近景中心绑定实际Python坐标，不凭空填写',()=>{
 const artifact=JSON.parse(readFileSync(new URL('../../exchange/m3/overlays/p2-1-layout.json',import.meta.url),'utf8'))
 const python=artifact.nodes.find((n:any)=>n.id==='skill:python')
 const views=['p1a2','p21','p22'].map(v=>comparisonSettings(`?graphVisual=${v}&graphCompare=near`))
 assert.deepEqual(views[0].transform,views[1].transform);assert.deepEqual(views[1].transform,views[2].transform)
 assert.equal(views[0].transform?.x,-python.x);assert.equal(views[0].transform?.y,-python.y)
 assert.equal(comparisonSettings('').visual,'p22')
})

const node=(id:string,kind='skill')=>({id,label:id,kind,size:8,color:''}) as any
const bounds={left:-100,right:100,top:-100,bottom:100}
test('关系显示逐边守恒：数据缺失/类型/LOD/坐标/视口/长度/预算分别对账',()=>{
 const nodes=[node('j','job'),...['shown','type','lod','unplaced','off1','off2','long1','long2','budget'].map(id=>node(id,id==='type'?'industry':'skill'))]
 const positions=new Map(nodes.filter(n=>n.id!=='unplaced').map(n=>[n.id,{x:0,y:0}]))
 positions.set('off1',{x:1000,y:1000});positions.set('off2',{x:1100,y:1100})
 positions.set('long1',{x:-500,y:0});positions.set('long2',{x:500,y:0})
 positions.set('budget',{x:20,y:0})
 const edges=[['j','shown'],['j','type'],['j','lod'],['j','unplaced'],['off1','off2'],['long1','long2'],['j','budget'],['j','missing']].map(([source,target],sourceIndex)=>({source,target,kind:'REQUIRES',sourceIndex}))
 const plan=planRelations(edges,nodes,positions,{activeKinds:new Set(['job','skill']),visibleIds:new Set(nodes.filter(n=>n.id!=='lod').map(n=>n.id)),showUnselected:true,viewport:bounds,scale:1,limit:1})
 assert.deepEqual(plan.audit,{scope:8,interactionHidden:0,invalidEndpoint:1,typeHidden:1,lodHidden:1,unplaced:1,viewportHidden:1,lengthHidden:1,budgetHidden:1,submitted:1})
 assert.equal(plan.edges[0].sourceIndex,0)
})
test('选中222真实直连不做视口/长度/预算删除；曲线保持全部原边身份及端点',()=>{
 const nodes=[node('s'),...Array.from({length:222},(_,i)=>node('j'+i,'job'))]
 const positions=new Map(nodes.map((n,i)=>[n.id,{x:i?1000+i:0,y:i*.01}]))
 const edges=nodes.slice(1).map((n,sourceIndex)=>({source:n.id,target:'s',kind:'REQUIRES',sourceIndex}))
 const plan=planRelations(edges,nodes,positions,{activeKinds:new Set(['job','skill']),visibleIds:new Set(nodes.map(n=>n.id)),selectedId:'s',showUnselected:true,viewport:bounds,scale:.1,limit:1})
 assert.equal(plan.edges.length,222);assert.equal(plan.audit.budgetHidden,0);assert.equal(plan.audit.viewportHidden,0);assert.equal(plan.audit.lengthHidden,0)
 const controls=fanControls(plan.edges,positions,'s')
 assert.equal(controls.size,222);assert.equal(new Set([...controls.values()].map(p=>p.y)).size,222)
 assert.deepEqual(plan.edges.map(e=>e.sourceIndex).sort((a,b)=>a-b),edges.map(e=>e.sourceIndex))
 assert.ok(curveIntersects({x:-200,y:0},{x:0,y:100},{x:200,y:0},bounds))
})
test('星体类型权重和尺寸固定，不接收统计字段；核心锐利而外围轻柔',()=>{
 const job=starAppearance('job',2),skill=starAppearance('skill',2),scene=starAppearance('industry',2)
 assert.ok(job.radius>skill.radius && skill.radius>scene.radius)
 assert.ok(starAppearance('job',100).radius<=5)
 assert.ok(starIntensity(0)>starIntensity(.2)*3)
 assert.ok(starIntensity(.6)>0 && starIntensity(.6)<.04)
})
test('标签选择其他可用位置，避开其他星核和标签，并执行密度上限',()=>{
 const candidates=[{id:'a',priority:4,bounds:{left:0,right:40,top:0,bottom:12},alternatives:[{left:0,right:40,top:30,bottom:42}]},{id:'b',priority:1,bounds:{left:50,right:90,top:0,bottom:12}}]
 const result=placeStarLabels(candidates,{left:0,right:100,top:0,bottom:100},[],[{id:'other',bounds:{left:10,right:20,top:0,bottom:12}}],1)
 assert.equal(result.size,1);assert.equal(result.get('a')?.top,30)
})
test('亚像素相切的真实曲线仍计入画布相交，不依赖16段抽样',()=>{
 assert.equal(curveIntersects({x:-200,y:-20.2148},{x:0,y:17.9452},{x:200,y:-15.8948},{left:-1000,right:1000,top:0,bottom:100}),true)
 assert.equal(curveIntersects({x:-200,y:-200},{x:0,y:-100},{x:200,y:-200},{left:-1000,right:1000,top:0,bottom:100}),false)
})
test('修订版近景长边参与可解释预算，不再被长度阈值提前全部删除',()=>{
 const nodes=['a','b','c','d'].map(id=>node(id,'job'))
 const positions=new Map([['a',{x:-500,y:0}],['b',{x:500,y:0}],['c',{x:0,y:20}],['d',{x:20,y:20}]])
 const edges=[{source:'a',target:'b',kind:'RELATED_TO'},{source:'c',target:'d',kind:'RELATED_TO'}]
 const result=planRelations(edges,nodes,positions,{activeKinds:new Set(['job']),visibleIds:new Set(nodes.map(n=>n.id)),showUnselected:true,viewport:bounds,scale:1.35,limit:2,preserveLongNear:true})
 assert.equal(result.audit.lengthHidden,0);assert.equal(result.edges.length,2)
})
