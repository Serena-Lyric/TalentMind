import { test } from 'node:test'
import assert from 'node:assert/strict'
import { Color } from 'three'
import { fileURLToPath } from 'node:url'
import { readFileSync } from 'node:fs'
import { graphComponent } from './helpers/graphComponent.ts'
import { createGalaxyCamera } from '../src/graph/galaxy/camera.ts'

globalThis.DOMRect ??= class {x=0;y=0;width=0;height=0} as typeof DOMRect

function setup(t:any,version='p25') {
 const app=graphComponent();t.after(app.stop)
 const rig=createGalaxyCamera();t.after(rig.dispose);rig.resize(1200,800)
 const load=(name:string)=>app.load(fileURLToPath(new URL(`../src/graph/galaxy/${name}.ts`,import.meta.url)))
 const layer=load('knowledge').createSpatialKnowledge(rig,true,version);t.after(()=>layer.dispose())
 globalThis.window={devicePixelRatio:1} as any;t.after(()=>{delete (globalThis as any).window})
 const state={activeKinds:new Set(['job','skill','industry']),focusIds:new Set(),priority:new Set(),matches:new Set(),hoveredId:null,panels:[],showDerived:false,derived:[]}
 return {app,rig,load,layer,state}
}

test('P2.5主体由知识类型决定，ID只控制次级纹理；三类颜色独立且无红橙主色',t=>{
 const {load}=setup(t),{knowledgeProfile}=load('visualSemantics')
 for(const kind of ['job','skill','industry']) {
  const a=knowledgeProfile(kind,'a'),b=knowledgeProfile(kind,'b')
  assert.equal(a.type,b.type);assert.equal(a.color,b.color);assert.notEqual(a.seed,b.seed)
  const c=new Color(a.color);assert.ok(c.b>c.r||c.g>c.r)
 }
 assert.equal(new Set(['job','skill','industry'].map(k=>knowledgeProfile(k,'a').type)).size,3)
})

test('投影密度连续跨越网格边界，平移和微小缩放不闪变，极端重叠仍线性工作',t=>{
 const {load}=setup(t),{screenDensity,densityAppearance}=load('visualSemantics')
 const points=Array.from({length:200},(_,i)=>({id:String(i),x:31.99+i%10,y:20+Math.floor(i/10)}))
 const before=JSON.stringify(points),a=screenDensity(points),b=screenDensity(points.map(p=>({...p,x:p.x+.02,y:p.y+.01})))
 assert.ok(a.get('0')>1)
 assert.ok(Math.abs(a.get('0')-b.get('0'))<.1)
 assert.equal(JSON.stringify(points),before)
 const dense=densityAppearance(a.get('0'),false),isolated=densityAppearance(1,false),protectedStar=densityAppearance(a.get('0'),true)
 assert.ok(dense.halo<isolated.halo);assert.ok(dense.radius>0);assert.ok(dense.opacity>0)
 assert.equal(protectedStar.radius,1);assert.ok(protectedStar.halo>dense.halo)
 assert.equal(screenDensity(Array.from({length:7845},(_,i)=>({id:String(i),x:0,y:0}))).size,7845)
})

test('真实GPU线geometry从source到target连续插值，反向边与派生层保持方向/身份',t=>{
 const {app,layer,state,load}=setup(t),{knowledgeProfile}=load('visualSemantics')
 const nodes=[{id:'j',kind:'job',label:'岗位'},{id:'s',kind:'skill',label:'技能'},{id:'i',kind:'industry',label:'场景'}]
 const edges=[{source:'j',target:'s',kind:'REQUIRES',sourceIndex:17},{source:'s',target:'j',kind:'RELATED_TO',sourceIndex:18}]
 layer.setData(nodes,edges,nodes.map((n,i)=>({id:n.id,x:i*20,y:0,degree:2})))
 const result=layer.update(app.state.canvasRef.value,{...state,selectedId:'s',priority:new Set(['j','s']),showDerived:true,derived:[{source:'s',target:'i',kind:'candidate_similarity'}]})
 assert.equal(result.submitted,2);assert.equal(result.derivedSubmitted,1)
 const lines=layer.group.children.find((c:any)=>c.isLineSegments),geometry=lines.geometry
 const tint=geometry.getAttribute('tint'),indices=geometry.getAttribute('sourceIndex'),progress=geometry.getAttribute('progress')
 for(let i=0;i<tint.count;i++) {
  const edge=indices.getX(i)===17?edges[0]:indices.getX(i)===18?edges[1]:{source:'s',target:'i'}
  const expected=new Color(knowledgeProfile(nodes.find(n=>n.id===edge.source)!.kind,edge.source).color).lerp(new Color(knowledgeProfile(nodes.find(n=>n.id===edge.target)!.kind,edge.target).color),progress.getX(i))
  assert.ok(Math.abs(tint.getX(i)-expected.r)<1e-6);assert.ok(Math.abs(tint.getY(i)-expected.g)<1e-6);assert.ok(Math.abs(tint.getZ(i)-expected.b)<1e-6)
 }
 assert.equal(geometry.getAttribute('dashed'),undefined)
 // Focusing increases visibility without whitening away the endpoint colors.
 layer.update(app.state.canvasRef.value,{...state,selectedId:'s',focusedEdge:edges[0]})
 assert.equal(lines.material.uniforms.focus.value,17)
 assert.doesNotMatch(lines.material.fragmentShader,/mix\(color,vec3/)
})

test('密度只缩小视觉覆盖：非关联星体/坐标/拾取/默认无线保留，选中保持优先',t=>{
 const {app,layer,state}=setup(t)
 const nodes=Array.from({length:100},(_,i)=>({id:String(i),kind:'skill',label:String(i)}))
 layer.setData(nodes,[],nodes.map((n,i)=>({id:n.id,x:i*.3,y:0,degree:2})))
 const positions=[...layer.positions].map(([id,p]:any)=>[id,p.toArray()])
 const result=layer.update(app.state.canvasRef.value,state)
 assert.equal(result.visibleNodes,100);assert.equal(result.submitted,0);assert.ok(result.density.compressed>0)
 const p=layer.projected('0');assert.equal(layer.pick(p.x,p.y),'0')
 const points=layer.group.children.find((c:any)=>c.geometry?.getAttribute('stellarType')&&c.geometry.getAttribute('radius').count===100)
 const before=points.geometry.getAttribute('radius').getX(0)
 layer.update(app.state.canvasRef.value,{...state,selectedId:'0',focusIds:new Set(['0']),priority:new Set(['0'])})
 assert.ok(points.geometry.getAttribute('radius').getX(0)>before)
 assert.deepEqual([...layer.positions].map(([id,p]:any)=>[id,p.toArray()]),positions)
 assert.equal(layer.projected('99').visible,true)
})

test('P2.4明确回退保留原随机恒星材质',t=>{
 const {app,layer,state}=setup(t,'p24')
 layer.setData([{id:'s',kind:'skill',label:'s'}],[],[{id:'s',x:0,y:0,degree:1}])
 assert.equal(layer.update(app.state.canvasRef.value,state).stellarVersion,'stellar-id-v1')
 const point=layer.group.children.find((c:any)=>c.geometry?.getAttribute('stellarType'))
 assert.match(point.material.fragmentShader,/vec3 warm/)
})

test('P2.5真实快照Python222边全部进入渐变geometry，过滤与清除守恒，原文及索引不变',t=>{
 const {app,layer,state}=setup(t)
 const root=new URL('../../',import.meta.url)
 const snapshot=JSON.parse(readFileSync(new URL('exchange/m3/graph.json',root),'utf8'))
 const artifact=JSON.parse(readFileSync(new URL('exchange/m3/overlays/p2-1-layout.json',root),'utf8'))
 const graph=app.load(fileURLToPath(new URL('../src/graph/historicalSnapshot.ts',import.meta.url))).adaptSnapshot(snapshot)
 assert.equal(graph.nodes.length,7845);assert.equal(graph.edges.length,11412)
 const before=JSON.stringify(graph),direct=graph.edges.filter((e:any)=>e.source==='skill:python'||e.target==='skill:python')
 assert.equal(direct.length,222)
 layer.setData(graph.nodes,graph.edges,artifact.nodes)
 const focus=new Set<string>(['skill:python',...direct.flatMap((e:any)=>[e.source,e.target])])
 const result=layer.update(app.state.canvasRef.value,{...state,selectedId:'skill:python',focusIds:focus,priority:focus})
 assert.equal(result.submitted,222);assert.deepEqual(new Set(result.drawnSourceIndices),new Set(direct.map((e:any)=>e.sourceIndex)))
 const lines=layer.group.children.find((c:any)=>c.isLineSegments),tint=lines.geometry.getAttribute('tint')
 assert.equal(tint.count,222*24)
 for(const edge of direct){
  const check=layer.update(app.state.canvasRef.value,{...state,selectedId:'skill:python',focusIds:focus,priority:focus,focusedEdge:edge})
  assert.equal(lines.material.uniforms.focus.value,edge.sourceIndex);assert.equal(check.submitted,222)
 }
 const hidden=layer.update(app.state.canvasRef.value,{...state,selectedId:'skill:python',focusIds:focus,priority:focus,activeKinds:new Set(['skill','industry'])})
 assert.equal(hidden.submitted,0);assert.equal(hidden.audit.typeHidden,222)
 const cleared=layer.update(app.state.canvasRef.value,state);assert.equal(cleared.submitted,0)
 assert.equal(JSON.stringify(graph),before)
})
